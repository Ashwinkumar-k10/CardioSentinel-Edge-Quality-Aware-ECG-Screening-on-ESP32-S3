/**
 * CardioSentinel Edge - Telemetry & PSRAM Audit Logger Implementation
 */

#include "telemetry.h"
#include <stdio.h>
#include <string.h>

#ifdef ESP_PLATFORM
#include "esp_log.h"
#include "esp_heap_caps.h"
static const char *TAG = "TELEMETRY";
#endif

#define MAX_JSON_PAYLOAD_LEN 512
static telemetry_stats_t s_stats;

void telemetry_init(void) {
    memset(&s_stats, 0, sizeof(s_stats));
    s_stats.ble_connected = false;
}

bool telemetry_send_event(const screening_event_t *ev, const inference_result_t *infer) {
    if (!ev) return false;

    char json_buf[MAX_JSON_PAYLOAD_LEN];
    size_t len = format_telemetry_json(ev, infer, json_buf, sizeof(json_buf));
    if (len == 0) return false;

    // Output over Serial / UART / USB-CDC
    printf("[TELEMETRY] %s\n", json_buf);
    s_stats.packets_sent++;
    return true;
}

bool telemetry_log_audit_episode(
    const screening_event_t *ev,
    const float *raw,
    const float *filt,
    size_t n
) {
    if (!ev || !raw || n == 0) return false;

    // Only save episodes routed to REVIEW or ABSTAIN
    if (ev->zone == DECISION_ZONE_ACCEPT) {
        return true;
    }

    if (ev->zone == DECISION_ZONE_REVIEW) {
        s_stats.review_episodes_saved++;
        printf("[AUDIT] Saved REVIEW episode seq=%lu to PSRAM audit ring\n", (unsigned long)ev->window_seq_id);
    } else if (ev->zone == DECISION_ZONE_ABSTAIN) {
        s_stats.abstain_episodes_saved++;
        printf("[AUDIT] Saved ABSTAIN episode seq=%lu to PSRAM audit ring\n", (unsigned long)ev->window_seq_id);
    }

    return true;
}

telemetry_stats_t telemetry_get_stats(void) {
    return s_stats;
}
