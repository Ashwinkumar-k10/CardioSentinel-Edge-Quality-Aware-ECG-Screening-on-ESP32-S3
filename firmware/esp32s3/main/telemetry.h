/**
 * CardioSentinel Edge - Telemetry & PSRAM Audit Logger
 * TECHgium Challenge 26 Research Prototype
 * Target: ESP32-S3 Core 0 (Priority 5 Low-Latency Telemetry)
 */

#ifndef TELEMETRY_H
#define TELEMETRY_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "decision_engine.h"

typedef struct {
    uint32_t packets_sent;
    uint32_t review_episodes_saved;
    uint32_t abstain_episodes_saved;
    bool ble_connected;
} telemetry_stats_t;

void telemetry_init(void);
bool telemetry_send_event(const screening_event_t *ev, const inference_result_t *infer);
bool telemetry_log_audit_episode(
    const screening_event_t *ev,
    const float *raw_window,
    const float *filtered_window,
    size_t num_samples
);
telemetry_stats_t telemetry_get_stats(void);

#endif // TELEMETRY_H
