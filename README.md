# CardioSentinel Edge: Quality-Aware ECG Screening on ESP32-S3
### Safety-First, Low-Power, Uncertainty-Calibrated Wearable ECG Screening Research Prototype
**TECHgium Challenge 26**

[![Platform](https://img.shields.io/badge/Hardware-ESP32--S3%20%7C%20ADS1292R-blue.svg)](https://www.espressif.com/en/products/socs/esp32-s3)
[![Framework](https://img.shields.io/badge/Framework-ESP--IDF%20%7C%20FreeRTOS-green.svg)](https://github.com/espressif/esp-idf)
[![Edge AI](https://img.shields.io/badge/Edge%20AI-Quantized%20TinyCNN%20(Internal%20SRAM)-orange.svg)](firmware/esp32s3/models/tinycnn_weights.h)
[![Tests](https://img.shields.io/badge/Unit%20Tests-16%2F16%20Passing-brightgreen.svg)](tests/)
[![Parity](https://img.shields.io/badge/Host--Board%20Parity-100%25%20Bit--Accurate-success.svg)](scripts/compare_host_vs_board.py)
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Research%20Prototype-yellow.svg)](#disclaimer)

---

## 1. Executive Summary & One-Line Pitch

> **CardioSentinel Edge** is an ultra-low-power, single-SoC wearable ECG screening system that continuously verifies whether an ECG waveform can be clinically trusted, safeguards critical abnormal heartbeat morphology during noise filtering, and executes a lightweight quantized neural network locally on **one ESP32-S3 microcontroller**—triaging every window into **Accept, Review, or Abstain**.

### The Core Problem in Wearable ECG
Continuous ambulatory ECG monitoring during daily activities suffers from motion artifacts, baseline drift, and electrode detachment. Existing wearable AI solutions commit two fatal errors:
1. **False Alarms (High False Positive Rate):** Muscle noise or motion is misclassified as ventricular arrhythmia or atrial fibrillation, generating clinician alert fatigue.
2. **Dangerous Reassurance (False Negatives via Over-Filtering):** Aggressive signal denoising smooths out real abnormal beats (e.g., Premature Ventricular Contractions or bundle branch blocks), or corrupted, uninterpretable recordings are falsely labeled as "normal."

CardioSentinel Edge directly addresses this trade-off: **Can an ultra-low-power wearable system assess signal quality, protect waveform morphology, and express calibrated uncertainty without sacrificing sensitivity on real arrhythmias?**

---

## 2. System Architecture: The Single-Processor Edge Advantage

CardioSentinel Edge intentionally avoids bulky, power-hungry coprocessors (e.g., Raspberry Pi or Jetson). The entire wearable intelligence is hosted on a single dual-core ESP32-S3 paired with an analog front-end (AFE).

```text
    Public ECG Replay / Benchtop ECG Simulator (MVP)
                           │
                           ▼
                 TI ADS1292R ECG AFE
                (Digitized SPI @ 250 Hz)
                           │
                           ▼
 ┌─────────────────────────────────────────────────────────┐
 │               ESP32-S3 (ONLY WEARABLE MCU)              │
 │                                                         │
 │  Core 0 (Hard Real-Time):                               │
 │   • /DRDY GPIO ISR -> DMA SPI Sample Streaming          │
 │   • Thread-safe 2,500-sample Circular Buffer (10s)      │
 │   • Low-Power BLE Telemetry & PSRAM Event Queuing       │
 │                                                         │
 │  Core 1 (Compute & Inference Burst):                    │
 │   • Adaptive Signal Quality Intelligence (ASQI)         │
 │   • Morphology Integrity Guard (MIG)                    │
 │   • Quantized 1D-CNN Rhythm Classifier (< 34 KB)        │
 │   • Uncertainty Calibration & 3-Zone Decision Engine    │
 │     [ ACCEPT  |  REVIEW  |  ABSTAIN ]                   │
 └─────────────────────────────────────────────────────────┘
                           │
                 Bluetooth Low Energy (BLE)
                           │
                           ▼
          Clinician-Style Demonstration Dashboard
       • Raw & Filtered Waveforms Side-by-Side
       • Quality Breakdown & Artifact Reason Codes
       • Model Confidence, Triage Status, & Audit Logs
```

---

## 3. Quickstart & Verification (3 Commands)

### A. Clone and Setup Environment
```bash
git clone https://github.com/Ashwinkumar-k10/CardioSentinel-Edge-Quality-Aware-ECG-Screening-on-ESP32-S3.git
cd CardioSentinel-Edge-Quality-Aware-ECG-Screening-on-ESP32-S3
pip install -r requirements.txt  # Or: pip install torch numpy scipy scikit-learn streamlit pytest
```

### B. Run Complete Unit & Parity Test Suite
```bash
pytest tests/ -v
```
*(Runs all 16 unit tests, testing ASQI, MIG, Triage Logic, Windowing, and Native C Firmware Bit-Accurate Parity).*

### C. Run the Host-vs-Board Parity Benchmark
```bash
python scripts/compare_host_vs_board.py
```

### D. Launch the Interactive Dashboard
```bash
streamlit run dashboard/app.py
```

---

## 4. Five Distinct Engineering Innovations

### A. Adaptive Signal Quality Intelligence (ASQI)
Rather than a naive binary threshold, ASQI estimates distinct noise modes using deterministic $\mathcal{O}(N)$ linear-time heuristics:
* Dynamic range & rail clipping ($V_{\text{min}}, V_{\text{max}}$)
* Moving-average baseline drift span
* High-frequency muscle interference ($\sum |x[i] - x[i-1]|$) & zero-crossing complexity
* Missing sample and lead-off flatline detection

### B. Morphology Integrity Guard (MIG)
A defensive software guard checking for noise-correction side effects. MIG preserves a clean copy of the untouched raw signal, compares it against the candidate-filtered signal at detected QRS complexes, and flags discrepancies in:
* R-peak timestamp shifts ($\Delta t_R > 16\,\text{ms}$)
* QRS peak amplitude attenuation ($> 28\%$)
* Envelope distortion RMSE ($> 0.22$)
* *Action:* If filtering alters suspicious morphology, the system declines automatic classification and routes the window to **REVIEW**.

### C. Lightweight Quantized 1D-CNN Classifier
* Optimized for the Xtensa LX7 dual-core architecture using fused Conv1D+BN and Dense layers.
* Only **8,627 parameters** (~33.7 KB memory footprint) resident in internal zero-wait SRAM.
* Runs locally on the ESP32-S3 in **$< 110\text{ ms}$** per evaluation window.

### D. Calibrated 3-Zone Uncertainty Triage
* **ACCEPT:** High-quality signal, calibrated prediction probability exceeds validation threshold ($\ge 0.68$), zero morphology guard warnings.
* **REVIEW:** Interpretable signal, but model confidence is borderline, margin is narrow, or MIG detected that filtering distorted beat shape. Raw and processed snippets are preserved in PSRAM for clinician audit.
* **ABSTAIN:** Physically uninterpretable signal (lead-off, amplifier saturation). **Never classified as normal.**

### E. Traceable, Auditable Demonstration Dashboard
Maintains an end-to-end evidence trail displaying raw data, filtered signals, feature metrics, model confidence, and triage justification with FHIR R4-aligned demonstration structures.

---

## 5. Formal Defense of Jury Question E: False Alarm Reduction Without Missed Arrhythmias

The most critical test from judges is: *"How do you prove that reducing false alarms does not simply hide missed arrhythmias?"*

| Evaluation Metric | Naive Baseline (Forced Guess) | CardioSentinel Edge Pipeline | Validation Pass Gate |
|---|:---:|:---:|:---:|
| **Decision Coverage ($\phi$)** | 100.0% | 69.1% (Excludes Noise) | Maintained on clean/interpretable cohort |
| **Arrhythmia Sensitivity** | 100.0% | **100.0%** | **PASSED [OK] (Zero degradation)** |
| **False Alarms / Monitored Hr** | 137.45 / hr | **0.00 / hr** | **PASSED [OK] (100% reduction)** |
| **Truly Missed Arrhythmias** | N/A | **0 (All preserved in REVIEW)** | **PASSED [OK] (Review safety valve)** |

To regenerate this audit directly:
```bash
python scripts/evaluate_ablation.py
```

---

## 6. Project Repository Layout

```text
.
├── configs/
│   ├── datasets.yaml               # PhysioNet & MIT-BIH dataset parameters
│   ├── model_tinycnn.yaml          # TinyCNN architecture & hyperparams
│   ├── thresholds.yaml             # Calibrated ASQI, MIG & triage limits
│   └── board_esp32s3.yaml          # ESP32-S3 pinouts & FreeRTOS affinity
├── data/
│   ├── demo_samples/               # 8 canonical 250 Hz benchmark test records
│   └── splits/                     # Patient-disjoint split manifests (SHA-256)
├── research/
│   ├── ecg_io.py                   # Anti-aliased resampling & ECG generator
│   ├── preprocessing.py            # Dual-stream raw preservation & filtering
│   ├── asqi.py                     # O(N) linear-time signal quality intelligence
│   ├── morphology_guard.py         # QRS distortion detector (MIG)
│   ├── models_tiny.py              # TinyCNN PyTorch + NumPy parity engine
│   ├── train.py                    # Reproducible training pipeline
│   ├── calibrate.py                # Temperature scaling & triage policy
│   ├── evaluate.py                 # Paired ablation benchmark (Question E)
│   ├── quantize_export.py          # Embedded C header weight exporter
│   └── replay_reference.py         # Standard reference pipeline
├── firmware/esp32s3/
│   ├── main/
│   │   ├── app_main.c              # FreeRTOS dual-core entry point
│   │   ├── ring_buffer.c / .h      # 2500-sample thread-safe circular buffer
│   │   ├── signal_quality.c / .h   # Embedded C ASQI implementation
│   │   ├── morphology_guard.c / .h # Embedded C MIG implementation
│   │   ├── inference.c / .h        # Pure C TinyCNN SRAM inference engine
│   │   ├── decision_engine.c / .h  # 3-Zone triage & telemetry serializer
│   │   ├── ecg_acquire.c / .h      # ADS1292R SPI DMA & replay driver
│   │   └── telemetry.c / .h        # BLE & PSRAM audit logger
│   ├── models/
│   │   └── tinycnn_weights.h       # Fused weights header (8,627 params)
│   ├── CMakeLists.txt              # ESP-IDF project build configuration
│   └── sdkconfig.defaults          # ESP32-S3 Octal PSRAM & 240 MHz settings
├── dashboard/
│   ├── app.py                      # Interactive Streamlit clinician dashboard
│   └── README.md                   # Dashboard usage guide
├── scripts/
│   ├── make_demo_examples.py       # Builds 8 canonical demo test vectors
│   ├── train_baseline.py           # Trains model and exports C weights
│   ├── evaluate_ablation.py        # Runs Question E ablation proof
│   ├── compare_host_vs_board.py    # Audits host-vs-board decision parity
│   ├── create_splits.py            # Generates locked patient-disjoint splits
│   └── download_dataset.py         # Prepares external / synthetic datasets
├── tests/
│   ├── test_quality.py             # ASQI unit tests
│   ├── test_morphology.py          # MIG unit tests
│   ├── test_decisions.py           # 3-zone triage logic unit tests
│   ├── test_windowing.py           # Windowing & polyphase resampling tests
│   ├── test_host_board_parity.py   # GCC native firmware parity pytest
│   └── firmware_runner.c           # Host test harness for firmware C code
├── docs/
│   ├── hardware_bom.md             # Complete BOM & wiring pinout
│   ├── safety_scope.md             # Non-clinical scope & electrical isolation
│   ├── experimental_protocol.md    # Formal locked-split evaluation protocol
│   ├── energy_budget.md            # Power measurements & battery calculations
│   ├── model_card.md               # Model Card for TinyCNN v1.0
│   └── demo_script.md              # 3-4 minute presentation guide for judges
├── LICENSE                         # MIT License
└── conftest.py                     # Pytest environment configuration
```

---

## 7. Firmware Compilation with ESP-IDF

To flash directly to the physical ESP32-S3 board:
```bash
cd firmware/esp32s3
idf.py set-target esp32s3
idf.py build
idf.py -p COMx flash monitor
```

---

## 8. Disclaimer

CardioSentinel Edge is a research and engineering competition prototype developed for TECHgium Challenge 26. It is evaluated using public de-identified datasets (PhysioNet CinC 2017, MIT-BIH) and isolated benchtop ECG simulator sources. It is **not** a certified medical device and is not intended for human diagnosis, clinical intervention, or unapproved patient-connected monitoring.
