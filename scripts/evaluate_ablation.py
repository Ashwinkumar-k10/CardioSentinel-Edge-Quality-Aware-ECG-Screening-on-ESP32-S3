"""
CardioSentinel Edge - Paired Ablation Benchmark & Question E Proof
TECHgium Challenge 26 Research Prototype
"""

import os
import sys
import json
import numpy as np
import torch

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from research.models_tiny import CardioSentinelTinyCNN
from research.evaluate import run_paired_ablation_benchmark


def main():
    print("=" * 75)
    print("CardioSentinel Edge - Paired Ablation Benchmark (Question E Defense)")
    print("=" * 75)

    test_split_path = os.path.join(REPO_ROOT, "models", "held_out_test_split.npz")
    if not os.path.exists(test_split_path):
        print(f"[ERROR] Held-out test split not found at: {test_split_path}")
        print("Please run `python scripts/train_baseline.py` first.")
        return

    data = np.load(test_split_path)
    X_test = data["X_test"]
    y_test = data["y_test"]

    print(f"[BENCHMARK] Loaded held-out test split: {len(y_test)} windows (10.0s @ 250 Hz)")

    # Load trained model
    model = CardioSentinelTinyCNN(in_channels=1, num_classes=3)
    weights_path = os.path.join(REPO_ROOT, "models", "tinycnn_best.pth")
    model.load_state_dict(torch.load(weights_path, weights_only=True))
    model.eval()

    def model_predict_fn(ecg_window: np.ndarray) -> np.ndarray:
        t_x = torch.from_numpy(ecg_window[np.newaxis, np.newaxis, :]).float()
        with torch.no_grad():
            out = model(t_x)
        return out.squeeze(0).cpu().numpy()

    benchmark_res = run_paired_ablation_benchmark(
        X_test=X_test,
        y_test=y_test,
        model_predict_fn=model_predict_fn,
        confidence_thresh=0.62
    )

    report_dir = os.path.join(REPO_ROOT, "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, "ablation_benchmark_results.json")
    with open(report_file, "w") as f:
        json.dump(benchmark_res, f, indent=2)

    nb = benchmark_res["naive_baseline"]
    cp = benchmark_res["cardiosentinel_pipeline"]
    gates = benchmark_res["pass_gates"]

    print("\n" + "-" * 75)
    print("PAIRED BENCHMARK RESULTS TABLE (Question E Verification)")
    print("-" * 75)
    print(f"{'Evaluation Metric':<32} | {'Naive Baseline':<18} | {'CardioSentinel Edge':<20}")
    print("-" * 75)
    print(f"{'Decision Coverage (phi)':<32} | {nb['coverage_pct']:<17.1f}% | {cp['coverage_pct']:<19.1f}%")
    print(f"{'Arrhythmia Sensitivity':<32} | {nb['arrhythmia_sensitivity_pct']:<17.1f}% | {cp['arrhythmia_sensitivity_pct']:<19.1f}%")
    print(f"{'False Alarms / Monitored Hr':<32} | {nb['false_alarms_per_hour']:<18.2f} | {cp['false_alarms_per_hour']:<20.2f}")
    print(f"{'False Alarm Reduction':<32} | {'0.0% (Reference)':<18} | {cp['false_alarm_reduction_pct']:.1f}%")
    print(f"{'Truly Missed Arrhythmias':<32} | {'N/A':<18} | {cp['truly_missed_arrhythmias_in_accept']} (All in Review)")
    print("-" * 75)
    print("SUCCESS GATES AUDIT:")
    for gate_name, passed in gates.items():
        status = "PASSED [OK]" if passed else "FAILED [X]"
        print(f"  • {gate_name:<38}: {status}")
    print("-" * 75)
    print(f"[REPORT] Saved full validation audit to: {report_file}\n")


if __name__ == "__main__":
    main()
