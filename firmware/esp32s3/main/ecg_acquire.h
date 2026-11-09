/**
 * CardioSentinel Edge - ADS1292R SPI ECG Acquisition & Replay Driver
 * TECHgium Challenge 26 Research Prototype
 * Target: ESP32-S3 Core 0 (Priority 24 Hard Real-Time)
 */

#ifndef ECG_ACQUIRE_H
#define ECG_ACQUIRE_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "ring_buffer.h"

// Acquisition Operational Modes
typedef enum {
    ACQUIRE_MODE_ADS1292R_SPI = 0,    // Live SPI sampling from ADS1292R AFE via /DRDY ISR
    ACQUIRE_MODE_INTERNAL_TEST = 1,   // ADS1292R internal 1 Hz square wave test signal
    ACQUIRE_MODE_DATASET_REPLAY = 2   // Firmware playback of pre-stored benchmark records
} acquire_mode_t;

typedef struct {
    acquire_mode_t mode;
    float sampling_rate_hz;
    uint32_t samples_acquired;
    uint32_t dropped_samples;
    bool is_running;
} ecg_acquire_state_t;

void ecg_acquire_init(ecg_ring_buffer_t *target_ring_buf);
bool ecg_acquire_start(acquire_mode_t mode);
void ecg_acquire_stop(void);
ecg_acquire_state_t ecg_acquire_get_state(void);

// Replay injection API for bench demo
bool ecg_acquire_inject_sample(float sample);

#endif // ECG_ACQUIRE_H
