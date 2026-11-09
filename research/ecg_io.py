"""
CardioSentinel Edge - ECG Input/Output & Resampling Module
TECHgium Challenge 26 Research Prototype
"""

import os
import math
import numpy as np
from scipy import signal
from typing import Tuple, Dict, Any, Optional, List


def resample_ecg(
    signal_data: np.ndarray,
    original_fs: float,
    target_fs: float = 250.0
) -> np.ndarray:
    """
    Resample ECG signal to target_fs (default 250 Hz) using polyphase filtering
    with anti-aliasing.
    """
    if abs(original_fs - target_fs) < 1e-3:
        return signal_data.astype(np.float32)

    # Calculate rational approximation for resample_poly
    gcd = math.gcd(int(round(original_fs)), int(round(target_fs)))
    up = int(round(target_fs)) // gcd
    down = int(round(original_fs)) // gcd

    resampled = signal.resample_poly(signal_data, up, down, axis=-1)
    return resampled.astype(np.float32)


def generate_synthetic_ecg(
    rhythm_type: str = "normal",
    duration_sec: float = 10.0,
    sampling_rate: int = 250,
    heart_rate_bpm: float = 75.0,
    noise_type: Optional[str] = None,
    noise_amplitude: float = 0.2,
    seed: Optional[int] = 42
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Generates realistic synthetic 250 Hz ECG windows for bench testing, unit testing,
    and baseline validation when external PhysioNet data is not locally downloaded.
    
    Rhythm types:
      - 'normal': Regular sinus rhythm with P-wave, QRS complex, T-wave.
      - 'af': Atrial fibrillation with irregularly irregular RR intervals and fibrillatory f-waves.
      - 'other': Sinus rhythm with ectopic premature ventricular contractions (PVCs).
      
    Noise types:
      - None: Clean ECG
      - 'baseline_wander': 0.15 - 0.3 Hz breathing drift
      - 'muscle_emg': High-frequency random Gaussian burst noise
      - 'rail_saturation': Voltage clipping at ADC positive/negative rails
      - 'lead_off': Flatline / near-zero variance disconnection
    """
    if seed is not None:
        np.random.seed(seed)

    n_samples = int(duration_sec * sampling_rate)
    time = np.linspace(0, duration_sec, n_samples, endpoint=False)
    ecg = np.zeros(n_samples, dtype=np.float32)

    # Generate beat timestamps based on rhythm
    beat_times = []
    if rhythm_type.lower() == "normal":
        rr_interval = 60.0 / heart_rate_bpm
        t = 0.2
        while t < duration_sec - 0.1:
            beat_times.append(t)
            # Normal physiological sinus arrhythmia (±4%)
            t += rr_interval * (1.0 + 0.04 * np.sin(2 * np.pi * 0.2 * t))

    elif rhythm_type.lower() == "af":
        # Irregularly irregular RR intervals (variable refractory period)
        mean_rr = 60.0 / heart_rate_bpm
        t = 0.2
        while t < duration_sec - 0.1:
            beat_times.append(t)
            # Log-normal/random variation in RR intervals characteristic of AF
            t += np.random.uniform(0.6 * mean_rr, 1.4 * mean_rr)

        # Add chaotic fibrillatory f-waves (4-8 Hz undulating oscillations)
        f_wave = 0.08 * np.sin(2 * np.pi * 6.2 * time) + 0.05 * np.cos(2 * np.pi * 4.7 * time)
        ecg += f_wave

    elif rhythm_type.lower() == "other":
        # Ectopic Premature Ventricular Contractions (PVC)
        rr_interval = 60.0 / heart_rate_bpm
        t = 0.2
        beat_idx = 0
        while t < duration_sec - 0.1:
            is_pvc = (beat_idx % 4 == 2)  # Every 4th beat is premature
            beat_times.append((t, is_pvc))
            if is_pvc:
                t += rr_interval * 0.65  # Short coupled beat
            else:
                t += rr_interval
            beat_idx += 1

    # Synthesize individual heartbeat waveforms
    for beat in beat_times:
        if isinstance(beat, tuple):
            t_r, is_pvc = beat
        else:
            t_r = beat
            is_pvc = False

        idx_r = int(t_r * sampling_rate)

        if not is_pvc:
            # Normal P-Q-R-S-T morphology
            # P wave (at -160 ms, duration 80 ms, amp 0.15) if not AF
            if rhythm_type.lower() != "af":
                t_p = t_r - 0.16
                sig_p = 0.035
                ecg += 0.15 * np.exp(-((time - t_p) ** 2) / (2 * sig_p ** 2))

            # Q wave (-40 ms, amp -0.15)
            t_q = t_r - 0.035
            ecg -= 0.15 * np.exp(-((time - t_q) ** 2) / (2 * 0.012 ** 2))

            # R peak (0 ms, amp 1.2 mV, narrow width)
            ecg += 1.25 * np.exp(-((time - t_r) ** 2) / (2 * 0.018 ** 2))

            # S wave (+40 ms, amp -0.25)
            t_s = t_r + 0.035
            ecg -= 0.25 * np.exp(-((time - t_s) ** 2) / (2 * 0.014 ** 2))

            # T wave (+250 ms, amp 0.3)
            t_t = t_r + 0.24
            ecg += 0.30 * np.exp(-((time - t_t) ** 2) / (2 * 0.055 ** 2))
        else:
            # Wide, bizarre PVC morphology (no P wave, wide QRS, inverted T wave)
            ecg += 1.60 * np.exp(-((time - t_r) ** 2) / (2 * 0.045 ** 2))
            ecg -= 0.70 * np.exp(-((time - (t_r + 0.07)) ** 2) / (2 * 0.040 ** 2))
            # Discordant inverted T wave
            t_t = t_r + 0.28
            ecg -= 0.45 * np.exp(-((time - t_t) ** 2) / (2 * 0.08 ** 2))

    # Add realistic mild background physiological noise
    ecg += 0.015 * np.random.randn(n_samples)

    metadata = {
        "rhythm_type": rhythm_type,
        "heart_rate_bpm": heart_rate_bpm,
        "sampling_rate": sampling_rate,
        "duration_sec": duration_sec,
        "noise_type": noise_type,
        "n_samples": n_samples
    }

    # Apply synthetic artifacts if specified
    if noise_type == "baseline_wander":
        drift = noise_amplitude * 1.5 * np.sin(2 * np.pi * 0.25 * time) + \
                noise_amplitude * 0.8 * np.sin(2 * np.pi * 0.08 * time)
        ecg += drift
    elif noise_type == "muscle_emg":
        emg = noise_amplitude * np.random.randn(n_samples) * (1.0 + 0.5 * np.sin(2 * np.pi * 1.5 * time))
        ecg += emg
    elif noise_type == "rail_saturation":
        rail_v = 1.05  # Saturation limit
        ecg = np.clip(ecg, -rail_v, rail_v)
    elif noise_type == "lead_off":
        # Disconnected electrode: tiny microvolt noise floor
        ecg = 0.001 * np.random.randn(n_samples)

    return ecg.astype(np.float32), metadata


def slice_sliding_windows(
    ecg_signal: np.ndarray,
    window_samples: int = 2500,
    stride_samples: int = 625
) -> np.ndarray:
    """
    Slices continuous ECG into sliding windows (e.g. 10s @ 250Hz, 2.5s stride).
    Returns array of shape (n_windows, window_samples).
    """
    n_samples = len(ecg_signal)
    if n_samples < window_samples:
        # Pad with edge values if shorter than one window
        padded = np.pad(ecg_signal, (0, window_samples - n_samples), mode='edge')
        return padded[np.newaxis, :]

    windows = []
    start = 0
    while start + window_samples <= n_samples:
        windows.append(ecg_signal[start:start + window_samples])
        start += stride_samples

    return np.array(windows, dtype=np.float32)
