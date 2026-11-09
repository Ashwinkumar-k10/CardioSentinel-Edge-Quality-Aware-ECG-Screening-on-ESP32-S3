"""
Unit Tests for Calibrated 3-Zone Triage Decisions
"""

import pytest
import numpy as np
from research.calibrate import apply_calibrated_triage
from research.asqi import ASQI_FLAG_OK, ASQI_FLAG_LEAD_OFF, ASQI_FLAG_RAIL_SATURATION


def test_triage_accept_high_confidence():
    probs = np.array([0.92, 0.05, 0.03])
    decision, label, conf = apply_calibrated_triage(
        probabilities=probs,
        asqi_usable=True,
        asqi_flags=ASQI_FLAG_OK,
        mig_passed=True,
        confidence_thresh=0.70
    )
    assert decision == "ACCEPT"
    assert label == "Normal"
    assert conf == pytest.approx(0.92, abs=1e-3)


def test_triage_abstain_on_lead_off():
    probs = np.array([0.95, 0.03, 0.02])
    decision, label, conf = apply_calibrated_triage(
        probabilities=probs,
        asqi_usable=False,
        asqi_flags=ASQI_FLAG_LEAD_OFF,
        mig_passed=True
    )
    assert decision == "ABSTAIN"
    assert label == "UNINTERPRETABLE"


def test_triage_review_on_ambiguous_confidence():
    # Borderline confidence below 0.70
    probs = np.array([0.55, 0.40, 0.05])
    decision, label, conf = apply_calibrated_triage(
        probabilities=probs,
        asqi_usable=True,
        asqi_flags=ASQI_FLAG_OK,
        mig_passed=True,
        confidence_thresh=0.70
    )
    assert decision == "REVIEW"
    assert "AMBIGUOUS" in label


def test_triage_review_on_morphology_distortion():
    probs = np.array([0.95, 0.03, 0.02])
    # MIG failed
    decision, label, conf = apply_calibrated_triage(
        probabilities=probs,
        asqi_usable=True,
        asqi_flags=ASQI_FLAG_OK,
        mig_passed=False
    )
    assert decision == "REVIEW"
    assert "FLAGGED" in label
