"""
Unit Tests for Sliding Window Segmentation and Resampling
"""

import pytest
import numpy as np
from research.ecg_io import slice_sliding_windows, resample_ecg


def test_slice_sliding_windows():
    # 20 seconds of ECG at 250 Hz = 5000 samples
    continuous_ecg = np.random.randn(5000).astype(np.float32)
    # 10s window (2500 samples), 2.5s stride (625 samples)
    windows = slice_sliding_windows(continuous_ecg, window_samples=2500, stride_samples=625)
    # Start indices: 0, 625, 1250, 1875, 2500 -> 5 windows
    assert windows.shape == (5, 2500)


def test_resample_ecg_polyphase():
    # Resample 300 Hz signal to 250 Hz
    fs_in = 300.0
    fs_out = 250.0
    duration = 5.0
    t_in = np.linspace(0, duration, int(duration * fs_in), endpoint=False)
    sig_in = np.sin(2 * np.pi * 5.0 * t_in).astype(np.float32)

    resampled = resample_ecg(sig_in, original_fs=fs_in, target_fs=fs_out)
    expected_len = int(duration * fs_out)
    assert len(resampled) == expected_len
