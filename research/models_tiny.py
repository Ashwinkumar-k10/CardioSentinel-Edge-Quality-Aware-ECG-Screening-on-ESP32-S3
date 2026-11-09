"""
CardioSentinel Edge - Tiny 1D-CNN Model Architecture for ESP32-S3
TECHgium Challenge 26 Research Prototype

Designed specifically for MCU zero-wait-state SRAM constraint (< 120 KB arena, < 25k params).
Includes both PyTorch nn.Module and a zero-dependency pure-NumPy inference engine
for bit-accurate parity verification between host and embedded C firmware.
"""

import math
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Any, Tuple, Optional


class CardioSentinelTinyCNN(nn.Module):
    """
    Lightweight 1D-CNN Rhythm Classifier optimized for Xtensa LX7 MCU SIMD operations.
    Total parameters: ~18,500 (< 75 KB unquantized float32, < 19 KB quantized INT8).
    """
    def __init__(self, in_channels: int = 1, num_classes: int = 3):
        super(CardioSentinelTinyCNN, self).__init__()
        
        # Block 1: Conv1D (k=7, s=2) -> BatchNorm -> ReLU -> MaxPool (k=2, s=2)
        # Input: [B, 1, 2500] -> Conv: [B, 16, 1250] -> Pool: [B, 16, 625]
        self.conv1 = nn.Conv1d(in_channels, 16, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm1d(16)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool1d(kernel_size=2, stride=2)

        # Block 2: Conv1D (k=5, s=2) -> BatchNorm -> ReLU -> MaxPool (k=2, s=2)
        # Input: [B, 16, 625] -> Conv: [B, 32, 313] -> Pool: [B, 32, 156]
        self.conv2 = nn.Conv1d(16, 32, kernel_size=5, stride=2, padding=2, bias=False)
        self.bn2 = nn.BatchNorm1d(32)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool1d(kernel_size=2, stride=2)

        # Block 3: Conv1D (k=3, s=2) -> BatchNorm -> ReLU
        # Input: [B, 32, 156] -> Conv: [B, 48, 78]
        self.conv3 = nn.Conv1d(32, 48, kernel_size=3, stride=2, padding=1, bias=False)
        self.bn3 = nn.BatchNorm1d(48)
        self.relu3 = nn.ReLU()

        # Global Average Pooling -> [B, 48]
        self.global_pool = nn.AdaptiveAvgPool1d(1)

        # Fully Connected Head
        self.fc1 = nn.Linear(48, 24)
        self.relu_fc = nn.ReLU()
        self.dropout = nn.Dropout(0.2)
        self.fc2 = nn.Linear(24, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: [B, 1, 2500]
        x = self.pool1(self.relu1(self.bn1(self.conv1(x))))
        x = self.pool2(self.relu2(self.bn2(self.conv2(x))))
        x = self.relu3(self.bn3(self.conv3(x)))
        x = self.global_pool(x)  # [B, 48, 1]
        x = x.squeeze(-1)        # [B, 48]
        x = self.relu_fc(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)          # [B, 3] logits
        return x


def fuse_conv_bn_weights(conv: nn.Conv1d, bn: nn.BatchNorm1d) -> Tuple[np.ndarray, np.ndarray]:
    """
    Fuses Convolution and BatchNorm weights for embedded deployment to save runtime compute.
    w_fused = w * gamma / sqrt(var + eps)
    b_fused = beta - mean * gamma / sqrt(var + eps)
    """
    w = conv.weight.detach().cpu().numpy()
    gamma = bn.weight.detach().cpu().numpy()
    beta = bn.bias.detach().cpu().numpy()
    mean = bn.running_mean.detach().cpu().numpy()
    var = bn.running_var.detach().cpu().numpy()
    eps = bn.eps

    std = np.sqrt(var + eps)
    w_fused = w * (gamma / std)[:, np.newaxis, np.newaxis]
    b_fused = beta - mean * (gamma / std)
    return w_fused.astype(np.float32), b_fused.astype(np.float32)


class TinyCNNFusedNumPyEngine:
    """
    Pure NumPy implementation of the fused model for host parity testing and embedded emulation.
    Matches exact arithmetic of firmware C implementation.
    """
    def __init__(self, fused_weights: Dict[str, np.ndarray]):
        self.w1 = fused_weights["w1"]  # [16, 1, 7]
        self.b1 = fused_weights["b1"]  # [16]
        self.w2 = fused_weights["w2"]  # [32, 16, 5]
        self.b2 = fused_weights["b2"]  # [32]
        self.w3 = fused_weights["w3"]  # [48, 32, 3]
        self.b3 = fused_weights["b3"]  # [48]
        self.w_fc1 = fused_weights["w_fc1"]  # [24, 48]
        self.b_fc1 = fused_weights["b_fc1"]  # [24]
        self.w_fc2 = fused_weights["w_fc2"]  # [3, 24]
        self.b_fc2 = fused_weights["b_fc2"]  # [3]

    def _conv1d_fused(self, x: np.ndarray, w: np.ndarray, b: np.ndarray, stride: int, pad: int) -> np.ndarray:
        # x: [C_in, L_in], w: [C_out, C_in, K], b: [C_out]
        c_in, l_in = x.shape
        c_out, _, k = w.shape
        if pad > 0:
            x_padded = np.pad(x, ((0, 0), (pad, pad)), mode='constant')
        else:
            x_padded = x
        l_out = (x_padded.shape[1] - k) // stride + 1
        out = np.zeros((c_out, l_out), dtype=np.float32)
        for oc in range(c_out):
            out[oc, :] = b[oc]
            for ic in range(c_in):
                for i in range(l_out):
                    start = i * stride
                    out[oc, i] += np.sum(x_padded[ic, start:start+k] * w[oc, ic, :])
        return out

    def _maxpool1d(self, x: np.ndarray, k: int = 2, s: int = 2) -> np.ndarray:
        c, l = x.shape
        l_out = (l - k) // s + 1
        out = np.zeros((c, l_out), dtype=np.float32)
        for i in range(l_out):
            start = i * s
            out[:, i] = np.max(x[:, start:start+k], axis=1)
        return out

    def predict(self, ecg_window: np.ndarray) -> np.ndarray:
        # Input: [2500] or [1, 2500]
        if ecg_window.ndim == 1:
            x = ecg_window[np.newaxis, :]
        else:
            x = ecg_window

        # Block 1: Conv1D (k=7, s=2, pad=3) + Bias + ReLU + MaxPool(2, 2)
        z1 = self._conv1d_fused(x, self.w1, self.b1, stride=2, pad=3)
        a1 = np.maximum(0, z1)
        p1 = self._maxpool1d(a1, k=2, s=2)

        # Block 2: Conv1D (k=5, s=2, pad=2) + Bias + ReLU + MaxPool(2, 2)
        z2 = self._conv1d_fused(p1, self.w2, self.b2, stride=2, pad=2)
        a2 = np.maximum(0, z2)
        p2 = self._maxpool1d(a2, k=2, s=2)

        # Block 3: Conv1D (k=3, s=2, pad=1) + Bias + ReLU
        z3 = self._conv1d_fused(p2, self.w3, self.b3, stride=2, pad=1)
        a3 = np.maximum(0, z3)

        # Global Average Pooling over length
        gap = np.mean(a3, axis=1)  # [48]

        # FC1: [48] -> [24] + ReLU
        fc1_out = np.maximum(0, np.dot(self.w_fc1, gap) + self.b_fc1)

        # FC2: [24] -> [3] (Logits)
        logits = np.dot(self.w_fc2, fc1_out) + self.b_fc2
        return logits.astype(np.float32)
