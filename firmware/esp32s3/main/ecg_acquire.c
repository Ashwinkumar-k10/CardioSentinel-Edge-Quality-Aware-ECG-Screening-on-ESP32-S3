/**
 * CardioSentinel Edge - ADS1292R SPI ECG Acquisition & Replay Implementation
 * Target: ESP32-S3 Core 0 (Priority 24 Hard Real-Time)
 */

#include "ecg_acquire.h"
#include <string.h>

#ifdef ESP_PLATFORM
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/spi_master.h"
#include "driver/gpio.h"
#include "driver/adc.h"
#include "esp_log.h"
#include "esp_timer.h"

static const char *TAG = "ECG_ACQUIRE";
static spi_device_handle_t s_spi_dev;
static TaskHandle_t s_acquire_task_handle = NULL;
static const int ADS1292_DRDY_PIN = 4;

// AD8232 Analog Front End Pins
static const adc1_channel_t AD8232_ADC_CH = ADC1_CHANNEL_0; // GPIO 1 on ESP32-S3
static const gpio_num_t AD8232_LO_PLUS = GPIO_NUM_2;        // Leads-Off +
static const gpio_num_t AD8232_LO_MINUS = GPIO_NUM_3;       // Leads-Off -
#endif

static ecg_ring_buffer_t *s_ring_buf = NULL;
static ecg_acquire_state_t s_state;

#ifdef ESP_PLATFORM
static void IRAM_ATTR ads1292_drdy_isr(void *arg) {
    BaseType_t high_task_woken = pdFALSE;
    if (s_acquire_task_handle != NULL) {
        vTaskNotifyGiveFromISR(s_acquire_task_handle, &high_task_woken);
        portYIELD_FROM_ISR(high_task_woken);
    }
}

static void ads1292_spi_acquisition_task(void *pvParameters) {
    uint8_t rx_data[9]; // 24-bit Status (3 bytes) + 24-bit CH1 (3 bytes) + 24-bit CH2 (3 bytes)
    spi_transaction_t t;
    memset(&t, 0, sizeof(t));
    t.length = 72; // 9 bytes * 8 bits
    t.rx_buffer = rx_data;

    ESP_LOGI(TAG, "ADS1292R Acquisition Task running on Core %d", xPortGetCoreID());

    while (s_state.is_running) {
        // Wait for /DRDY falling edge interrupt notification
        if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(50)) == pdTRUE) {
            esp_err_t err = spi_device_polling_transmit(s_spi_dev, &t);
            if (err == ESP_OK) {
                // Parse Channel 1: 24-bit signed 2's complement
                int32_t raw_ch1 = ((int32_t)rx_data[3] << 24) |
                                  ((int32_t)rx_data[4] << 16) |
                                  ((int32_t)rx_data[5] << 8);
                raw_ch1 = raw_ch1 >> 8; // Arithmetic shift preserves sign bit

                // Convert to millivolts: Vref = 2.42V, Gain = 6 default
                // V_in = (raw / (2^23 - 1)) * (Vref / Gain) * 1000.0 mV
                float sample_mv = ((float)raw_ch1 / 8388607.0f) * (2.42f / 6.0f) * 1000.0f;

                if (s_ring_buf) {
                    bool ok = ecg_ring_buffer_push(s_ring_buf, sample_mv);
                    if (ok) {
                        s_state.samples_acquired++;
                    } else {
                        s_state.dropped_samples++;
                    }
                }
            }
        }
    }
    vTaskDelete(NULL);
}

