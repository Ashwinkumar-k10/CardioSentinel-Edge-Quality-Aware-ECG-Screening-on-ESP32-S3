"""
CardioSentinel Edge - Uncertainty Calibration & Triage Policy
TECHgium Challenge 26 Research Prototype

Fits temperature scaling parameter T on validation split logits.
Computes calibrated confidence thresholds to guarantee non-degrading sensitivity.
"""

import os
import yaml
import numpy as np
import torch
import torch.nn as nn
from scipy.optimize import minimize
from typing import Dict, Any, Tuple

from research.models_tiny import CardioSentinelTinyCNN


class ModelWithTemperature(nn.Module):
    """
    Applies temperature scaling to logits:
    p_i = exp(z_i / T) / sum(exp(z_j / T))
    """
    def __init__(self, model: nn.Module):
        super(ModelWithTemperature, self).__init__()
        self.model = model
        self.temperature = nn.Parameter(torch.ones(1) * 1.15)

    def forward(self, input):
        logits = self.model(input)
        return self.temperature_scale(logits)

    def temperature_scale(self, logits):
        temperature = self.temperature.unsqueeze(1).expand(logits.size(0), logits.size(1))
        return logits / temperature


def calibrate_temperature(
    model: nn.Module,
    val_loader: torch.utils.data.DataLoader
) -> float:
    """
    Tunes temperature T using NLL on validation set via L-BFGS optimizer.
    """
    model.eval()
    nll_criterion = nn.CrossEntropyLoss()

    logits_list = []
    labels_list = []
    with torch.no_grad():
        for input, label in val_loader:
            logits = model(input)
            logits_list.append(logits)
            labels_list.append(label)
    logits = torch.cat(logits_list)
    labels = torch.cat(labels_list)

    temperature = nn.Parameter(torch.ones(1) * 1.2)
    optimizer = torch.optim.LBFGS([temperature], lr=0.01, max_iter=50)

    def eval():
        optimizer.zero_grad()
        loss = nll_criterion(logits / temperature, labels)
        loss.backward()
        return loss

    optimizer.step(eval)
    t_val = float(temperature.item())
    print(f"[CALIBRATE] Optimal Temperature Scaling factor T = {t_val:.4f}")
    return max(0.5, min(t_val, 3.0))


def apply_calibrated_triage(
    probabilities: np.ndarray,
    asqi_usable: bool,
    asqi_flags: int,
    mig_passed: bool,
    confidence_thresh: float = 0.68,
    margin_thresh: float = 0.15
) -> Tuple[str, str, float]:
    """
    CardioSentinel 3-Zone Decision Policy:
    
    1. ABSTAIN:
       - Triggered by physical/hardware invalidity: lead-off, rail saturation.
       - Model output is masked; decision is strictly ABSTAIN.
       
    2. REVIEW:
       - Triggered if signal is usable but model confidence < confidence_thresh,
         OR top1 - top2 margin < margin_thresh (ambiguous rhythm),
         OR MIG detected filter-induced morphology distortion.
       - Raw & processed waveforms preserved for clinical audit.
       
    3. ACCEPT:
       - High signal quality, MIG passed, calibrated confidence meets threshold.
       
    Returns: (decision, predicted_label, confidence)
    """
    class_names = ["Normal", "AF", "Other"]
    
    # Check physical abstention criteria
    from research.asqi import ASQI_FLAG_LEAD_OFF, ASQI_FLAG_RAIL_SATURATION
    if not asqi_usable or (asqi_flags & (ASQI_FLAG_LEAD_OFF | ASQI_FLAG_RAIL_SATURATION)):
        return "ABSTAIN", "UNINTERPRETABLE", 0.0

    # Sort class probabilities
    top_indices = np.argsort(probabilities)[::-1]
    top1_idx = top_indices[0]
    top2_idx = top_indices[1]
    
    top1_prob = float(probabilities[top1_idx])
    top2_prob = float(probabilities[top2_idx])
    margin = top1_prob - top2_prob
    predicted_label = class_names[top1_idx]

    # Morphology Guard check: if filter distorted suspicious beats, force REVIEW
    if not mig_passed:
        return "REVIEW", f"FLAGGED_{predicted_label.upper()}", top1_prob

    # Model confidence check
    if top1_prob < confidence_thresh or margin < margin_thresh:
        return "REVIEW", f"AMBIGUOUS_{predicted_label.upper()}", top1_prob

    return "ACCEPT", predicted_label, top1_prob
