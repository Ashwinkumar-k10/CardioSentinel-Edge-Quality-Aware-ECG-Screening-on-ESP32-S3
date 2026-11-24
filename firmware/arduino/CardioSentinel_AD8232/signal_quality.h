/**
 * CardioSentinel Edge - Embedded Signal Quality Intelligence (ASQI)
 * TECHgium Challenge 26 Research Prototype
 * Bounded O(N) Complexity: Execution time < 12 ms on ESP32-S3 @ 240 MHz
 */

#ifndef SIGNAL_QUALITY_H
#define SIGNAL_QUALITY_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

// Reason Flags (Bitmask)
#define ASQI_FLAG_OK                0x0000
#define ASQI_FLAG_LEAD_OFF          0x0001
#define ASQI_FLAG_RAIL_SATURATION   0x0002
#define ASQI_FLAG_EXCESSIVE_DRIFT   0x0004
#define ASQI_FLAG_MUSCLE_NOISE_EMG  0x0008
#define ASQI_FLAG_LOW_AMPLITUDE     0x0010
#define ASQI_FLAG_HIGH_ZERO_CROSS   0x0020

typedef struct {
    float quality_score;     // 0.0f to 1.0f
    bool usable;             // true if adequate for screening
    uint16_t flags;          // Bitmask of quality flags
    float peak_to_peak;
    float variance;
    float drift_span;
    float line_length_norm;
    float zero_cross_rate;
} asqi_result_t;

void asqi_init(void);
asqi_result_t asqi_evaluate_window(const float *ecg_window, size_t num_samples, float fs);

#endif // SIGNAL_QUALITY_H
