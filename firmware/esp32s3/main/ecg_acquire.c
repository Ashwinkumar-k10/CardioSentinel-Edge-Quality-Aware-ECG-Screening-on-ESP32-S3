/**
 * CardioSentinel Edge - ADS1292R SPI ECG Acquisition & Replay Implementation
 */

#include "ecg_acquire.h"
#include <string.h>

#ifdef ESP_PLATFORM
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/spi_master.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"

static const char *TAG = "ECG_ACQUIRE";
static spi_device_handle_t spi_dev;
#endif

static ecg_ring_buffer_t *s_ring_buf = NULL;
static ecg_acquire_state_t s_state;

void ecg_acquire_init(ecg_ring_buffer_t *target_ring_buf) {
    s_ring_buf = target_ring_buf;
    memset(&s_state, 0, sizeof(s_state));
    s_state.mode = ACQUIRE_MODE_DATASET_REPLAY;
    s_state.sampling_rate_hz = 250.0f;
    s_state.is_running = false;

#ifdef ESP_PLATFORM
    ESP_LOGI(TAG, "Initializing SPI interface for ADS1292R...");
    // Configuration details loaded from board_esp32s3.yaml
    spi_bus_config_t buscfg = {
        .miso_io_num = 13,
        .mosi_io_num = 11,
        .sclk_io_num = 12,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 32
    };
    spi_device_interface_config_t devcfg = {
        .clock_speed_hz = 1000000, // 1 MHz
        .mode = 1,                 // CPOL=0, CPHA=1 for ADS1292R
        .spics_io_num = 10,
        .queue_size = 3
    };
    spi_bus_initialize(SPI2_HOST, &buscfg, SPI_DMA_CH_AUTO);
    spi_bus_add_device(SPI2_HOST, &devcfg, &spi_dev);

    // Configure /DRDY interrupt pin
    gpio_config_t io_conf = {
        .intr_type = GPIO_INTR_NEGEDGE,
        .mode = GPIO_MODE_INPUT,
        .pin_bit_mask = (1ULL << 4),
        .pull_up_en = GPIO_PULLUP_ENABLE
    };
    gpio_config(&io_conf);
#endif
}

bool ecg_acquire_start(acquire_mode_t mode) {
    s_state.mode = mode;
    s_state.is_running = true;
    s_state.samples_acquired = 0;
    s_state.dropped_samples = 0;
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
