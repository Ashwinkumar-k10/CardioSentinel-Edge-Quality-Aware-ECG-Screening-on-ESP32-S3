/**
 * CardioSentinel Edge - Calibrated 3-Zone Triage & Decision Engine
 * TECHgium Challenge 26 Research Prototype
 */

#ifndef DECISION_ENGINE_H
#define DECISION_ENGINE_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "signal_quality.h"
#include "morphology_guard.h"
#include "inference.h"

typedef enum {
    DECISION_ZONE_ACCEPT = 0,
    DECISION_ZONE_REVIEW = 1,
    DECISION_ZONE_ABSTAIN = 2
} decision_zone_t;

typedef struct {
    decision_zone_t zone;
    char decision_str[16];      // "ACCEPT", "REVIEW", "ABSTAIN"
    char classification_str[24];// "Normal", "AF", "Other", "UNINTERPRETABLE"
    float confidence;
    uint16_t asqi_flags;
    uint16_t mig_flags;
    bool quality_usable;
    bool mig_passed;
    uint32_t dropped_samples;
    uint32_t window_seq_id;
} screening_event_t;

void decision_engine_init(void);

screening_event_t evaluate_screening_decision(
    const asqi_result_t *asqi,
    const mig_result_t *mig,
    const inference_result_t *infer,
    uint32_t dropped_samples,
    uint32_t window_seq_id
);

// Formats the event into standard CardioSentinel JSON telemetry
size_t format_telemetry_json(
    const screening_event_t *ev,
    const inference_result_t *infer,
    char *out_buffer,
    size_t max_len
);

#endif // DECISION_ENGINE_H
