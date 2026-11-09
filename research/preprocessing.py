"""
CardioSentinel Edge - Signal Preprocessing & Filtering Module
TECHgium Challenge 26 Research Prototype
"""

import os
import sys
import numpy as np
from typing import Tuple, Dict, Any

def _safe_import_scipy_signal():
    try:
        stderr_fd = sys.stderr.fileno()
        saved_stderr = os.dup(stderr_fd)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, stderr_fd)
        os.close(devnull)
        try:
            from scipy import signal
            _ = signal.butter
            return signal, True
        finally:
            os.dup2(saved_stderr, stderr_fd)
            os.close(saved_stderr)
    except Exception:
        return None, False

signal, HAVE_SCIPY = _safe_import_scipy_signal()


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
    Falls back to zero-phase FIR matching firmware app_main.c if SciPy is unavailable.
    """
    raw = np.asarray(data, dtype=np.float32)
    if HAVE_SCIPY:
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        b, a = signal.butter(order, [low, high], btype='band')
        filtered = signal.filtfilt(b, a, raw, axis=-1)
        return filtered.astype(np.float32)
    else:
        # Zero-phase moving-average detrending + 5-point smoothing (matching embedded C firmware)
        k_dc = max(3, int(fs * 0.8))
        cumsum = np.cumsum(np.insert(raw, 0, 0))
        dc = (cumsum[k_dc:] - cumsum[:-k_dc]) / k_dc
        pad_front = k_dc // 2
        pad_back = len(raw) - len(dc) - pad_front
        dc_padded = np.pad(dc, (pad_front, pad_back), mode='edge')
        detrended = raw - dc_padded
        
        # 5-point smoothing kernel: [0.1, 0.2, 0.4, 0.2, 0.1]
        kernel = np.array([0.1, 0.2, 0.4, 0.2, 0.1], dtype=np.float32)
        filtered = np.convolve(detrended, kernel, mode='same')
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
    if HAVE_SCIPY:
        nyq = 0.5 * fs
        freq = notch_freq / nyq
        b, a = signal.iirnotch(freq, quality_factor)
        filtered = signal.filtfilt(b, a, data, axis=-1)
        return filtered.astype(np.float32)
    return data.astype(np.float32)


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
    
    if HAVE_SCIPY:
        baseline = signal.medfilt(data, kernel_size=window_samples)
        corrected = data - baseline
        return corrected.astype(np.float32)
    else:
        cumsum = np.cumsum(np.insert(data, 0, 0))
        baseline = (cumsum[window_samples:] - cumsum[:-window_samples]) / window_samples
        pad_front = window_samples // 2
        pad_back = len(data) - len(baseline) - pad_front
        baseline_padded = np.pad(baseline, (pad_front, pad_back), mode='edge')
        return (data - baseline_padded).astype(np.float32)


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
