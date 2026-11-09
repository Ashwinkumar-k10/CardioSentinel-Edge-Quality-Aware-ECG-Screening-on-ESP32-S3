"""
CardioSentinel Edge - Host Replay Reference Pipeline
TECHgium Challenge 26 Research Prototype

Runs end-to-end signal processing, ASQI, MIG, model inference, and triage
producing standardized JSON payloads for host-vs-firmware parity verification.
"""

import os
import json
import numpy as np
from typing import Dict, Any, Optional

from research.asqi import compute_asqi
from research.morphology_guard import evaluate_morphology_integrity
from research.preprocessing import prepare_dual_stream_ecg
from research.calibrate import apply_calibrated_triage
from research.models_tiny import TinyCNNFusedNumPyEngine


def process_ecg_window_reference(
    raw_window: np.ndarray,
    model_engine: Optional[TinyCNNFusedNumPyEngine] = None,
    fs: float = 250.0,
    device_id: str = "cardiosentinel_demo_01",
    mode: str = "dataset_replay",
    model_version: str = "tinycnn_v1_sram"
) -> Dict[str, Any]:
    """
    Standard CardioSentinel Edge Processing Pipeline:
    1. Dual-stream raw preservation and bandpass/notch filtering
    2. Adaptive Signal Quality Intelligence (ASQI)
    3. Morphology Integrity Guard (MIG)
    4. TinyCNN Inference
    5. Calibrated 3-Zone Triage
    """
    n_samples = len(raw_window)
    assert n_samples == 2500, f"Expected 2500 samples (10s @ 250Hz), got {n_samples}"

    raw, filtered = prepare_dual_stream_ecg(raw_window, fs=fs)

    # 1. ASQI Quality Assessment
    asqi_res = compute_asqi(raw, fs=fs)

    # 2. MIG Morphology Check
    mig_res = evaluate_morphology_integrity(raw, filtered, fs=fs)

    # 3. Model Inference (if model engine provided)
    if model_engine is not None:
        norm_filtered = (filtered - np.mean(filtered)) / (np.std(filtered) + 1e-6)
        logits = model_engine.predict(norm_filtered)
        # Softmax with Temperature T = 1.15
        T = 1.15
        exp_l = np.exp((logits / T) - np.max(logits / T))
        probs = exp_l / np.sum(exp_l)
        
        decision, pred_label, conf = apply_calibrated_triage(
            probabilities=probs,
            asqi_usable=asqi_res.usable,
            asqi_flags=asqi_res.flags,
            mig_passed=mig_res.passed
        )
        
        classification_payload = {
            "label": pred_label,
            "confidence": round(float(conf), 4),
            "class_probabilities": {
                "Normal": round(float(probs[0]), 4),
                "AF": round(float(probs[1]), 4),
                "Other": round(float(probs[2]), 4)
            }
        }
    else:
        decision = "ABSTAIN" if not asqi_res.usable else "REVIEW"
        classification_payload = {
            "label": "UNCONFIRMED",
            "confidence": None,
            "class_probabilities": None
        }

    all_reasons = []
    if asqi_res.reasons:
        all_reasons.extend(asqi_res.reasons)
    if not mig_res.passed:
        all_reasons.extend(mig_res.reasons)

    payload = {
        "device_id": device_id,
        "mode": mode,
        "sample_rate_hz": int(fs),
        "window_samples": n_samples,
        "model_version": model_version,
        "quality": {
            "score": round(asqi_res.quality_score, 4),
            "usable": asqi_res.usable,
            "status": "PASS" if asqi_res.usable else "FAIL",
            "flags": asqi_res.flags,
            "reason_codes": all_reasons
        },
        "morphology_guard": {
            "passed": mig_res.passed,
            "flags": mig_res.flags,
            "max_shift_ms": round(mig_res.metrics.get("max_shift_ms", 0.0), 2),
            "max_attenuation": round(mig_res.metrics.get("max_attenuation", 0.0), 3),
            "envelope_rmse": round(mig_res.metrics.get("envelope_rmse", 0.0), 3)
        },
        "classification": classification_payload,
        "decision": decision,
        "dropped_samples": 0
    }

    return payload
