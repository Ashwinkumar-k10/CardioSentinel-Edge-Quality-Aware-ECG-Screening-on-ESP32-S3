/**
 * CardioSentinel Edge - Embedded Morphology Integrity Guard (MIG)
 * TECHgium Challenge 26 Research Prototype
 * Execution time: < 20 ms on ESP32-S3 @ 240 MHz
 */

#ifndef MORPHOLOGY_GUARD_H
#define MORPHOLOGY_GUARD_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#define MIG_STATUS_PASSED               0x0000
#define MIG_STATUS_R_PEAK_SHIFT         0x0001
#define MIG_STATUS_PEAK_ATTENUATION     0x0002
#define MIG_STATUS_ENVELOPE_DISTORTION  0x0004
#define MIG_STATUS_BEAT_MISMATCH        0x0008

#define MIG_MAX_PEAKS                   64

typedef struct {
    bool passed;
    uint16_t flags;
    float max_shift_ms;
    float max_attenuation;
    float envelope_rmse;
    uint16_t raw_peak_count;
    uint16_t filt_peak_count;
} mig_result_t;

void mig_init(void);
mig_result_t mig_evaluate_window(
    const float *raw_ecg,
    const float *filtered_ecg,
    size_t num_samples,
    float fs
);

#endif // MORPHOLOGY_GUARD_H
