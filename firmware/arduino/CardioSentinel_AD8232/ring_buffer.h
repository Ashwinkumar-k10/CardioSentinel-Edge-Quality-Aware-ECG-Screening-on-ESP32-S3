/**
 * CardioSentinel Edge - Thread-Safe Circular ECG Buffer
 * TECHgium Challenge 26 Research Prototype
 * Target: ESP32-S3 Internal SRAM (Zero wait states)
 */

#ifndef RING_BUFFER_H
#define RING_BUFFER_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#define ECG_WINDOW_SAMPLES      2500   // 10.0 seconds @ 250 Hz
#define ECG_STRIDE_SAMPLES      625    // 2.5 seconds stride (75% overlap)
#define RING_BUFFER_CAPACITY    3750   // 15 seconds capacity to absorb compute jitter

typedef struct {
    float buffer[RING_BUFFER_CAPACITY];
    volatile size_t head;
    volatile size_t tail;
    volatile size_t count;
    volatile uint32_t dropped_samples;
    volatile uint32_t total_samples_pushed;
} ecg_ring_buffer_t;

void ecg_ring_buffer_init(ecg_ring_buffer_t *rb);
bool ecg_ring_buffer_push(ecg_ring_buffer_t *rb, float sample);
bool ecg_ring_buffer_is_window_ready(const ecg_ring_buffer_t *rb);
bool ecg_ring_buffer_get_window(ecg_ring_buffer_t *rb, float *out_window, size_t num_samples);
void ecg_ring_buffer_advance_stride(ecg_ring_buffer_t *rb, size_t stride_samples);
uint32_t ecg_ring_buffer_get_dropped(const ecg_ring_buffer_t *rb);

#endif // RING_BUFFER_H