static void ad8232_adc_acquisition_task(void *pvParameters) {
    ESP_LOGI(TAG, "AD8232 ADC Acquisition Task running on Core %d (250 Hz Periodic)", xPortGetCoreID());
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(4); // 4ms = 250 Hz

    while (s_state.is_running) {
        int raw = adc1_get_raw(AD8232_ADC_CH);
        int lo_plus = gpio_get_level(AD8232_LO_PLUS);
        int lo_minus = gpio_get_level(AD8232_LO_MINUS);

        float sample_mv = 0.0f;
        if (lo_plus == 1 || lo_minus == 1) {
            // Electrode detached: drive flatline so ASQI flags lead-off immediately
            sample_mv = 0.0f;
        } else {
            // 12-bit ADC (0 to 4095), ~1.65V mid-scale baseline
            // Body-surface mV with ~100x AD8232 front-end gain:
            sample_mv = (((float)raw - 2048.0f) * (3300.0f / 4095.0f)) / 100.0f;
        }

        if (s_ring_buf) {
            bool ok = ecg_ring_buffer_push(s_ring_buf, sample_mv);
            if (ok) {
                s_state.samples_acquired++;
            } else {
                s_state.dropped_samples++;
            }
        }

        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
    vTaskDelete(NULL);
}
#endif

void ecg_acquire_init(ecg_ring_buffer_t *target_ring_buf) {
    s_ring_buf = target_ring_buf;
    memset(&s_state, 0, sizeof(s_state));
    s_state.mode = ACQUIRE_MODE_DATASET_REPLAY;
    s_state.sampling_rate_hz = 250.0f;
    s_state.is_running = false;

#ifdef ESP_PLATFORM
    ESP_LOGI(TAG, "Initializing SPI master interface for ADS1292R...");
    spi_bus_config_t buscfg = {
        .miso_io_num = 13,
        .mosi_io_num = 11,
        .sclk_io_num = 12,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 32
    };
    spi_device_interface_config_t devcfg = {
        .clock_speed_hz = 1000000, // 1 MHz SPI clock
        .mode = 1,                 // CPOL=0, CPHA=1 (SPI Mode 1 for ADS1292R)
        .spics_io_num = 10,
        .queue_size = 3
    };
    spi_bus_initialize(SPI2_HOST, &buscfg, SPI_DMA_CH_AUTO);
    spi_bus_add_device(SPI2_HOST, &devcfg, &s_spi_dev);

    // Configure /DRDY interrupt pin
    gpio_config_t io_conf = {
        .intr_type = GPIO_INTR_NEGEDGE,
        .mode = GPIO_MODE_INPUT,
        .pin_bit_mask = (1ULL << ADS1292_DRDY_PIN),
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE
    };
    gpio_config(&io_conf);
    gpio_install_isr_service(0);
    gpio_isr_handler_add(ADS1292_DRDY_PIN, ads1292_drdy_isr, NULL);
    // Configure AD8232 ADC1 channel & leads-off GPIOs
    adc1_config_width(ADC_WIDTH_BIT_12);
    adc1_config_channel_atten(AD8232_ADC_CH, ADC_ATTEN_DB_11);

    gpio_config_t lo_conf = {
        .intr_type = GPIO_INTR_DISABLE,
        .mode = GPIO_MODE_INPUT,
        .pin_bit_mask = (1ULL << AD8232_LO_PLUS) | (1ULL << AD8232_LO_MINUS),
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE
    };
    gpio_config(&lo_conf);
#endif
}

bool ecg_acquire_start(acquire_mode_t mode) {
    s_state.mode = mode;
    s_state.is_running = true;
    s_state.samples_acquired = 0;
    s_state.dropped_samples = 0;

#ifdef ESP_PLATFORM
    if (mode == ACQUIRE_MODE_ADS1292R_SPI) {
        xTaskCreatePinnedToCore(
            ads1292_spi_acquisition_task,
            "ecg_spi_acquire",
            4096,
            NULL,
            24, // Priority 24 (Hard real-time)
            &s_acquire_task_handle,
            0   // Pinned to Core 0
        );
    } else if (mode == ACQUIRE_MODE_AD8232_ADC) {
        xTaskCreatePinnedToCore(
            ad8232_adc_acquisition_task,
            "ad8232_acquire",
            4096,
            NULL,
            24, // Priority 24 (Hard real-time)
            &s_acquire_task_handle,
            0   // Pinned to Core 0
        );
    }
#endif
    return true;
}

void ecg_acquire_stop(void) {
    s_state.is_running = false;
}

ecg_acquire_state_t ecg_acquire_get_state(void) {
    if (s_ring_buf) {
        s_state.dropped_samples = ecg_ring_buffer_get_dropped(s_ring_buf);
    }
    return s_state;
}

bool ecg_acquire_inject_sample(float sample) {
    if (!s_ring_buf || !s_state.is_running) return false;
    bool ok = ecg_ring_buffer_push(s_ring_buf, sample);
    if (ok) {
        s_state.samples_acquired++;
    }
    return ok;
}
