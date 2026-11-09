/**
 * CardioSentinel Edge - Embedded Signal Quality Intelligence (ASQI) Implementation
 */

#include "signal_quality.h"
#include <math.h>

void asqi_init(void) {
    // No dynamic allocation needed; O(1) state
}

asqi_result_t asqi_evaluate_window(const float *x, size_t n, float fs) {
    asqi_result_t res;
    res.quality_score = 1.0f;
    res.usable = true;
    res.flags = ASQI_FLAG_OK;
    res.peak_to_peak = 0.0f;
    res.variance = 0.0f;
    res.drift_span = 0.0f;
    res.line_length_norm = 0.0f;
    res.zero_cross_rate = 0.0f;

    if (!x || n == 0) {
        res.quality_score = 0.0f;
        res.usable = false;
        res.flags = ASQI_FLAG_LEAD_OFF;
        return res;
    }

    // 1. Single-pass linear scan for min, max, mean
    float v_min = x[0];
    float v_max = x[0];
    double sum = 0.0;

    for (size_t i = 0; i < n; i++) {
        float val = x[i];
        if (val < v_min) v_min = val;
        if (val > v_max) v_max = val;
        sum += val;
    }

    float mean = (float)(sum / n);
    res.peak_to_peak = v_max - v_min;

    // 2. Second pass: Variance, line length, flat-top clipping
    double var_sum = 0.0;
    double line_len_sum = 0.0;
    uint32_t flat_at_pos_peak = 0;
    uint32_t flat_at_neg_peak = 0;
    uint32_t zero_crossings = 0;

    float pos_thresh = 0.85f * v_max;
    float neg_thresh = 0.85f * v_min;

    for (size_t i = 0; i < n; i++) {
        float diff_mean = x[i] - mean;
        var_sum += (diff_mean * diff_mean);

        if (i > 0) {
            float d = fabsf(x[i] - x[i - 1]);
            line_len_sum += d;

            if (d < 1e-4f) {
                if (x[i - 1] > pos_thresh) flat_at_pos_peak++;
                if (x[i - 1] < neg_thresh) flat_at_neg_peak++;
            }

            // Zero crossing around mean
            if ((x[i - 1] - mean) * diff_mean < 0.0f) {
                zero_crossings++;
            }
        }
    }

    res.variance = (float)(var_sum / n);
    res.zero_cross_rate = (float)zero_crossings / (float)n;

    float denom = (res.peak_to_peak > 0.1f) ? res.peak_to_peak : 0.1f;
    res.line_length_norm = (float)(line_len_sum / (n * denom));

    // 3. Lead-off detection (Flatline)
    if (res.variance < 0.0005f || res.peak_to_peak < 0.03f) {
        res.flags |= ASQI_FLAG_LEAD_OFF;
        res.quality_score = 0.0f;
        res.usable = false;
        return res;
    }

    // 4. Rail saturation
    bool is_rail = (flat_at_pos_peak + flat_at_neg_peak > 15) || (v_max >= 3.0f) || (v_min <= -3.0f);
    if (is_rail) {
        res.flags |= ASQI_FLAG_RAIL_SATURATION;
        res.quality_score -= 0.60f;
    }

    // 5. Baseline Drift (1-second moving average span)
    size_t k = (size_t)fs;
    if (k > 0 && n >= k) {
        double block_sum = 0.0;
        for (size_t i = 0; i < k; i++) {
            block_sum += x[i];
        }
        float min_block = (float)(block_sum / k);
        float max_block = min_block;

        for (size_t i = k; i < n; i++) {
            block_sum += x[i] - x[i - k];
            float curr_block = (float)(block_sum / k);
            if (curr_block < min_block) min_block = curr_block;
            if (curr_block > max_block) max_block = curr_block;
        }
        res.drift_span = max_block - min_block;
    }

    if (res.drift_span > 0.8f) {
        res.flags |= ASQI_FLAG_EXCESSIVE_DRIFT;
        float factor = res.drift_span / 0.8f;
        if (factor > 2.0f) factor = 2.0f;
        res.quality_score -= 0.25f * factor;
    }

    // 6. Muscle noise (EMG)
    if (res.line_length_norm > 0.12f) {
        res.flags |= ASQI_FLAG_MUSCLE_NOISE_EMG;
        float factor = res.line_length_norm / 0.12f;
        if (factor > 2.0f) factor = 2.0f;
        res.quality_score -= 0.35f * factor;
    }

    // 7. High zero crossing
    if (res.zero_cross_rate > 0.35f) {
        res.flags |= ASQI_FLAG_HIGH_ZERO_CROSS;
        res.quality_score -= 0.20f;
    }

    // Clip score [0.0, 1.0]
    if (res.quality_score < 0.0f) res.quality_score = 0.0f;
    if (res.quality_score > 1.0f) res.quality_score = 1.0f;

    res.usable = (res.quality_score >= 0.55f) && !(res.flags & (ASQI_FLAG_LEAD_OFF | ASQI_FLAG_RAIL_SATURATION));
    return res;
}
