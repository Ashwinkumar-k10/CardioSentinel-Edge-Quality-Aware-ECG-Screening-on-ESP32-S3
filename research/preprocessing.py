"""
CardioSentinel Edge - Signal Preprocessing & Filtering Module
TECHgium Challenge 26 Research Prototype
"""

import numpy as np
from scipy import signal
from typing import Tuple, Dict, Any


def butter_bandpass_filter(
    data: np.ndarray,
    lowcut: float = 0.5,
    highcut: float = 40.0,
    fs: float = 250.0,
    order: int = 2
) -> np.ndarray:
    """
    Standard 2nd-order Butterworth bandpass filter.
    Preserves diagnostic ECG band (0.5 to 40 Hz) while attenuating low-frequency
    drift and high-frequency muscle noise.
    """
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = signal.butter(order, [low, high], btype='band')
    
    # Use forward-backward filtering to prevent phase distortion
    filtered = signal.filtfilt(b, a, data, axis=-1)
    return filtered.astype(np.float32)


def notch_filter(
    data: np.ndarray,
    notch_freq: float = 50.0,
    quality_factor: float = 30.0,
    fs: float = 250.0
) -> np.ndarray:
    """
    IIR Notch filter to remove 50 Hz (or 60 Hz) powerline mains interference.
    """
    nyq = 0.5 * fs
    freq = notch_freq / nyq
    b, a = signal.iirnotch(freq, quality_factor)
    filtered = signal.filtfilt(b, a, data, axis=-1)
    return filtered.astype(np.float32)


def moving_median_baseline_removal(
    data: np.ndarray,
    window_len_ms: float = 200.0,
    fs: float = 250.0
) -> np.ndarray:
    """
    O(N) moving median approximation for baseline removal.
    """
    window_samples = int(window_len_ms * fs / 1000.0)
    if window_samples % 2 == 0:
        window_samples += 1
    
    baseline = signal.medfilt(data, kernel_size=window_samples)
    corrected = data - baseline
    return corrected.astype(np.float32)


def prepare_dual_stream_ecg(
    raw_window: np.ndarray,
    fs: float = 250.0,
    apply_notch: bool = True
) -> Tuple[np.ndarray, np.ndarray]:
    """
    CardioSentinel Architecture Principle:
    Preserve raw ECG window alongside candidate-filtered signal.
    Returns: (raw_ecg, filtered_ecg)
    """
    raw_copy = np.copy(raw_window).astype(np.float32)
    
    # 1. Bandpass 0.5 - 40 Hz
    filtered = butter_bandpass_filter(raw_copy, lowcut=0.5, highcut=40.0, fs=fs)
    
    # 2. Notch filter for powerline if enabled
    if apply_notch:
        filtered = notch_filter(filtered, notch_freq=50.0, fs=fs)
        
    return raw_copy, filtered.astype(np.float32)
