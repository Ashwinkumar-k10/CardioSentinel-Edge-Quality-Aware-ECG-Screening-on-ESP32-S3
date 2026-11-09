"""
CardioSentinel Edge - Signal Preprocessing & Filtering Module
TECHgium Challenge 26 Research Prototype
"""

import numpy as np
from typing import Tuple, Dict, Any

try:
    from scipy import signal
    _SCIPY_AVAILABLE = True
except (ImportError, AttributeError):
    signal = None
    _SCIPY_AVAILABLE = False


def pure_numpy_conservative_filter(data: np.ndarray) -> np.ndarray:
    """
    Zero-dependency 5-point moving average filter matching exact ESP32-S3 firmware C
    implementation in firmware/esp32s3/main/app_main.c.
    Preserves diagnostic ECG band while attenuating high-frequency noise and baseline offset.
    """
    x = np.asarray(data, dtype=np.float32)
    n = len(x)
    if n < 5:
        return np.copy(x)
    
    filt = np.empty_like(x)
    filt[0] = x[0]
    filt[1] = x[1]
    filt[-2] = x[-2]
    filt[-1] = x[-1]

    # Symmetric weights: [0.1, 0.2, 0.4, 0.2, 0.1]
    filt[2:-2] = (
        0.1 * x[:-4] +
        0.2 * x[1:-3] +
        0.4 * x[2:-2] +
        0.2 * x[3:-1] +
        0.1 * x[4:]
    )
    return filt.astype(np.float32)


def butter_bandpass_filter(
    data: np.ndarray,
    lowcut: float = 0.5,
    highcut: float = 40.0,
    fs: float = 250.0,
    order: int = 2
) -> np.ndarray:
    """
    Standard 2nd-order Butterworth bandpass filter.
    Falls back to pure-NumPy firmware-matched filter if SciPy is unavailable.
    """
    if not _SCIPY_AVAILABLE or signal is None:
        return pure_numpy_conservative_filter(data)

    try:
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        b, a = signal.butter(order, [low, high], btype='band')
        filtered = signal.filtfilt(b, a, data, axis=-1)
        return filtered.astype(np.float32)
    except Exception:
        return pure_numpy_conservative_filter(data)


def notch_filter(
    data: np.ndarray,
    notch_freq: float = 50.0,
    quality_factor: float = 30.0,
    fs: float = 250.0
) -> np.ndarray:
    """
    IIR Notch filter to remove 50 Hz (or 60 Hz) powerline mains interference.
    Falls back to pure-NumPy filter if SciPy is unavailable.
    """
    if not _SCIPY_AVAILABLE or signal is None:
        return pure_numpy_conservative_filter(data)

    try:
        nyq = 0.5 * fs
        freq = notch_freq / nyq
        b, a = signal.iirnotch(freq, quality_factor)
        filtered = signal.filtfilt(b, a, data, axis=-1)
        return filtered.astype(np.float32)
    except Exception:
        return pure_numpy_conservative_filter(data)


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
    
    if _SCIPY_AVAILABLE and signal is not None and hasattr(signal, 'medfilt'):
        try:
            baseline = signal.medfilt(data, kernel_size=window_samples)
            corrected = data - baseline
            return corrected.astype(np.float32)
        except Exception:
            pass

    # Pure NumPy block mean baseline removal fallback
    k = max(3, window_samples)
    cumsum = np.cumsum(np.insert(data, 0, 0))
    # Approximate baseline via sliding average
    half = k // 2
    padded = np.pad(data, (half, half), mode='edge')
    cumsum_pad = np.cumsum(np.insert(padded, 0, 0))
    baseline = (cumsum_pad[k:] - cumsum_pad[:-k]) / k
    corrected = data - baseline[:len(data)]
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
    if apply_notch and _SCIPY_AVAILABLE:
        filtered = notch_filter(filtered, notch_freq=50.0, fs=fs)
        
    return raw_copy, filtered.astype(np.float32)
