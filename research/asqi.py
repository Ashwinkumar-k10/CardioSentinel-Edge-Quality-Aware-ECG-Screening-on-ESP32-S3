"""
CardioSentinel Edge - Adaptive Signal Quality Intelligence (ASQI)
TECHgium Challenge 26 Research Prototype

Bounded O(N) complexity signal quality evaluation for embedded microcontrollers.
Strictly excludes O(N^2) sample entropy to guarantee real-time execution (< 15 ms on ESP32-S3).
"""

import numpy as np
from typing import Dict, Any, List, Tuple

# Bitmask Constants for Firmware Parity
ASQI_FLAG_OK                = 0x0000
ASQI_FLAG_LEAD_OFF          = 0x0001
ASQI_FLAG_RAIL_SATURATION   = 0x0002
ASQI_FLAG_EXCESSIVE_DRIFT   = 0x0004
ASQI_FLAG_MUSCLE_NOISE_EMG  = 0x0008
ASQI_FLAG_LOW_AMPLITUDE     = 0x0010
ASQI_FLAG_HIGH_ZERO_CROSS   = 0x0020


class ASQIResult:
    def __init__(
        self,
        quality_score: float,
        usable: bool,
        flags: int,
        reasons: List[str],
        metrics: Dict[str, float]
    ):
        self.quality_score = float(quality_score)
        self.usable = bool(usable)
        self.flags = int(flags)
        self.reasons = reasons
        self.metrics = metrics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quality_score": round(self.quality_score, 4),
            "usable": self.usable,
            "flags": self.flags,
            "reasons": self.reasons,
            "metrics": {k: round(v, 4) for k, v in self.metrics.items()}
        }


def compute_asqi(
    signal_data: np.ndarray,
    fs: float = 250.0,
    rail_threshold_v: float = 3.0,
    flatline_variance_min: float = 0.0005,
    max_drift_threshold: float = 0.8,
    max_line_length_norm: float = 0.12,
    min_zero_cross_rate: float = 0.005,
    max_zero_cross_rate: float = 0.35
) -> ASQIResult:
    """
    Computes embedded-ready O(N) ASQI metrics for a 10-second ECG window (N=2500).
    """
    x = np.asarray(signal_data, dtype=np.float32)
    n = len(x)
    if n == 0:
        return ASQIResult(0.0, False, ASQI_FLAG_LEAD_OFF, ["EMPTY_SIGNAL"], {})

    flags = ASQI_FLAG_OK
    reasons: List[str] = []

    # 1. Linear scan for Flatline / Electrode Detachment (Lead-off)
    v_max = float(np.max(x))
    v_min = float(np.min(x))
    peak_to_peak = v_max - v_min
    signal_variance = float(np.var(x))

    if signal_variance < flatline_variance_min or peak_to_peak < 0.03:
        flags |= ASQI_FLAG_LEAD_OFF
        reasons.append("LEAD_OFF")
        return ASQIResult(
            quality_score=0.0,
            usable=False,
            flags=flags,
            reasons=reasons,
            metrics={"peak_to_peak": peak_to_peak, "variance": signal_variance}
        )

    # 2. Linear scan for Rail Clipping / Saturation (Flat-top clipping or extreme voltage)
    diffs = np.abs(np.diff(x))
    flat_at_positive_peak = np.sum((diffs < 1e-4) & (x[:-1] > 0.85 * v_max))
    flat_at_negative_peak = np.sum((diffs < 1e-4) & (x[:-1] < 0.85 * v_min))
    is_rail_saturated = (flat_at_positive_peak + flat_at_negative_peak > 15) or (v_max >= rail_threshold_v) or (v_min <= -rail_threshold_v)

    if is_rail_saturated:
        flags |= ASQI_FLAG_RAIL_SATURATION
        reasons.append("RAIL_SATURATION")

    # 3. Baseline Drift Proxy (Difference between moving average and global mean)
    kernel_size = int(fs)
    if kernel_size > 0 and n >= kernel_size:
        cumsum = np.cumsum(np.insert(x, 0, 0))
        block_means = (cumsum[kernel_size:] - cumsum[:-kernel_size]) / kernel_size
        drift_span = float(np.max(block_means) - np.min(block_means))
    else:
        drift_span = 0.0

    if drift_span > max_drift_threshold:
        flags |= ASQI_FLAG_EXCESSIVE_DRIFT
        reasons.append("EXCESSIVE_DRIFT")

    # 4. Curve Line-Length / High-Frequency Complexity
    line_length = float(np.sum(diffs))
    line_length_norm = line_length / (n * max(peak_to_peak, 0.1))

    if line_length_norm > max_line_length_norm:
        flags |= ASQI_FLAG_MUSCLE_NOISE_EMG
        reasons.append("MUSCLE_NOISE_EMG")

    # 5. Zero-Crossing Rate (Centered around mean)
    x_centered = x - np.mean(x)
    zero_crossings = np.sum(np.diff(np.signbit(x_centered)) != 0)
    zero_cross_rate = float(zero_crossings) / n

    if zero_cross_rate > max_zero_cross_rate:
        flags |= ASQI_FLAG_HIGH_ZERO_CROSS
        reasons.append("HIGH_ZERO_CROSSING")

    # 6. Composite Quality Score [0.0 - 1.0]
    # Penalize based on detected degradation modes
    score = 1.0
    if flags & ASQI_FLAG_LEAD_OFF:
        score -= 0.95
    if flags & ASQI_FLAG_RAIL_SATURATION:
        score -= 0.60
    if flags & ASQI_FLAG_EXCESSIVE_DRIFT:
        score -= 0.25 * min(drift_span / max_drift_threshold, 2.0)
    if flags & ASQI_FLAG_MUSCLE_NOISE_EMG:
        score -= 0.35 * min(line_length_norm / max_line_length_norm, 2.0)
    if flags & ASQI_FLAG_HIGH_ZERO_CROSS:
        score -= 0.20

    score = float(np.clip(score, 0.0, 1.0))
    usable = (score >= 0.55) and not (flags & (ASQI_FLAG_LEAD_OFF | ASQI_FLAG_RAIL_SATURATION))

    metrics = {
        "peak_to_peak": peak_to_peak,
        "variance": signal_variance,
        "is_rail_saturated": float(1.0 if is_rail_saturated else 0.0),
        "drift_span": drift_span,
        "line_length_norm": line_length_norm,
        "zero_cross_rate": zero_cross_rate
    }

    if not reasons:
        reasons.append("CLEAN")

    return ASQIResult(
        quality_score=score,
        usable=usable,
        flags=flags,
        reasons=reasons,
        metrics=metrics
    )
