/**
 * CardioSentinel Edge - Embedded Morphology Integrity Guard (MIG) Implementation
 */

#include "morphology_guard.h"
#include <math.h>
#include <string.h>

void mig_init(void) {
    // Static O(1) state
}

static size_t detect_peaks_internal(
    const float *x,
    size_t n,
    float fs,
    uint16_t *out_peaks,
    size_t max_peaks
) {
    if (n < 20 || !out_peaks || max_peaks == 0) return 0;

    size_t k_len = (size_t)(0.08f * fs);
    if (k_len < 3) k_len = 3;

    // Moving integration of squared derivative
    double energy_sum = 0.0;
    double energy_sq_sum = 0.0;
    size_t count = 0;

    // First pass: compute threshold
    for (size_t i = 1; i < n; i++) {
        float d = x[i] - x[i - 1];
        float sq = d * d;
        energy_sum += sq;
        energy_sq_sum += sq * sq;
        count++;
    }

    double mean_e = energy_sum / count;
    double var_e = (energy_sq_sum / count) - (mean_e * mean_e);
    double std_e = (var_e > 0.0) ? sqrt(var_e) : 0.0;
    float thresh = (float)(mean_e + 0.35 * std_e);

    size_t min_dist = (size_t)(0.25f * fs); // 250 ms refractory period
    size_t n_peaks = 0;
    size_t last_peak = 0;

    for (size_t i = 1; i < n - 1; i++) {
        float d = x[i] - x[i - 1];
        float sq = d * d;
        if (sq > thresh) {
            // Local peak search in raw signal around this energy point
            size_t w_start = (i > k_len) ? i - k_len : 0;
            size_t w_end = (i + 2 * k_len < n) ? i + 2 * k_len : n;

            float max_val = x[w_start];
            size_t best_idx = w_start;
            for (size_t j = w_start + 1; j < w_end; j++) {
                if (x[j] > max_val) {
                    max_val = x[j];
                    best_idx = j;
                }
            }

            if (n_peaks == 0 || (best_idx - last_peak) >= min_dist) {
                out_peaks[n_peaks++] = (uint16_t)best_idx;
                last_peak = best_idx;
                if (n_peaks >= max_peaks) break;
            }
            i += min_dist;
        }
    }

    return n_peaks;
}

mig_result_t mig_evaluate_window(
    const float *raw,
    const float *filt,
    size_t n,
    float fs
) {
    mig_result_t res;
    res.passed = true;
    res.flags = MIG_STATUS_PASSED;
    res.max_shift_ms = 0.0f;
    res.max_attenuation = 0.0f;
    res.envelope_rmse = 0.0f;
    res.raw_peak_count = 0;
    res.filt_peak_count = 0;

    if (!raw || !filt || n == 0) return res;

    uint16_t raw_peaks[MIG_MAX_PEAKS];
    uint16_t filt_peaks[MIG_MAX_PEAKS];

    size_t n_raw = detect_peaks_internal(raw, n, fs, raw_peaks, MIG_MAX_PEAKS);
    size_t n_filt = detect_peaks_internal(filt, n, fs, filt_peaks, MIG_MAX_PEAKS);

    res.raw_peak_count = (uint16_t)n_raw;
    res.filt_peak_count = (uint16_t)n_filt;

    if (n_raw == 0) return res;

    // 1. Beat count mismatch check
    int diff_beats = (int)n_raw - (int)n_filt;
    if (diff_beats < 0) diff_beats = -diff_beats;
    int max_allowed_diff = (int)(0.25f * n_raw);
    if (max_allowed_diff < 2) max_allowed_diff = 2;

    if (diff_beats > max_allowed_diff) {
        res.flags |= MIG_STATUS_BEAT_MISMATCH;
    }

    // 2. Peak matching for shift and attenuation
    int window_radius = (int)(0.05f * fs); // 50 ms window
    int max_shift_samp = 0;
    float max_att = 0.0f;

    for (size_t i = 0; i < n_raw; i++) {
        uint16_t rp = raw_peaks[i];
        int best_dist = 999999;
        int matched_idx = -1;

        for (size_t j = 0; j < n_filt; j++) {
            int d = (int)filt_peaks[j] - (int)rp;
            if (d < 0) d = -d;
            if (d <= window_radius && d < best_dist) {
                best_dist = d;
                matched_idx = (int)filt_peaks[j];
            }
        }

        if (matched_idx >= 0) {
            if (best_dist > max_shift_samp) max_shift_samp = best_dist;

            float r_amp = fabsf(raw[rp]);
            float f_amp = fabsf(filt[matched_idx]);
            if (r_amp > 1e-4f) {
                float att = (r_amp - f_amp) / r_amp;
                if (att > max_att) max_att = att;
            }
        }
    }

    res.max_shift_ms = ((float)max_shift_samp / fs) * 1000.0f;
    res.max_attenuation = max_att;

    if (res.max_shift_ms > 16.0f) {
        res.flags |= MIG_STATUS_R_PEAK_SHIFT;
    }
    if (res.max_attenuation > 0.38f) {
        res.flags |= MIG_STATUS_PEAK_ATTENUATION;
    }

    // 3. Envelope RMSE
    double mean_raw = 0.0, mean_filt = 0.0;
    for (size_t i = 0; i < n; i++) {
        mean_raw += raw[i];
        mean_filt += filt[i];
    }
    mean_raw /= n;
    mean_filt /= n;

    double var_raw = 0.0, var_filt = 0.0;
    for (size_t i = 0; i < n; i++) {
        double dr = raw[i] - mean_raw;
        double df = filt[i] - mean_filt;
        var_raw += dr * dr;
        var_filt += df * df;
    }
    float std_r = (float)sqrt((var_raw / n) + 1e-6);
    float std_f = (float)sqrt((var_filt / n) + 1e-6);

    double rmse_sum = 0.0;
    for (size_t i = 0; i < n; i++) {
        float nr = (float)((raw[i] - mean_raw) / std_r);
        float nf = (float)((filt[i] - mean_filt) / std_f);
        float err = nr - nf;
        rmse_sum += err * err;
    }
    res.envelope_rmse = (float)sqrt(rmse_sum / n);

    if (res.envelope_rmse > 0.45f) {
        res.flags |= MIG_STATUS_ENVELOPE_DISTORTION;
    }

    res.passed = (res.flags == MIG_STATUS_PASSED);
    return res;
}
