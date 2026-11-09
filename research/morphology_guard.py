"""
CardioSentinel Edge - Morphology Integrity Guard (MIG)
TECHgium Challenge 26 Research Prototype

Guards against filter-induced clinical misclassification. Compares the untouched
raw ECG window against candidate-filtered ECG at detected QRS complexes.
If digital filtering significantly attenuates or shifts abnormal beat morphology
(such as premature ventricular complexes), automatic classification is blocked
and the window is safely escalated to REVIEW.
"""

import numpy as np
from typing import Dict, Any, List, Tuple

# MIG Status Bitmask Constants
MIG_STATUS_PASSED               = 0x0000
MIG_STATUS_R_PEAK_SHIFT         = 0x0001
MIG_STATUS_PEAK_ATTENUATION     = 0x0002
MIG_STATUS_ENVELOPE_DISTORTION  = 0x0004
MIG_STATUS_BEAT_MISMATCH        = 0x0008


class MIGResult:
    def __init__(
        self,
        passed: bool,
        flags: int,
        reasons: List[str],
        metrics: Dict[str, float]
    ):
        self.passed = bool(passed)
        self.flags = int(flags)
        self.reasons = reasons
        self.metrics = metrics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "flags": self.flags,
            "reasons": self.reasons,
            "metrics": {k: round(v, 4) for k, v in self.metrics.items()}
        }


def detect_qrs_peaks(
    ecg_signal: np.ndarray,
    fs: float = 250.0,
    min_distance_ms: float = 250.0,
    rel_height_thresh: float = 0.35
) -> np.ndarray:
    """
    Lightweight, embedded-friendly QRS detector using derivative energy envelope.
    O(N) operation suitable for ESP32-S3 implementation.
    """
    x = np.asarray(ecg_signal, dtype=np.float32)
    n = len(x)
    if n < 10:
        return np.array([], dtype=np.int32)

    # 1. First difference / derivative
    diff = np.diff(x)
    squared_diff = diff ** 2

    # 2. Moving integration window (~80 ms for QRS duration)
    kernel_len = max(3, int(0.08 * fs))
    cumsum = np.cumsum(np.insert(squared_diff, 0, 0))
    integrated = (cumsum[kernel_len:] - cumsum[:-kernel_len]) / kernel_len

    # 3. Dynamic thresholding
    threshold = float(np.mean(integrated) + rel_height_thresh * np.std(integrated))
    min_dist_samples = int(min_distance_ms * fs / 1000.0)

    # Peak search on original signal near high energy regions
    peaks = []
    i = 0
    while i < len(integrated):
        if integrated[i] > threshold:
            # Search local maximum in raw signal in [i, i + kernel_len]
            search_start = max(0, i - kernel_len)
            search_end = min(n, i + 2 * kernel_len)
            local_peak = search_start + int(np.argmax(x[search_start:search_end]))
            
            # Ensure distance from last detected peak
            if not peaks or (local_peak - peaks[-1]) >= min_dist_samples:
                peaks.append(local_peak)
            i += min_dist_samples
        else:
            i += 1

    return np.array(peaks, dtype=np.int32)


def evaluate_morphology_integrity(
    raw_ecg: np.ndarray,
    filtered_ecg: np.ndarray,
    fs: float = 250.0,
    max_shift_ms: float = 16.0,             # Max allowable R-peak delta t_R (~4 samples @ 250Hz)
    max_attenuation_ratio: float = 0.38,     # Max 38% peak attenuation allowed
    max_envelope_rmse: float = 0.45         # Normalized envelope discrepancy boundary
) -> MIGResult:
    """
    Evaluates morphological consistency between raw and filtered signal.
    """
    raw = np.asarray(raw_ecg, dtype=np.float32)
    filt = np.asarray(filtered_ecg, dtype=np.float32)
    n = len(raw)
    
    flags = MIG_STATUS_PASSED
    reasons: List[str] = []

    # Detect peaks in both signals
    raw_peaks = detect_qrs_peaks(raw, fs=fs)
    filt_peaks = detect_qrs_peaks(filt, fs=fs)

    if len(raw_peaks) == 0:
        return MIGResult(True, MIG_STATUS_PASSED, ["NO_PEAKS_DETECTED"], {
            "max_shift_ms": 0.0,
            "max_attenuation": 0.0,
            "envelope_rmse": 0.0
        })

    # 1. Beat Count / Mismatch Check
    peak_diff = abs(len(raw_peaks) - len(filt_peaks))
    if peak_diff > max(2, int(0.25 * len(raw_peaks))):
        flags |= MIG_STATUS_BEAT_MISMATCH
        reasons.append("QRS_COUNT_MISMATCH")

    # 2. Match corresponding peaks and check displacement (delta t_R) & amplitude attenuation
    max_detected_shift_samples = 0
    max_detected_attenuation = 0.0
    matched_shifts = []
    matched_attenuations = []

    for r_p in raw_peaks:
        # Find nearest peak in filtered signal within ±50ms
        window_radius = int(0.05 * fs)
        candidates = filt_peaks[np.abs(filt_peaks - r_p) <= window_radius]
        if len(candidates) > 0:
            nearest = candidates[np.argmin(np.abs(candidates - r_p))]
            shift_samp = abs(int(nearest) - int(r_p))
            matched_shifts.append(shift_samp)
            
            # Check amplitude at peaks
            raw_amp = abs(raw[r_p])
            filt_amp = abs(filt[nearest])
            if raw_amp > 1e-4:
                attenuation = (raw_amp - filt_amp) / raw_amp
                matched_attenuations.append(attenuation)

    max_shift_samp = max(matched_shifts) if matched_shifts else 0
    max_shift_ms_val = (max_shift_samp / fs) * 1000.0
    max_attenuation_val = max(matched_attenuations) if matched_attenuations else 0.0

    if max_shift_ms_val > max_shift_ms:
        flags |= MIG_STATUS_R_PEAK_SHIFT
        reasons.append(f"R_PEAK_SHIFT_{round(max_shift_ms_val, 1)}MS")

    if max_attenuation_val > max_attenuation_ratio:
        flags |= MIG_STATUS_PEAK_ATTENUATION
        reasons.append(f"AMPLITUDE_ATTENUATION_{round(max_attenuation_val * 100, 1)}PCT")

    # 3. Overall QRS Envelope Distortion RMSE
    # Compare centered normalized signals in the active QRS band
    raw_norm = (raw - np.mean(raw)) / (np.std(raw) + 1e-6)
    filt_norm = (filt - np.mean(filt)) / (np.std(filt) + 1e-6)
    rmse = float(np.sqrt(np.mean((raw_norm - filt_norm) ** 2)))

    if rmse > max_envelope_rmse:
        flags |= MIG_STATUS_ENVELOPE_DISTORTION
        reasons.append(f"ENVELOPE_DISTORTION_RMSE_{round(rmse, 2)}")

    passed = (flags == MIG_STATUS_PASSED)
    if not reasons:
        reasons.append("MORPHOLOGY_PRESERVED")

    metrics = {
        "max_shift_ms": max_shift_ms_val,
        "max_attenuation": max_attenuation_val,
        "envelope_rmse": rmse,
        "raw_peak_count": float(len(raw_peaks)),
        "filt_peak_count": float(len(filt_peaks))
    }

    return MIGResult(
        passed=passed,
        flags=flags,
        reasons=reasons,
        metrics=metrics
    )
