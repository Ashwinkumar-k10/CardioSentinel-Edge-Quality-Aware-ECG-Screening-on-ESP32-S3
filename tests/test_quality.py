"""
Unit Tests for Adaptive Signal Quality Intelligence (ASQI)
"""

import pytest
import numpy as np
from research.asqi import (
    compute_asqi,
    ASQI_FLAG_OK,
    ASQI_FLAG_LEAD_OFF,
    ASQI_FLAG_RAIL_SATURATION,
    ASQI_FLAG_EXCESSIVE_DRIFT,
    ASQI_FLAG_MUSCLE_NOISE_EMG
)
from research.ecg_io import generate_synthetic_ecg


def test_asqi_clean_ecg():
    ecg, _ = generate_synthetic_ecg(rhythm_type="normal", duration_sec=10.0, seed=42)
    res = compute_asqi(ecg, fs=250.0)
    assert res.usable is True
    assert res.quality_score >= 0.80
    assert "CLEAN" in res.reasons


def test_asqi_lead_off_flatline():
    # Microvolt noise floor simulating disconnected electrodes
    ecg = np.random.randn(2500) * 0.001
    res = compute_asqi(ecg, fs=250.0)
    assert res.usable is False
    assert (res.flags & ASQI_FLAG_LEAD_OFF) != 0
    assert "LEAD_OFF" in res.reasons
    assert res.quality_score == 0.0


def test_asqi_rail_saturation():
    ecg, _ = generate_synthetic_ecg(rhythm_type="normal", duration_sec=10.0, seed=42)
    # Saturate signal at 1.05V
    ecg_clipped = np.clip(ecg, -1.05, 1.05)
    res = compute_asqi(ecg_clipped, fs=250.0)
    assert (res.flags & ASQI_FLAG_RAIL_SATURATION) != 0
    assert res.usable is False


def test_asqi_excessive_drift():
    ecg, _ = generate_synthetic_ecg(
        rhythm_type="normal",
        duration_sec=10.0,
        noise_type="baseline_wander",
        noise_amplitude=1.5,
        seed=42
    )
    res = compute_asqi(ecg, fs=250.0)
    assert (res.flags & ASQI_FLAG_EXCESSIVE_DRIFT) != 0
    assert "EXCESSIVE_DRIFT" in res.reasons
