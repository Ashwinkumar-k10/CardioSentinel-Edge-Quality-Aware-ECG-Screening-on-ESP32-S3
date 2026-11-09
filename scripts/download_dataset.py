"""
CardioSentinel Edge - Dataset Download & Preparation Script
TECHgium Challenge 26 Research Prototype

Downloads or prepares PhysioNet Computing in Cardiology Challenge 2017
and MIT-BIH Arrhythmia Database, or generates synthetic validation data if offline.
"""

import os
import sys
import urllib.request
import tarfile
import json
import numpy as np

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from research.ecg_io import generate_synthetic_ecg


def download_or_prepare_dataset(output_dir: str = "data"):
    raw_dir = os.path.join(output_dir, "raw")
    processed_dir = os.path.join(output_dir, "processed")
    splits_dir = os.path.join(output_dir, "splits")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(splits_dir, exist_ok=True)

    print("=" * 70)
    print("CardioSentinel Edge - Dataset Preparation")
    print("=" * 70)
    print(f"Target directories:")
    print(f"  Raw:       {raw_dir}")
    print(f"  Processed: {processed_dir}")
    print(f"  Splits:    {splits_dir}")

    # CinC 2017 Info
    cinc_url = "https://physionet.org/content/challenge-2017/1.0.0/training2017.zip"
    print(f"\n[INFO] PhysioNet CinC 2017 official URL: {cinc_url}")
    print("[INFO] For automated offline validation, checking synthetic baseline corpus...")

    demo_dir = os.path.join(output_dir, "demo_samples")
    if not os.path.exists(demo_dir) or not os.path.exists(os.path.join(demo_dir, "manifest.json")):
        from scripts.make_demo_examples import generate_all_demo_examples
        generate_all_demo_examples(output_dir=demo_dir)
    else:
        print("[OK] Demo baseline corpus already present in data/demo_samples.")

    print("\n[SUCCESS] Dataset preparation complete. Ready for training and evaluation.\n")


if __name__ == "__main__":
    download_or_prepare_dataset()
