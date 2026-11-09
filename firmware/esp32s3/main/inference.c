/**
 * CardioSentinel Edge - Embedded TinyCNN Inference Engine Implementation
 */

#include "inference.h"
#include "../models/tinycnn_weights.h"
#include <math.h>
#include <string.h>

// Static internal working buffers (Internal Zero-Wait SRAM)
// Conv1 out: [16, 1250] -> Pool1 out: [16, 625] = 10,000 floats = 40 KB
static float buf_conv1[CONV1_OUT_CHANNELS * 625];
// Conv2 out: [32, 313] -> Pool2 out: [32, 156] = 4,992 floats = ~20 KB
static float buf_conv2[CONV2_OUT_CHANNELS * 156];
// Conv3 out: [48, 78] = 3,744 floats = ~15 KB
static float buf_conv3[CONV3_OUT_CHANNELS * 78];

void tinycnn_inference_init(void) {
    // Zero-initialization of working memory
    memset(buf_conv1, 0, sizeof(buf_conv1));
    memset(buf_conv2, 0, sizeof(buf_conv2));
    memset(buf_conv3, 0, sizeof(buf_conv3));
}

inference_result_t tinycnn_predict(const float *x, size_t n) {
    inference_result_t res;
    memset(&res, 0, sizeof(res));
    if (!x || n < INPUT_LENGTH) return res;

    // 0. Normalize input window to zero-mean, unit-variance
    double sum = 0.0, sq_sum = 0.0;
    for (size_t i = 0; i < INPUT_LENGTH; i++) {
        sum += x[i];
        sq_sum += (double)x[i] * x[i];
    }
    float mean = (float)(sum / INPUT_LENGTH);
    float var = (float)((sq_sum / INPUT_LENGTH) - (mean * mean));
    float inv_std = 1.0f / (sqrtf(var > 0.0f ? var : 1e-6f) + 1e-6f);

    // =========================================================================
    // Block 1: Conv1D (k=7, s=2, pad=3) -> ReLU -> MaxPool (k=2, s=2)
    // Input: [1, 2500] -> Conv: [16, 1250] -> Pool: [16, 625]
    // =========================================================================
    const int conv1_out_len = 1250;
    const int pool1_out_len = 625;

    for (int oc = 0; oc < CONV1_OUT_CHANNELS; oc++) {
        const float *w_oc = &TINYCNN_CONV1_W[oc * CONV1_KERNEL_SIZE];
        float b = TINYCNN_CONV1_B[oc];

        for (int p = 0; p < pool1_out_len; p++) {
            // Fused Conv + ReLU + MaxPool(2,2): evaluate two consecutive conv outputs
            float m_val = 0.0f; // ReLU lower bound

            for (int sub = 0; sub < 2; sub++) {
                int conv_idx = p * 2 + sub;
                float acc = b;
                int start_in = conv_idx * CONV1_STRIDE - CONV1_PAD;

                for (int k = 0; k < CONV1_KERNEL_SIZE; k++) {
                    int in_idx = start_in + k;
                    float val = 0.0f;
                    if (in_idx >= 0 && in_idx < INPUT_LENGTH) {
                        val = (x[in_idx] - mean) * inv_std;
                    }
                    acc += val * w_oc[k];
                }

                if (acc > m_val) m_val = acc; // ReLU and MaxPool
            }
            buf_conv1[oc * pool1_out_len + p] = m_val;
        }
    }

    // =========================================================================
    // Block 2: Conv1D (k=5, s=2, pad=2) -> ReLU -> MaxPool (k=2, s=2)
    // Input: [16, 625] -> Conv: [32, 313] -> Pool: [32, 156]
    // =========================================================================
    const int pool2_out_len = 156;

    for (int oc = 0; oc < CONV2_OUT_CHANNELS; oc++) {
        const float *w_oc = &TINYCNN_CONV2_W[oc * CONV1_OUT_CHANNELS * CONV2_KERNEL_SIZE];
        float b = TINYCNN_CONV2_B[oc];

        for (int p = 0; p < pool2_out_len; p++) {
            float m_val = 0.0f;

            for (int sub = 0; sub < 2; sub++) {
                int conv_idx = p * 2 + sub;
                float acc = b;
                int start_in = conv_idx * CONV2_STRIDE - CONV2_PAD;

                for (int ic = 0; ic < CONV1_OUT_CHANNELS; ic++) {
                    const float *w_ic = &w_oc[ic * CONV2_KERNEL_SIZE];
                    const float *in_ic = &buf_conv1[ic * pool1_out_len];

                    for (int k = 0; k < CONV2_KERNEL_SIZE; k++) {
                        int in_idx = start_in + k;
                        if (in_idx >= 0 && in_idx < pool1_out_len) {
                            acc += in_ic[in_idx] * w_ic[k];
                        }
                    }
                }

                if (acc > m_val) m_val = acc;
            }
            buf_conv2[oc * pool2_out_len + p] = m_val;
        }
    }

    // =========================================================================
    // Block 3: Conv1D (k=3, s=2, pad=1) -> ReLU
    // Input: [32, 156] -> Conv: [48, 78]
    // =========================================================================
    const int conv3_out_len = 78;

    for (int oc = 0; oc < CONV3_OUT_CHANNELS; oc++) {
        const float *w_oc = &TINYCNN_CONV3_W[oc * CONV2_OUT_CHANNELS * CONV3_KERNEL_SIZE];
        float b = TINYCNN_CONV3_B[oc];

        for (int i = 0; i < conv3_out_len; i++) {
            float acc = b;
            int start_in = i * CONV3_STRIDE - CONV3_PAD;

            for (int ic = 0; ic < CONV2_OUT_CHANNELS; ic++) {
                const float *w_ic = &w_oc[ic * CONV3_KERNEL_SIZE];
                const float *in_ic = &buf_conv2[ic * pool2_out_len];

                for (int k = 0; k < CONV3_KERNEL_SIZE; k++) {
                    int in_idx = start_in + k;
                    if (in_idx >= 0 && in_idx < pool2_out_len) {
                        acc += in_ic[in_idx] * w_ic[k];
                    }
                }
            }

            // ReLU
            buf_conv3[oc * conv3_out_len + i] = (acc > 0.0f) ? acc : 0.0f;
        }
    }

    // =========================================================================
    // Global Average Pooling: [48, 78] -> [48]
    // =========================================================================
    float gap[CONV3_OUT_CHANNELS];
    for (int oc = 0; oc < CONV3_OUT_CHANNELS; oc++) {
        const float *channel_ptr = &buf_conv3[oc * conv3_out_len];
        float ch_sum = 0.0f;
        for (int i = 0; i < conv3_out_len; i++) {
            ch_sum += channel_ptr[i];
        }
        gap[oc] = ch_sum / conv3_out_len;
    }

    // =========================================================================
    // Dense Head: FC1 [48] -> [24] + ReLU
    // =========================================================================
    float fc1_out[FC1_OUT_FEATURES];
    for (int o = 0; o < FC1_OUT_FEATURES; o++) {
        float acc = TINYCNN_FC1_B[o];
        const float *w_o = &TINYCNN_FC1_W[o * FC1_IN_FEATURES];
        for (int i = 0; i < FC1_IN_FEATURES; i++) {
            acc += gap[i] * w_o[i];
        }
        fc1_out[o] = (acc > 0.0f) ? acc : 0.0f; // ReLU
    }

    // =========================================================================
    // Dense Head: FC2 [24] -> [3] Logits
    // =========================================================================
    for (int o = 0; o < NUM_CLASSES; o++) {
        float acc = TINYCNN_FC2_B[o];
        const float *w_o = &TINYCNN_FC2_W[o * FC1_OUT_FEATURES];
        for (int i = 0; i < FC1_OUT_FEATURES; i++) {
            acc += fc1_out[i] * w_o[i];
        }
        res.logits[o] = acc;
    }

    // =========================================================================
    // Temperature Scaling Softmax
    // =========================================================================
    float max_l = res.logits[0];
    if (res.logits[1] > max_l) max_l = res.logits[1];
    if (res.logits[2] > max_l) max_l = res.logits[2];

    float exp_sum = 0.0f;
    for (int o = 0; o < NUM_CLASSES; o++) {
        res.probabilities[o] = expf((res.logits[o] - max_l) / CALIBRATED_TEMPERATURE);
        exp_sum += res.probabilities[o];
    }
    for (int o = 0; o < NUM_CLASSES; o++) {
        res.probabilities[o] /= exp_sum;
    }

    // Find top class and margin
    uint8_t top_idx = 0;
    float top_p = res.probabilities[0];
    for (uint8_t o = 1; o < NUM_CLASSES; o++) {
        if (res.probabilities[o] > top_p) {
            top_p = res.probabilities[o];
            top_idx = o;
        }
    }

    // Find second best for margin
    float second_p = 0.0f;
    for (uint8_t o = 0; o < NUM_CLASSES; o++) {
        if (o != top_idx && res.probabilities[o] > second_p) {
            second_p = res.probabilities[o];
        }
    }

    res.top_class_id = top_idx;
    res.top_confidence = top_p;
    res.margin = top_p - second_p;

    return res;
}
