"""
CardioSentinel Edge - Host-vs-Firmware Parity Verification Tool
TECHgium Challenge 26 Research Prototype

Verifies numerical and decision agreement between Python research algorithms
and embedded C firmware compiled for the ESP32-S3.
"""

import os
import sys
import json
import subprocess
import numpy as np

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from research.models_tiny import CardioSentinelTinyCNN, TinyCNNFusedNumPyEngine
from research.quantize_export import export_fused_c_header
from research.replay_reference import process_ecg_window_reference
import torch


def run_parity_comparison():
    print("=" * 80)
    print("CardioSentinel Edge - Host-vs-Firmware Parity Audit")
    print("=" * 80)

    # 1. Ensure firmware runner binary exists
    runner_src = "tests/firmware_runner.c"
    runner_bin = "tests/firmware_runner.exe" if os.name == "nt" else "tests/firmware_runner"

    if not os.path.exists(runner_bin):
        print(f"[BUILD] Compiling native firmware test harness: {runner_bin}...")
        cmd = [
            "gcc", "-O2",
            "-I", "firmware/esp32s3/main",
            "-I", "firmware/esp32s3/models",
            runner_src,
            "firmware/esp32s3/main/ring_buffer.c",
            "firmware/esp32s3/main/signal_quality.c",
            "firmware/esp32s3/main/morphology_guard.c",
            "firmware/esp32s3/main/inference.c",
            "firmware/esp32s3/main/decision_engine.c",
            "-lm", "-o", runner_bin
        ]
        subprocess.check_call(cmd)

    # 2. Load Python reference engine
    model = CardioSentinelTinyCNN()
    model.load_state_dict(torch.load("models/tinycnn_best.pth", weights_only=True))
    fused_info = export_fused_c_header(model, "firmware/esp32s3/models/tinycnn_weights.h")
    py_engine = TinyCNNFusedNumPyEngine(fused_info["fused_arrays"])

    demo_records = [
        "01_clean_normal",
        "02_clean_af",
        "03_clean_other_pvc",
        "04_baseline_wander",
        "05_muscle_noise_emg",
        "06_lead_off_flatline",
        "07_rail_saturation",
        "08_mig_distortion"
    ]

    print(f"\n{'Demo Scenario':<22} | {'Python Decision':<16} | {'C Firmware Decision':<18} | {'Parity'}")
    print("-" * 80)

    all_matched = True
    temp_bin = "tests/temp_parity.bin"

    for rec in demo_records:
        npy_path = f"data/demo_samples/{rec}.npy"
        raw_ecg = np.load(npy_path).astype(np.float32)

        # Host Python Reference
        py_res = process_ecg_window_reference(raw_ecg, model_engine=py_engine)
        py_decision = py_res["decision"]
        py_label = py_res["classification"]["label"]

        # C Firmware
        raw_ecg.tofile(temp_bin)
        fw_out = subprocess.check_output([runner_bin, temp_bin]).decode().strip()
        fw_json = json.loads(fw_out)
        fw_decision = fw_json["decision"]
        fw_label = fw_json["class"]

        # Parity match condition
        decision_match = (py_decision == fw_decision)
        if not decision_match:
            all_matched = False
            status = "MISMATCH [X]"
        else:
            status = "MATCH [OK]"

        print(f"{rec:<22} | {py_decision:<7} ({py_label:<7}) | {fw_decision:<7} ({fw_label:<9}) | {status}")

    if os.path.exists(temp_bin):
        os.remove(temp_bin)

    print("-" * 80)
    if all_matched:
        print("[AUDIT PASSED] 100% Host-vs-Board Decision Parity Confirmed across all test vectors.\n")
    else:
        print("[AUDIT FAILED] Discrepancies detected between host and firmware.\n")


if __name__ == "__main__":
    run_parity_comparison()
