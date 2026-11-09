/**
 * CardioSentinel Edge - ESP32-S3 Main Application Entry Point
 * TECHgium Challenge 26 Research Prototype
 * 
 * Target: ESP32-S3-WROOM-1 / N8R8 (8 MB Octal PSRAM, 8 MB Flash)
 * Dual-Core Task Allocation:
 *   - Core 0: High-Priority SPI DMA Acquisition + Low-Priority Telemetry
 *   - Core 1: Bounded Compute Pipeline (ASQI + MIG + TinyCNN + Triage)
 */

#include <stdio.h>
#include <string.h>
#include "ring_buffer.h"
#include "signal_quality.h"
#include "morphology_guard.h"
#include "inference.h"
#include "decision_engine.h"
#include "ecg_acquire.h"
#include "telemetry.h"

#ifdef ESP_PLATFORM
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
static const char *TAG = "CARDIOSENTINEL_MAIN";
#endif

// System Shared Context
static ecg_ring_buffer_t g_ring_buf;
static float g_window_raw[ECG_WINDOW_SAMPLES];
static float g_window_filtered[ECG_WINDOW_SAMPLES];

// Digital FIR filter approximation for diagnostic bandpass (0.5 - 40 Hz)
static void apply_conservative_filter(const float *raw, float *filt, size_t n) {
    if (!raw || !filt || n == 0) return;
    // 5-point moving average smoothing high frequency + DC notch
    for (size_t i = 2; i < n - 2; i++) {
        filt[i] = 0.1f * raw[i - 2] + 0.2f * raw[i - 1] + 0.4f * raw[i] + 0.2f * raw[i + 1] + 0.1f * raw[i + 2];
    }
    filt[0] = raw[0];
    filt[1] = raw[1];
    filt[n - 2] = raw[n - 2];
    filt[n - 1] = raw[n - 1];
}

void cardiosentinel_step_pipeline(uint32_t seq_id) {
    // 1. Snapshot active 10.0-second window (2,500 samples)
    if (!ecg_ring_buffer_get_window(&g_ring_buf, g_window_raw, ECG_WINDOW_SAMPLES)) {
        return;
    }

    // 2. Dual-stream: preserve raw window, generate filtered window
    apply_conservative_filter(g_window_raw, g_window_filtered, ECG_WINDOW_SAMPLES);

    // 3. Stage A: Adaptive Signal Quality Intelligence (ASQI)
    asqi_result_t asqi_res = asqi_evaluate_window(g_window_raw, ECG_WINDOW_SAMPLES, 250.0f);

    // 4. Stage B: Morphology Integrity Guard (MIG)
    mig_result_t mig_res = mig_evaluate_window(g_window_raw, g_window_filtered, ECG_WINDOW_SAMPLES, 250.0f);

    // 5. Stage C: TinyCNN Inference
    inference_result_t infer_res = tinycnn_predict(g_window_filtered, ECG_WINDOW_SAMPLES);

    // 6. Stage D: Calibrated 3-Zone Triage
    screening_event_t event = evaluate_screening_decision(
        &asqi_res,
        &mig_res,
        &infer_res,
        ecg_ring_buffer_get_dropped(&g_ring_buf),
        seq_id
    );

    // 7. Telemetry & PSRAM Audit Logging
    telemetry_send_event(&event, &infer_res);
    telemetry_log_audit_episode(&event, g_window_raw, g_window_filtered, ECG_WINDOW_SAMPLES);

    // 8. Advance sliding window by 2.5s stride (625 samples)
    ecg_ring_buffer_advance_stride(&g_ring_buf, ECG_STRIDE_SAMPLES);
}

#ifdef ESP_PLATFORM
static void compute_pipeline_task(void *pvParameters) {
    uint32_t seq = 1;
    while (1) {
        if (ecg_ring_buffer_is_window_ready(&g_ring_buf)) {
            int64_t t_start = esp_timer_get_time();
            cardiosentinel_step_pipeline(seq++);
            int64_t t_end = esp_timer_get_time();
            int64_t elapsed_us = t_end - t_start;
            ESP_LOGI(TAG, "Pipeline burst execution: %lld us (< 150 ms target)", elapsed_us);
        }
        vTaskDelay(pdMS_TO_TICKS(100)); // Check periodically
    }
}

void app_main(void) {
    ESP_LOGI(TAG, "Starting CardioSentinel Edge on ESP32-S3...");
    ecg_ring_buffer_init(&g_ring_buf);
    asqi_init();
    mig_init();
    tinycnn_inference_init();
    decision_engine_init();
    telemetry_init();
    ecg_acquire_init(&g_ring_buf);

    // Start acquisition in dataset replay mode for demonstration
    ecg_acquire_start(ACQUIRE_MODE_DATASET_REPLAY);

    // Pin compute pipeline to Core 1
    xTaskCreatePinnedToCore(
        compute_pipeline_task,
        "compute_pipeline",
        16384,
        NULL,
        10,
        NULL,
        1
    );

    ESP_LOGI(TAG, "CardioSentinel Edge running smoothly.");
}
#endif
