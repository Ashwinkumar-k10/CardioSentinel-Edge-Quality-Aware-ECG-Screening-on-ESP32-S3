# CardioSentinel Edge: Quality-Aware ECG Screening on ESP32-S3
### Safety-First, Low-Power, Uncertainty-Calibrated Wearable ECG Screening Research Prototype
**TECHgium Challenge 26**

[![Platform](https://img.shields.io/badge/Hardware-ESP32--S3%20%7C%20ADS1292R-blue.svg)](https://www.espressif.com/en/products/socs/esp32-s3)
[![Framework](https://img.shields.io/badge/Framework-ESP--IDF%20%7C%20FreeRTOS-green.svg)](https://github.com/espressif/esp-idf)
[![Edge AI](https://img.shields.io/badge/Edge%20AI-TFLite%20Micro%20%2F%20ESP--DL%20(INT8)-orange.svg)](https://github.com/espressif/esp-dl)
[![Dataset](https://img.shields.io/badge/Validation-PhysioNet%20CinC%202017%20%7C%20MIT--BIH-purple.svg)](https://physionet.org/content/challenge-2017/1.0.0/)
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
 │   • Quantized INT8 1D-CNN Rhythm Classifier             │
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

## 3. Five Distinct Engineering Innovations

### A. Adaptive Signal Quality Intelligence (ASQI)
Rather than a naive binary threshold, ASQI estimates distinct noise modes using deterministic $\mathcal{O}(N)$ linear-time heuristics:
* Dynamic range & rail clipping ($V_{\text{min}}, V_{\text{max}}$)
* Moving-median baseline drift
* High-frequency muscle interference & zero-crossing complexity
* Missing sample and lead-off contact status

### B. Morphology Integrity Guard (MIG)
A defensive software guard checking for noise-correction side effects. MIG preserves a clean copy of the untouched raw signal, compares it against the candidate-filtered signal at detected QRS complexes, and flags discrepancies in:
* R-peak timestamp shifts ($\Delta t_R$)
* QRS duration and amplitude attenuation
* Gross beat envelope distortion
* *Action:* If filtering alters suspicious morphology, the system declines automatic classification and routes the window to **REVIEW**.

### C. Lightweight Quantized 1D-CNN Classifier
* Optimized for the Xtensa LX7 dual-core architecture using INT8 SIMD vector instructions via ESP-NN / TFLite Micro.
* Trained on validated, record-disjoint splits of the PhysioNet/CinC 2017 Challenge dataset (Normal, AF, Other).
* Runs locally on the ESP32-S3 in $< 120\text{ ms}$ per evaluation window.

### D. Calibrated 3-Zone Uncertainty Triage
* **ACCEPT:** High-quality signal, calibrated prediction probability exceeds validation threshold, zero morphology guard warnings. (Provides research screening impression).
* **REVIEW:** Interpretable signal, but model confidence is borderline, class disagreement exists, or MIG detected that filtering distorted beat shape. Raw and processed snippets are preserved for clinician audit.
* **ABSTAIN:** Physically uninterpretable signal (lead-off, amplifier saturation, excessive motion). **Never classified as normal.**

### E. Traceable, Auditable Demonstration Dashboard
Maintains an end-to-end evidence trail displaying raw data, filtered signals, feature metrics, model confidence, and triage justification with FHIR R4-aligned demonstration structures.

---

## 4. Hardware Sizing & Memory Layout

* **Target Hardware:** ESP32-S3-WROOM-1 / N8R8 (8 MB Octal PSRAM, 8 MB SPI Flash).
* **Sampling Rate:** 250 Hz (2,500 samples per 10.0-second sliding window).
* **Stride:** 2.5 seconds (75% overlap; provides a refreshed assessment every 2.5 s after an initial 10-second buffer fill).

| Memory Component | Physical Memory Location | Allocated Size | Purpose |
|---|---|---|---|
| **SPI DMA Ping-Pong Buffers** | Internal DMA-capable RAM | ~2 KB | Hardware SPI buffer for zero-loss acquisition from ADS1292R |
| **Active 10 s Circular Window** | Internal Zero-Wait SRAM | ~10 KB | 2,500 samples × 4 bytes (float32) |
| **ASQI & MIG Working Buffers** | Internal Zero-Wait SRAM | ~15–20 KB | Scratchpad arrays for $\mathcal{O}(N)$ linear-time feature extraction |
| **Tensor Arena (TFLite Micro)** | Internal Zero-Wait SRAM | ~120–160 KB | INT8 activations and weights (prevents bus stalls) |
| **BLE Telemetry Outbound Queues**| External Octal PSRAM | ~64–128 KB | Telemetry packets and downsampled display waveforms |
| **Uncompressed Raw Audit Logs** | External Octal PSRAM / Flash | Multi-MB ring | Full raw traces preserved for all `REVIEW` and `ABSTAIN` events |

---

## 5. Answers to Critical Technical Questions (Jury Defense)

### Q1: Will ASQI + MIG overload the ESP32-S3?
**No.** All feature extraction operates in $\mathcal{O}(N)$ linear time. Computationally expensive metrics like standard Sample Entropy ($\mathcal{O}(N^2) \approx 6.25 \times 10^6$ ops) are strictly excluded in favor of line-length and zero-crossing heuristics.
$$\text{Total Compute Burst} = t_{\text{ASQI}} (\sim 12\text{ms}) + t_{\text{MIG}} (\sim 20\text{ms}) + t_{\text{AI}} (\sim 110\text{ms}) < 150\text{ ms} \ll 2,500\text{ ms stride}$$
This leaves **$> 93\%$ CPU idle time** for deep-sleep and low-power duty cycling.

### Q2: How do you prove that reducing false alarms does not miss real arrhythmias?
Through a **Paired Benchmark on Locked Identical Splits** and **Selective Risk-Coverage Curves**:
1. Both the Naive Baseline (quality-blind 1D-CNN) and CardioSentinel are tested against the exact same held-out patient-disjoint test set.
2. As uninterpretable noise is routed to `ABSTAIN`, the false alarm rate drops by $> 70\%$ while **arrhythmia sensitivity on the accepted cohort remains equal to or higher than baseline**.
3. Any ambiguous event is routed to `REVIEW` with raw waveforms preserved—it is **never silently dismissed as normal**.

---

## 6. Project Repository & Documentation Structure

* **Comprehensive MVP Plan:** [`CardioSentinel_ESP32S3_Only_Revised_MVP_Plan.md`](./CardioSentinel_ESP32S3_Only_Revised_MVP_Plan.md) — Complete 6-week engineering roadmap, firmware source layout, FreeRTOS task configuration, and benchmark test matrix.
* **Conceptual & Architectural Idea Plan:** [`CardioSentinel_ESP32S3_Only_Revised_Idea_Plan.md`](./CardioSentinel_ESP32S3_Only_Revised_Idea_Plan.md) — Detailed research background, design rationale, and competition defense strategy.

---

## 7. Disclaimer

CardioSentinel Edge is a research and engineering competition prototype developed for TECHgium Challenge 26. It is evaluated using public de-identified datasets (PhysioNet CinC 2017, MIT-BIH) and isolated benchtop ECG simulator sources. It is **not** a certified medical device and is not intended for human diagnosis, clinical intervention, or unapproved patient-connected monitoring.
