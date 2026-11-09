"""
Unit Tests for Morphology Integrity Guard (MIG)
"""

import pytest
import numpy as np
from research.morphology_guard import (
    evaluate_morphology_integrity,
    detect_qrs_peaks,
    MIG_STATUS_PASSED,
    MIG_STATUS_R_PEAK_SHIFT,
    MIG_STATUS_PEAK_ATTENUATION
)
from research.ecg_io import generate_synthetic_ecg
from research.preprocessing import butter_bandpass_filter


def test_mig_on_clean_normal_ecg():
    ecg, _ = generate_synthetic_ecg(rhythm_type="normal", duration_sec=10.0, seed=42)
    filtered = butter_bandpass_filter(ecg, lowcut=0.5, highcut=40.0, fs=250.0)
    res = evaluate_morphology_integrity(ecg, filtered, fs=250.0)
    assert res.passed is True
    assert res.flags == MIG_STATUS_PASSED


def test_mig_detects_peak_shift():
    ecg, _ = generate_synthetic_ecg(rhythm_type="normal", duration_sec=10.0, seed=42)
    # Artificially shift filtered signal by 25 ms (6 samples @ 250 Hz)
    shifted = np.roll(ecg, 6)
    res = evaluate_morphology_integrity(ecg, shifted, fs=250.0, max_shift_ms=16.0)
    assert res.passed is False
    assert (res.flags & MIG_STATUS_R_PEAK_SHIFT) != 0


def test_mig_detects_amplitude_attenuation():
    ecg, _ = generate_synthetic_ecg(rhythm_type="other", duration_sec=10.0, seed=42)
    # Artificially attenuate filtered signal by 40%
    attenuated = ecg * 0.60
    res = evaluate_morphology_integrity(ecg, attenuated, fs=250.0, max_attenuation_ratio=0.25)
    assert res.passed is False
    assert (res.flags & MIG_STATUS_PEAK_ATTENUATION) != 0
