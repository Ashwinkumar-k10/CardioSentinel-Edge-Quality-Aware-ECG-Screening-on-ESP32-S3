/**
 * CardioSentinel Edge - Ring Buffer Implementation
 * Supports lockless/thread-safe single-producer (Core 0 ISR) single-consumer (Core 1 Compute)
 */

#include "ring_buffer.h"
#include <string.h>

void ecg_ring_buffer_init(ecg_ring_buffer_t *rb) {
    if (!rb) return;
    memset((void*)rb->buffer, 0, sizeof(rb->buffer));
    rb->head = 0;
    rb->tail = 0;
    rb->count = 0;
    rb->dropped_samples = 0;
    rb->total_samples_pushed = 0;
}

bool ecg_ring_buffer_push(ecg_ring_buffer_t *rb, float sample) {
    if (!rb) return false;

    if (rb->count >= RING_BUFFER_CAPACITY) {
        // Buffer full: drop oldest sample to avoid stalling high-priority Core 0 ISR
        rb->tail = (rb->tail + 1) % RING_BUFFER_CAPACITY;
        rb->dropped_samples++;
    } else {
        rb->count++;
    }

    rb->buffer[rb->head] = sample;
    rb->head = (rb->head + 1) % RING_BUFFER_CAPACITY;
    rb->total_samples_pushed++;
    return true;
}

bool ecg_ring_buffer_is_window_ready(const ecg_ring_buffer_t *rb) {
    if (!rb) return false;
    return (rb->count >= ECG_WINDOW_SAMPLES);
}

bool ecg_ring_buffer_get_window(ecg_ring_buffer_t *rb, float *out_window, size_t num_samples) {
    if (!rb || !out_window || rb->count < num_samples) {
        return false;
    }

    size_t idx = rb->tail;
    for (size_t i = 0; i < num_samples; i++) {
        out_window[i] = rb->buffer[idx];
        idx = (idx + 1) % RING_BUFFER_CAPACITY;
    }
    return true;
}

void ecg_ring_buffer_advance_stride(ecg_ring_buffer_t *rb, size_t stride_samples) {
    if (!rb) return;
    if (stride_samples > rb->count) {
        stride_samples = rb->count;
    }
    rb->tail = (rb->tail + stride_samples) % RING_BUFFER_CAPACITY;
    rb->count -= stride_samples;
}

uint32_t ecg_ring_buffer_get_dropped(const ecg_ring_buffer_t *rb) {
    return rb ? rb->dropped_samples : 0;
}
