"""
Pytest Suite for Host-vs-Board Parity
"""

import os
import json
import subprocess
import pytest
import numpy as np


@pytest.fixture(scope="module")
def firmware_binary():
    runner_bin = "tests/firmware_runner.exe" if os.name == "nt" else "tests/firmware_runner"
    if not os.path.exists(runner_bin):
        cmd = [
            "gcc", "-O2",
            "-I", "firmware/esp32s3/main",
            "-I", "firmware/esp32s3/models",
            "tests/firmware_runner.c",
            "firmware/esp32s3/main/ring_buffer.c",
            "firmware/esp32s3/main/signal_quality.c",
            "firmware/esp32s3/main/morphology_guard.c",
            "firmware/esp32s3/main/inference.c",
            "firmware/esp32s3/main/decision_engine.c",
            "-lm", "-o", runner_bin
        ]
        subprocess.check_call(cmd)
    return runner_bin


def test_firmware_normal_accept(firmware_binary):
    x = np.load("data/demo_samples/01_clean_normal.npy").astype(np.float32)
    temp_bin = "tests/temp_test_normal.bin"
    x.tofile(temp_bin)
    try:
        out = subprocess.check_output([firmware_binary, temp_bin]).decode().strip()
        data = json.loads(out)
        assert data["decision"] == "ACCEPT"
        assert data["class"] == "Normal"
        assert data["quality"]["usable"] is True
        assert data["mig"]["passed"] is True
    finally:
        if os.path.exists(temp_bin):
            os.remove(temp_bin)


def test_firmware_af_accept(firmware_binary):
    x = np.load("data/demo_samples/02_clean_af.npy").astype(np.float32)
    temp_bin = "tests/temp_test_af.bin"
    x.tofile(temp_bin)
    try:
        out = subprocess.check_output([firmware_binary, temp_bin]).decode().strip()
        data = json.loads(out)
        assert data["decision"] == "ACCEPT"
        assert data["class"] == "AF"
    finally:
        if os.path.exists(temp_bin):
            os.remove(temp_bin)


def test_firmware_lead_off_abstain(firmware_binary):
    x = np.load("data/demo_samples/06_lead_off_flatline.npy").astype(np.float32)
    temp_bin = "tests/temp_test_leadoff.bin"
    x.tofile(temp_bin)
    try:
        out = subprocess.check_output([firmware_binary, temp_bin]).decode().strip()
        data = json.loads(out)
        assert data["decision"] == "ABSTAIN"
        assert data["class"] == "UNINTERPRETABLE"
        assert data["quality"]["usable"] is False
    finally:
        if os.path.exists(temp_bin):
            os.remove(temp_bin)
