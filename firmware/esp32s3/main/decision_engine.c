/**
 * CardioSentinel Edge - Decision Engine Implementation
 */

#include "decision_engine.h"
#include <stdio.h>
#include <string.h>

void decision_engine_init(void) {
    // Static O(1) state
}

screening_event_t evaluate_screening_decision(
    const asqi_result_t *asqi,
    const mig_result_t *mig,
    const inference_result_t *infer,
    uint32_t dropped_samples,
    uint32_t window_seq_id
) {
    screening_event_t ev;
    memset(&ev, 0, sizeof(ev));
    ev.window_seq_id = window_seq_id;
    ev.dropped_samples = dropped_samples;
    ev.asqi_flags = asqi ? asqi->flags : ASQI_FLAG_LEAD_OFF;
    ev.mig_flags = mig ? mig->flags : MIG_STATUS_BEAT_MISMATCH;
    ev.quality_usable = asqi ? asqi->usable : false;
    ev.mig_passed = mig ? mig->passed : false;

    // Class string lookup
    static const char *CLASS_NAMES[] = {"Normal", "AF", "Other"};

    // 1. Hardware / Physical Invalidity -> Strict ABSTAIN
    if (!ev.quality_usable || (ev.asqi_flags & (ASQI_FLAG_LEAD_OFF | ASQI_FLAG_RAIL_SATURATION))) {
        ev.zone = DECISION_ZONE_ABSTAIN;
        snprintf(ev.decision_str, sizeof(ev.decision_str), "ABSTAIN");
        snprintf(ev.classification_str, sizeof(ev.classification_str), "UNINTERPRETABLE");
        ev.confidence = 0.0f;
        return ev;
    }

    // 2. Morphology Integrity Guard Violation -> Forced REVIEW
    if (!ev.mig_passed) {
        ev.zone = DECISION_ZONE_REVIEW;
        snprintf(ev.decision_str, sizeof(ev.decision_str), "REVIEW");
        if (infer && infer->top_class_id < 3) {
            snprintf(ev.classification_str, sizeof(ev.classification_str), "FLAGGED_%s", CLASS_NAMES[infer->top_class_id]);
            ev.confidence = infer->top_confidence;
        } else {
            snprintf(ev.classification_str, sizeof(ev.classification_str), "FLAGGED_BEAT");
            ev.confidence = 0.0f;
        }
        return ev;
    }

    // 3. Ambiguous Model Confidence or Margin -> REVIEW
    if (!infer || infer->top_confidence < 0.68f || infer->margin < 0.15f) {
        ev.zone = DECISION_ZONE_REVIEW;
        snprintf(ev.decision_str, sizeof(ev.decision_str), "REVIEW");
        if (infer && infer->top_class_id < 3) {
            snprintf(ev.classification_str, sizeof(ev.classification_str), "AMBIGUOUS_%s", CLASS_NAMES[infer->top_class_id]);
            ev.confidence = infer->top_confidence;
        } else {
            snprintf(ev.classification_str, sizeof(ev.classification_str), "AMBIGUOUS");
            ev.confidence = 0.0f;
        }
        return ev;
    }

    // 4. Calibrated High Confidence & Quality -> ACCEPT
    ev.zone = DECISION_ZONE_ACCEPT;
    snprintf(ev.decision_str, sizeof(ev.decision_str), "ACCEPT");
    snprintf(ev.classification_str, sizeof(ev.classification_str), "%s", CLASS_NAMES[infer->top_class_id]);
    ev.confidence = infer->top_confidence;
    return ev;
}

size_t format_telemetry_json(
    const screening_event_t *ev,
    const inference_result_t *infer,
    char *buf,
    size_t max_len
) {
    if (!ev || !buf || max_len == 0) return 0;

    float p_norm = infer ? infer->probabilities[0] : 0.0f;
    float p_af   = infer ? infer->probabilities[1] : 0.0f;
    float p_oth  = infer ? infer->probabilities[2] : 0.0f;

    int written = snprintf(buf, max_len,
        "{\"seq\":%lu,\"device\":\"cardiosentinel_s3\",\"decision\":\"%s\","
        "\"class\":\"%s\",\"conf\":%.3f,\"quality\":{\"usable\":%s,\"flags\":%u},"
        "\"mig\":{\"passed\":%s,\"flags\":%u},"
        "\"probs\":[%.3f,%.3f,%.3f],\"dropped\":%lu}",
        (unsigned long)ev->window_seq_id,
        ev->decision_str,
        ev->classification_str,
        ev->confidence,
        ev->quality_usable ? "true" : "false",
        ev->asqi_flags,
        ev->mig_passed ? "true" : "false",
        ev->mig_flags,
        p_norm, p_af, p_oth,
        (unsigned long)ev->dropped_samples
    );

    return (written > 0 && (size_t)written < max_len) ? (size_t)written : 0;
}
