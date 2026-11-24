/**
 * CardioSentinel Edge - Embedded TinyCNN Inference Engine
 * TECHgium Challenge 26 Research Prototype
 * Target: ESP32-S3 Internal SRAM (Execution burst: ~80-110 ms @ 240 MHz)
 */

#ifndef INFERENCE_H
#define INFERENCE_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#define RHYTHM_CLASS_NORMAL 0
#define RHYTHM_CLASS_AF     1
#define RHYTHM_CLASS_OTHER  2

typedef struct {
    float logits[3];
    float probabilities[3]; // Temperature-calibrated softmax
    uint8_t top_class_id;
    float top_confidence;
    float margin;           // top1_prob - top2_prob
} inference_result_t;

void tinycnn_inference_init(void);
inference_result_t tinycnn_predict(const float *ecg_window, size_t num_samples);

#endif // INFERENCE_H
