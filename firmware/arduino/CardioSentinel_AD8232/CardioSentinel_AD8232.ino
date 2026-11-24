/**
 * CardioSentinel Edge - Arduino IDE Firmware for ESP32-S3 + AD8232
 * TECHgium Challenge 26 Research Prototype
 * 
 * Hardware:
 *   - ESP32-S3 (Dual-Core @ 240 MHz, 8MB PSRAM)
 *   - AD8232 Single-Lead ECG Analog Front-End
 * Pinout:
 *   - AD8232 OUTPUT -> GPIO 1 (ADC1 Ch 0)
 *   - AD8232 LO+    -> GPIO 2 (Leads-Off +)
 *   - AD8232 LO-    -> GPIO 3 (Leads-Off -)
 *   - AD8232 3.3V   -> 3V3
 *   - AD8232 GND    -> GND
 */

#include <Arduino.h>

extern "C" {
#include "ring_buffer.h"
#include "signal_quality.h"
#include "morphology_guard.h"
#include "inference.h"
#include "decision_engine.h"
}

// Pin Definitions
#define PIN_ECG_OUT   1
#define PIN_LO_PLUS   2
#define PIN_LO_MINUS  3

static ecg_ring_buffer_t g_ring_buf;
static float g_window_raw[ECG_WINDOW_SAMPLES];
static float g_window_filtered[ECG_WINDOW_SAMPLES];

static TaskHandle_t s_sample_task_handle = NULL;
static uint32_t s_seq_id = 1;

// 5-point moving average smoothing filter (0.5 - 40 Hz approximation)
static void apply_conservative_filter(const float *raw, float *filt, size_t n) {
    if (!raw || !filt || n == 0) return;
    for (size_t i = 2; i < n - 2; i++) {
        filt[i] = 0.1f * raw[i - 2] + 0.2f * raw[i - 1] + 0.4f * raw[i] + 0.2f * raw[i + 1] + 0.1f * raw[i + 2];
    }
    filt[0] = raw[0];
    filt[1] = raw[1];
    filt[n - 2] = raw[n - 2];
    filt[n - 1] = raw[n - 1];
}

// Core 0: 250 Hz Periodic Hard Real-Time Sampler Task
void sampleTask(void *pvParameters) {
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(4); // 4 ms = 250 Hz

    while (1) {
        int lo_p = digitalRead(PIN_LO_PLUS);
        int lo_m = digitalRead(PIN_LO_MINUS);
        int raw_adc = analogRead(PIN_ECG_OUT);

        float sample_mv = 0.0f;
        if (lo_p == HIGH || lo_m == HIGH) {
            // Electrode detached: zero out signal to force ASQI flatline detection
            sample_mv = 0.0f;
        } else {
            // ESP32-S3 12-bit ADC (0 - 4095), ~1.65V mid-scale center
            // Body surface mV with ~100x AD8232 front-end gain:
            sample_mv = (((float)raw_adc - 2048.0f) * (3300.0f / 4095.0f)) / 100.0f;
        }

        ecg_ring_buffer_push(&g_ring_buf, sample_mv);
        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
}

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("===========================================================================");
    Serial.println("CardioSentinel Edge: Low-Power Quality-Aware ECG Screening on ESP32-S3");
    Serial.println("TECHgium Challenge 26 | Sensor: AD8232 (Lead II)");
    Serial.println("===========================================================================");

    // Pin configuration
    pinMode(PIN_LO_PLUS, INPUT_PULLDOWN);
    pinMode(PIN_LO_MINUS, INPUT_PULLDOWN);
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);

    // Initialize algorithm modules
    ecg_ring_buffer_init(&g_ring_buf);
    asqi_init();
    mig_init();
    tinycnn_inference_init();
    decision_engine_init();

    // Start 250 Hz acquisition task on Core 0
    xTaskCreatePinnedToCore(
        sampleTask,
        "sample_task",
        4096,
        NULL,
        24,
        &s_sample_task_handle,
        0
    );

    Serial.println("[SYSTEM] Core 0 250 Hz Acquisition Initialized. Buffering initial 10s...");
}

void loop() {
    // Check if 10.0-second window (2500 samples) is ready
    if (ecg_ring_buffer_is_window_ready(&g_ring_buf)) {
        unsigned long t_start = micros();

        // 1. Snapshot active 10s raw window
        ecg_ring_buffer_get_window(&g_ring_buf, g_window_raw, ECG_WINDOW_SAMPLES);

        // 2. Dual-stream: produce candidate-filtered window
        apply_conservative_filter(g_window_raw, g_window_filtered, ECG_WINDOW_SAMPLES);

        // 3. Stage A: Adaptive Signal Quality Intelligence (ASQI)
        asqi_result_t asqi_res = asqi_evaluate_window(g_window_raw, ECG_WINDOW_SAMPLES, 250.0f);

        // 4. Stage B: Morphology Integrity Guard (MIG)
        mig_result_t mig_res = mig_evaluate_window(g_window_raw, g_window_filtered, ECG_WINDOW_SAMPLES, 250.0f);

        // 5. Stage C: TinyCNN 1D-CNN Inference (<35ms on FPU)
        inference_result_t infer_res = tinycnn_predict(g_window_filtered, ECG_WINDOW_SAMPLES);

        // 6. Stage D: Calibrated 3-Zone Triage
        screening_event_t event = evaluate_screening_decision(
            &asqi_res,
            &mig_res,
            &infer_res,
            ecg_ring_buffer_get_dropped(&g_ring_buf),
            s_seq_id++
        );

        unsigned long t_elapsed = micros() - t_start;
        uint32_t bpm = mig_res.filt_peak_count * 6; // 10s window * 6 = BPM

        // Print Telemetry JSON to Serial (115200 baud)
        char json_buf[512];
        format_telemetry_json(&event, &infer_res, json_buf, sizeof(json_buf));

        Serial.printf("[TELEMETRY] %s\n", json_buf);
        Serial.printf("[SUMMARY] Seq: %lu | Zone: %s | AI: %s (%.1f%%) | ASQI: %.2f | MIG: %s | HR: %lu BPM | Burst: %lu us\n",
            (unsigned long)event.window_seq_id,
            event.decision_str,
            event.classification_str,
            event.confidence * 100.0f,
            asqi_res.quality_score,
            mig_res.passed ? "PASS" : "DISTORTION",
            (unsigned long)bpm,
            t_elapsed
        );

        // Advance sliding window by 2.5s stride (625 samples)
        ecg_ring_buffer_advance_stride(&g_ring_buf, ECG_STRIDE_SAMPLES);
    }

    delay(50); // Polling delay
}
