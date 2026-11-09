"""
CardioSentinel Edge - Standalone Training & Baseline Script
TECHgium Challenge 26 Research Prototype
"""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from research.train import train_model
from research.quantize_export import export_fused_c_header
from research.models_tiny import CardioSentinelTinyCNN
import torch

def main():
    print("=" * 70)
    print("CardioSentinel Edge - Stage 1 & Stage 3: Model Training & Quantization")
    print("=" * 70)

    # 1. Train model
    res = train_model(epochs=20, output_dir="models")
    best_weights_path = res["best_weights_path"]

    # 2. Load model and export fused C header
    model = CardioSentinelTinyCNN(in_channels=1, num_classes=3)
    model.load_state_dict(torch.load(best_weights_path, weights_only=True))
    
    header_res = export_fused_c_header(
        model=model,
        output_header_path="firmware/esp32s3/models/tinycnn_weights.h"
    )

    print("\n[SUCCESS] Model training and embedded C header generation finished!")
    print(f"  Checkpoint: {best_weights_path}")
    print(f"  C Header:   {header_res['header_path']}")
    print(f"  Params:     {header_res['total_params']}")


if __name__ == "__main__":
    main()
