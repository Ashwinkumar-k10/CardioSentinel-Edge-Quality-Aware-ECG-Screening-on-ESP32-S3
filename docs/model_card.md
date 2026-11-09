# Model Card — CardioSentinel TinyCNN v1.0
**TECHgium Challenge 26 Research Prototype**

## 1. Model Details
- **Architecture:** 1D Convolutional Neural Network (3 Conv Blocks with BatchNorm & MaxPool, Global Average Pooling, 2-layer MLP Head)
- **Parameters:** 8,627 fused parameters (~33.7 KB float32, < 9 KB INT8)
- **Target Hardware:** ESP32-S3 Xtensa LX7 (Internal Zero-Wait SRAM resident)
- **Input Dimensions:** 1 channel × 2,500 samples (10.0 seconds @ 250 Hz)
- **Output Classes:**
  - `0`: Normal Sinus Rhythm (Normal)
  - `1`: Atrial Fibrillation (AF)
  - `2`: Other Arrhythmia / Ectopy (Other)

---

## 2. Intended Use & Context
- **Intended Use:** On-device screening and alert triaging on low-power wearable edge devices.
- **Out of Scope:** Clinical diagnosis, direct emergency intervention, single-lead pediatric cardiology, or unreviewed automatic medication dosing.

---

## 3. Training & Validation Data
- **Training Cohort:** Record-disjoint splits of the PhysioNet / Computing in Cardiology Challenge 2017 Dataset and MIT-BIH Arrhythmia Database.
- **Data Augmentation:** Baseline wander injection, Gaussian muscle noise, electrode motion artifacts.
- **Loss Function:** Class-weighted cross-entropy / focal loss.

---

## 4. Calibration & Triage Thresholds
- **Temperature Scaling Parameter ($T$):** 1.1500
- **Acceptance Confidence Threshold ($\tau_{\text{accept}}$):** 0.6800
- **Ambiguity Margin Threshold ($\tau_{\text{margin}}$):** 0.1500
- **Abstention Policy:** Strictly enforced whenever ASQI indicates lead-off or rail saturation, or MIG indicates filter distortion.
