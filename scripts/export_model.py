"""
CardioSentinel Edge - Standalone Model Exporter Script
TECHgium Challenge 26 Research Prototype
"""

import os
import sys
import torch

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from research.models_tiny import CardioSentinelTinyCNN
from research.quantize_export import export_fused_c_header


def main():
    print("=" * 70)
    print("CardioSentinel Edge - Exporting Model to Embedded C Header")
    print("=" * 70)

    model_path = "models/tinycnn_best.pth"
    if not os.path.exists(model_path):
        print(f"[ERROR] Trained weights not found at: {model_path}")
        print("Please run `python scripts/train_baseline.py` first.")
        return

    model = CardioSentinelTinyCNN()
    model.load_state_dict(torch.load(model_path, weights_only=True))
    
    header_path = "firmware/esp32s3/models/tinycnn_weights.h"
    res = export_fused_c_header(model, header_path)

    print(f"\n[SUCCESS] Successfully exported to: {res['header_path']}")
    print(f"  Total Fused Parameters: {res['total_params']}")
    print(f"  Memory Footprint:       {res['size_kb']} KB (Resident in Internal SRAM)")


if __name__ == "__main__":
    main()
