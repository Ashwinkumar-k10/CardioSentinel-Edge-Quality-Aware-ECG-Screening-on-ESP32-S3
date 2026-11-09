"""
CardioSentinel Edge - Model Training Pipeline
TECHgium Challenge 26 Research Prototype
"""

import os
import json
import yaml
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
from typing import Dict, Any, Tuple, Optional

from research.models_tiny import CardioSentinelTinyCNN
from research.ecg_io import generate_synthetic_ecg, slice_sliding_windows
from research.preprocessing import prepare_dual_stream_ecg


def create_synthetic_training_corpus(
    n_records_per_class: int = 150,
    seed: int = 42
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Creates a verified, reproducible research corpus containing:
    0: Normal Sinus Rhythm (with sinus arrhythmia)
    1: Atrial Fibrillation (chaotic RR and f-waves)
    2: Other Rhythm (Premature Ventricular Contractions)
    """
    np.random.seed(seed)
    all_windows_raw = []
    all_windows_norm = []
    all_labels = []

    classes = [("normal", 0), ("af", 1), ("other", 2)]
    for rhythm, class_id in classes:
        for i in range(n_records_per_class):
            hr = np.random.uniform(55, 110)
            noise_type = None
            if np.random.rand() < 0.25:
                noise_type = np.random.choice(["baseline_wander", "muscle_emg"])
            
            # Raw 10-second window @ 250 Hz
            raw, _ = generate_synthetic_ecg(
                rhythm_type=rhythm,
                duration_sec=10.0,
                sampling_rate=250,
                heart_rate_bpm=hr,
                noise_type=noise_type,
                noise_amplitude=float(np.random.uniform(0.05, 0.20)),
                seed=seed + i * 10 + class_id
            )
            # Preprocess
            _, filtered = prepare_dual_stream_ecg(raw, fs=250.0)
            
            # Normalize to zero mean, unit variance for neural network training
            norm_ecg = (filtered - np.mean(filtered)) / (np.std(filtered) + 1e-6)
            all_windows_raw.append(raw[np.newaxis, :])    # [1, 2500] Raw
            all_windows_norm.append(norm_ecg[np.newaxis, :]) # [1, 2500] Norm
            all_labels.append(class_id)

    X_raw = np.array(all_windows_raw, dtype=np.float32)
    X_norm = np.array(all_windows_norm, dtype=np.float32)
    y = np.array(all_labels, dtype=np.int64)

    indices = np.arange(len(y))
    np.random.shuffle(indices)
    return X_raw[indices], X_norm[indices], y[indices]


def train_model(
    config_path: str = "configs/model_tinycnn.yaml",
    output_dir: str = "models",
    epochs: int = 25,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Trains CardioSentinel TinyCNN with class-weighting and early stopping.
    """
    torch.manual_seed(seed)
    np.random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)

    # 1. Generate or load training data
    print("[TRAIN] Preparing training & validation datasets...")
    X_raw, X_norm, y = create_synthetic_training_corpus(n_records_per_class=120, seed=seed)
    
    n_samples = len(y)
    n_train = int(0.70 * n_samples)
    n_val = int(0.15 * n_samples)

    X_train, y_train = X_norm[:n_train], y[:n_train]
    X_val, y_val = X_norm[n_train:n_train+n_val], y[n_train:n_train+n_val]
    # For testing, save RAW windows so ASQI + MIG test authentic input
    X_test_raw, y_test = X_raw[n_train+n_val:], y[n_train+n_val:]

    train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
    val_ds = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))

    train_loader = DataLoader(train_ds, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=32, shuffle=False)

    # 2. Initialize Model
    model = CardioSentinelTinyCNN(in_channels=1, num_classes=3)
    class_weights = torch.tensor([1.0, 2.5, 2.0], dtype=torch.float32)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = optim.Adam(model.parameters(), lr=0.002, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=3)

    best_val_loss = float('inf')
    best_weights_path = os.path.join(output_dir, "tinycnn_best.pth")

    print(f"[TRAIN] Training TinyCNN for {epochs} epochs...")
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        correct = 0
        total = 0

        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            out = model(batch_x)
            loss = criterion(out, batch_y)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * len(batch_y)
            preds = torch.argmax(out, dim=1)
            correct += (preds == batch_y).sum().item()
            total += len(batch_y)

        train_loss /= total
        train_acc = correct / total

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                out = model(batch_x)
                loss = criterion(out, batch_y)
                val_loss += loss.item() * len(batch_y)
                preds = torch.argmax(out, dim=1)
                val_correct += (preds == batch_y).sum().item()
                val_total += len(batch_y)

        val_loss /= val_total
        val_acc = val_correct / val_total
        scheduler.step(val_loss)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), best_weights_path)

        if epoch % 5 == 0 or epoch == epochs:
            print(f"  Epoch {epoch:02d}/{epochs:02d} | Train Loss: {train_loss:.4f} Acc: {train_acc*100:.1f}% | Val Loss: {val_loss:.4f} Acc: {val_acc*100:.1f}%")

    print(f"[TRAIN] Training complete. Best weights saved to: {best_weights_path}")
    
    # Save held-out test split for evaluation
    np.savez_compressed(
        os.path.join(output_dir, "held_out_test_split.npz"),
        X_test=X_test_raw,
        y_test=y_test,
        X_val=X_val,
        y_val=y_val
    )

    return {
        "best_weights_path": best_weights_path,
        "val_loss": best_val_loss,
        "n_train": len(X_train),
        "n_val": len(X_val),
        "n_test": len(X_test_raw)
    }


if __name__ == "__main__":
    train_model(epochs=20)
