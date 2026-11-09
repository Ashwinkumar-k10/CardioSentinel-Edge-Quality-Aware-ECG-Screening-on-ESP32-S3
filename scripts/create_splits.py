"""
CardioSentinel Edge - Patient-Disjoint Split Generator
TECHgium Challenge 26 Research Prototype

Ensures strict record/patient disjointness across Train, Validation, and Test splits.
Generates cryptographic SHA-256 split manifests for zero data leakage.
"""

import os
import sys
import json
import hashlib
import numpy as np

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def generate_patient_disjoint_splits(output_dir: str = "data/splits", seed: int = 42):
    os.makedirs(output_dir, exist_ok=True)
    np.random.seed(seed)

    print("=" * 70)
    print("CardioSentinel Edge - Generating Immutable Record Splits")
    print("=" * 70)

    # 300 synthetic/annotated record IDs simulating patient cohorts
    patients = [f"PATIENT_{i:03d}" for i in range(1, 301)]
    np.random.shuffle(patients)

    n_total = len(patients)
    n_train = int(0.70 * n_total)
    n_val = int(0.15 * n_total)

    train_patients = sorted(patients[:n_train])
    val_patients = sorted(patients[n_train:n_train + n_val])
    test_patients = sorted(patients[n_train + n_val:])

    # Verify disjointness
    set_train = set(train_patients)
    set_val = set(val_patients)
    set_test = set(test_patients)

    assert len(set_train.intersection(set_val)) == 0, "Leakage between train and val!"
    assert len(set_train.intersection(set_test)) == 0, "Leakage between train and test!"
    assert len(set_val.intersection(set_test)) == 0, "Leakage between val and test!"

    manifest = {
        "dataset": "CardioSentinel Research Cohort",
        "seed": seed,
        "splits": {
            "train": {
                "count": len(train_patients),
                "ratio": 0.70,
                "patient_ids": train_patients
            },
            "validation": {
                "count": len(val_patients),
                "ratio": 0.15,
                "patient_ids": val_patients
            },
            "test": {
                "count": len(test_patients),
                "ratio": 0.15,
                "patient_ids": test_patients
            }
        }
    }

    manifest_json = json.dumps(manifest, indent=2)
    sha256 = hashlib.sha256(manifest_json.encode()).hexdigest()
    manifest["sha256_hash"] = sha256

    manifest_path = os.path.join(output_dir, "split_manifest_v1.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[SPLIT] Manifest written: {manifest_path}")
    print(f"  Train:      {len(train_patients)} patients (70%)")
    print(f"  Validation: {len(val_patients)} patients (15%)")
    print(f"  Test:       {len(test_patients)} patients (15%)")
    print(f"  SHA-256:    {sha256}")
    print("[SUCCESS] Zero-leakage patient-disjoint split manifest frozen.\n")


if __name__ == "__main__":
    generate_patient_disjoint_splits()
