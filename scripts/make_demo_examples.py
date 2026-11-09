"""
CardioSentinel Edge - Demo Examples Generator
TECHgium Challenge 26 Research Prototype

Generates canonical 10-second (2500-sample @ 250 Hz) ECG waveforms covering
the 8 primary clinical and artifact verification scenarios for live jury demonstration.
"""

import os
import sys
import json
import numpy as np

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from research.ecg_io import generate_synthetic_ecg


def generate_all_demo_examples(output_dir: str = "data/demo_samples"):
    os.makedirs(output_dir, exist_ok=True)
    print(f"[DEMO_GEN] Generating benchmark demo records into {output_dir}...")

    # 1. Clean Normal Sinus Rhythm (HR = 72 bpm)
    ecg_normal, meta_normal = generate_synthetic_ecg(
        rhythm_type="normal", duration_sec=10.0, heart_rate_bpm=72.0, seed=101
    )
    
    # 2. Atrial Fibrillation (Irregular RR, chaotic f-waves, HR = 95 bpm)
    ecg_af, meta_af = generate_synthetic_ecg(
        rhythm_type="af", duration_sec=10.0, heart_rate_bpm=95.0, seed=102
    )

    # 3. Other Rhythm - Ectopic Premature Ventricular Contractions (PVC)
    ecg_other, meta_other = generate_synthetic_ecg(
        rhythm_type="other", duration_sec=10.0, heart_rate_bpm=76.0, seed=103
    )

    # 4. Severe Baseline Wander (Respiratory drift)
    ecg_wander, meta_wander = generate_synthetic_ecg(
        rhythm_type="normal", duration_sec=10.0, heart_rate_bpm=68.0,
        noise_type="baseline_wander", noise_amplitude=0.9, seed=104
    )

    # 5. High-Frequency Muscle Tremor / EMG Noise
    ecg_emg, meta_emg = generate_synthetic_ecg(
        rhythm_type="normal", duration_sec=10.0, heart_rate_bpm=80.0,
        noise_type="muscle_emg", noise_amplitude=0.35, seed=105
    )

    # 6. Disconnected Electrode / Flatline (Lead-off)
    ecg_leadoff, meta_leadoff = generate_synthetic_ecg(
        rhythm_type="normal", duration_sec=10.0,
        noise_type="lead_off", seed=106
    )

    # 7. Hardware Rail Saturation (ADC clipping)
    ecg_rail, meta_rail = generate_synthetic_ecg(
        rhythm_type="normal", duration_sec=10.0,
        noise_type="rail_saturation", seed=107
    )

    # 8. Morphology-Distorted Beat (High-frequency sharp feature that is attenuated by filtering, triggering MIG)
    ecg_mig, meta_mig = generate_synthetic_ecg(
        rhythm_type="other", duration_sec=10.0, heart_rate_bpm=76.0, seed=108
    )
    # Add sharp spike on 3rd beat peak (simulating pacemaker spike or notch)
    peak_samp = int(2.72 * 250)
    ecg_mig[peak_samp] += 1.4  # Sharp 1-sample spike that lowpass filter will attenuate by >50%

    records = {
        "01_clean_normal": (ecg_normal, meta_normal, "Clean Normal Sinus Rhythm (Expected: ACCEPT)"),
        "02_clean_af": (ecg_af, meta_af, "Atrial Fibrillation (Expected: ACCEPT AF)"),
        "03_clean_other_pvc": (ecg_other, meta_other, "Ventricular Ectopy / PVC (Expected: REVIEW/ACCEPT Other)"),
        "04_baseline_wander": (ecg_wander, meta_wander, "Respiratory Drift (Expected: REVIEW with ASQI flag)"),
        "05_muscle_noise_emg": (ecg_emg, meta_emg, "Muscle Tremor Noise (Expected: REVIEW with ASQI flag)"),
        "06_lead_off_flatline": (ecg_leadoff, meta_leadoff, "Electrode Disconnect (Expected: ABSTAIN Lead-Off)"),
        "07_rail_saturation": (ecg_rail, meta_rail, "ADC Rail Saturation (Expected: ABSTAIN Rail)"),
        "08_mig_distortion": (ecg_mig, meta_mig, "Filter-induced Distortion Test (Expected: REVIEW MIG)")
    }

    manifest = {}
    for name, (data, meta, desc) in records.items():
        npy_path = os.path.join(output_dir, f"{name}.npy")
        json_path = os.path.join(output_dir, f"{name}.json")
        np.save(npy_path, data)
        with open(json_path, "w") as f:
            json.dump({**meta, "description": desc, "file": f"{name}.npy"}, f, indent=2)
        manifest[name] = {"description": desc, "samples": len(data), "fs": 250}
        print(f"  Saved: {name}.npy ({len(data)} samples @ 250 Hz)")

    with open(os.path.join(output_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[DEMO_GEN] Successfully generated all 8 canonical test cases.")


if __name__ == "__main__":
    generate_all_demo_examples()
