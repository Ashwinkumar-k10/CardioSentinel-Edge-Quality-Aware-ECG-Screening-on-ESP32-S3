# CardioSentinel — Revised ESP32-S3-Only MVP Development Plan
## TECHgium Challenge 26 | Quality-aware, uncertainty-calibrated ECG screening research prototype

> **Version:** 3.0 — 2026-11-09  
> **Architecture decision:** **One ESP32-S3 is the only main embedded processor**. No Raspberry Pi, Jetson, second AI accelerator, second MCU, or wearable-to-cloud inference dependency in the primary design. The **ADS1292R is an ECG analog front end, not a second processor**. A laptop/PC is permitted for **model training, test analysis, dashboard viewing, and development**, not as a hidden second wearable inference processor.  
> **Status:** Development plan, not evidence of a built or medically validated device.  
> **Scope & safety:** Public/de-identified ECG, synthetic artifacts and simulator/AFE test signals only. No human electrode connection with homemade hardware during MVP. Not for medical diagnosis, emergencies or unsupervised care.

---

## 1. Final project decision

**Selected design:** ADS1292R ECG AFE → ESP32-S3 → low-cost BLE/Wi-Fi telemetry → laptop dashboard. ECG quality checking, low-cost morphology integrity checks, the lightweight rhythm classifier and the final screening decision should **run on the ESP32-S3**, insofar as profiling demonstrates feasibility. The laptop only displays and logs the output. All model **training** happens offline on a laptop/desktop, and the trained model is compressed/deployed to the ESP32-S3.

**Why:** A compact wearable prioritizes energy, cost, easy integration, demonstrability and reliable interpretation over a larger AI architecture. More AI compute is not automatically better screening. Keep an optional hybrid/cloud architecture as a **future research option**, only if measured accuracy, memory, latency or energy limits force reconsideration.

**Important engineering exception:** The first **software validation stage** runs the same algorithm on a laptop so it can be trained and rigorously checked; this does not make the final wearable a hybrid architecture. If the selected GRU cannot be deployed on the ESP32-S3 with the available embedded runtime, replace it with a **quantized compact 1D-CNN or CNN+TCN**, while preserving the same quality/guard/triage features. Do not claim full on-device GRU unless it runs and is measured on the board.

### Nonnegotiable design priorities (highest first)
1. Preserve clinically meaningful waveform evidence and abstain when uncertain.
2. Demonstrate reproducible accuracy and reductions in false alarms **at measured coverage**.
3. Fit inference within the actual ESP32-S3 board's SRAM/PSRAM/flash budget.
4. Measure low-power operation and realistic battery life.
5. Keep cost, development complexity and latency practical.
6. Add advanced AI only when it produces an independently measured improvement.

---

## 2. Revised architecture

```text
              PUBLIC ECG REPLAY / ECG SIMULATOR (MVP)
                              |
                              v
               ADS1292R ECG analog front end
                    (SPI digital samples)
                              |
                              v
              +----------------------------------+
              |         ESP32-S3 (ONLY MCU)      |
              |                                  |
              |  A. Input validation + ring buf  |
              |  B. Fixed-point/bounded filters  |
              |  C. Lightweight SQI / ASQI       |
              |  D. Morphology Integrity Guard   |
              |  E. Tiny quantized ECG classifier|
              |  F. Calibrated decision policy   |
              |     ACCEPT / REVIEW / ABSTAIN    |
              |  G. Logging + BLE/Wi-Fi telemetry|
              +----------------------------------+
                              |
                        BLE or Wi-Fi
                              |
                              v
                 LAPTOP / MOBILE DEMO UI
              waveform + quality + reasons
              (no mandatory cloud inference)

OFFLINE DEVELOPMENT ONLY:
PhysioNet data -> preprocessing -> reproducible training ->
calibration -> quantization -> firmware integration -> board tests
```

**Clarification:** A prerecorded signal played directly into a simulator, a physical AFE internal test signal, and replay of a digitally saved ECG window through ESP32 firmware are **three different demonstration modes**. Internal AFE test signals validate acquisition but **do not demonstrate realistic arrhythmia classification**. An ECG simulator tests acquisition; digital dataset replay tests algorithms. Clearly label the mode shown to judges.

---

## 3. Functional scope: what must work

| Requirement | What to implement | Demo / pass condition |
|---|---|---|
| ECG input | 250 samples/s target; timestamp and overflow checks | Sample counter and verified waveform capture from simulator/test mode |
| Replay mode | Run a saved public ECG window through identical algorithm path | Same windows processed repeatedly with fixed decisions |
| Quality assessment | Baseline drift, clipping/flatline, mains/EMG-like noise proxies, beat detector consistency | Detect labeled/synthetic corruptions and report reason codes |
| Morphology Integrity Guard | Retain raw window; compare before/after R-peaks and QRS features | Dangerous processing alterations lead to REVIEW rather than silent normalization |
| Classifier | Small, quantized 1D-CNN first; CNN+GRU only if board-verified | On-device class scores, memory map and board latency logs |
| Decision engine | ACCEPT / REVIEW / ABSTAIN with evidence | Low quality never becomes 'confidently normal' |
| Connectivity | BLE notifications or throttled Wi-Fi streaming | Dashboard receives timestamps, scores and review reasons |
| Dashboard | Raw/processed plots, quality, class scores, decisions, saved episodes | Judges can inspect sample-to-decision chain |
| Experiments | Fixed dataset splits, error audit and baseline comparison | Saved reproducible report including failures |
| Energy | Real board current measurement across operating modes | Battery estimate from measured average current, not guesses |

### Explicitly out of scope for MVP
- Human clinical testing, clinical diagnosis, emergency intervention, regulatory approval.
- Guaranteed '100% VT/PVC preservation' or guaranteed zero false negatives.
- Training large models directly on ESP32-S3.
- Continuous Wi-Fi streaming at maximum radio duty cycle **and** assuming ultra-low current.
- Mandatory Raspberry Pi / Jetson / cloud inference / multi-processor hybrid solution.
- A six-class output assembled by silently relabeling incompatible datasets.

---

## 4. Proposed hardware, memory map, and interfaces

| Part | Proposed role | Key implementation note |
|---|---|---|
| **ESP32-S3 dev board with PSRAM** | One main processor, inference, SPI, logging, wireless | Target **ESP32-S3-WROOM-1 / N8R8 (8 MB Octal PSRAM, 8 MB Flash)**. Prioritize internal SRAM for the zero-wait-state AI/DSP pipeline; use PSRAM as safety-net memory for logs and BLE buffers. |
| **ADS1292R-based evaluation board** | Two-channel-capable ECG analog front end | Connected via SPI with hardware `/DRDY` interrupt line. Use published reference/evaluation hardware and documented test modes; confirm 3.3V logic levels. |
| **ECG waveform simulator / known test source** | Bench-only signal source | No homemade USB/mains-connected electrodes on a person. |
| **Battery + protected regulation** | Later portable demonstrator | Sized to measured current, peak radio bursts, and LDO dropout. |
| **Optional microSD / external flash** | Store representative raw windows | Prefer SPI Flash / internal partition table for MVP. |
| **USB cable** | Firmware flashing / serial debug | Connect only in simulator/test-signal bench mode. |

### 4.1 Memory allocation architecture (Internal SRAM vs. External PSRAM)

The ESP32-S3 features 512 KB internal SRAM. Accounting for I-RAM, D-RAM, FreeRTOS kernel, and the Bluetooth controller stack (~70–100 KB), approximately 250–320 KB heap remains. The pipeline memory layout is strictly structured:

| Memory component | Memory space | Allocation size | Purpose & Rationale |
|---|---|---|---|
| **SPI DMA Ping-Pong Buffers** | Internal DMA RAM | ~2 KB (2 × 1 KB) | Required by hardware DMA engine for ADS1292R SPI transactions. |
| **Active Sliding ECG Window** | Internal SRAM | ~10 KB | 2,500 samples (10 s @ 250 Hz) × 4 bytes (float32). Zero-wait SRAM. |
| **ASQI & MIG Working Buffers** | Internal SRAM | ~15–20 KB | Scratchpad arrays for $\mathcal{O}(N)$ linear-time feature extraction. |
| **TFLite Micro / ESP-DL Tensor Arena** | Internal SRAM | ~120–160 KB | INT8 quantized 1D-CNN activations. Fast SRAM access prevents compute stalls. |
| **Telemetry & BLE Outbound Queues** | External PSRAM | ~64–128 KB | Queues status packets, downsampled waveforms, and alerts without choking heap. |
| **Uncompressed Raw Audit Log** | External PSRAM | Multi-MB ring buffer | Preserves full raw episodes when flagged as REVIEW or ABSTAIN for PC audit. |

**Power-planning principle:** Latency and power are different constraints. '32.8 ms per 10 seconds' is only a **historical unverified proposal number**, not an ESP32-S3 guarantee. A 110 mAh cell will *not* necessarily provide 24.6 hours; measure active acquisition, AI bursts, sleep, storage and BLE/Wi-Fi usage first. For example, an **illustrative** average draw of 8 mA yields a theoretical 110/8 ≈ 13.75 hours before usable-capacity and conversion losses; this example is **not** a board measurement.

**Radio recommendation:** Start with **BLE** for compact periodic results and compressed/downsampled waveform updates. Enable Wi-Fi only for convenient local demonstration and separately measure its energy cost. Never claim that BLE and Wi-Fi have equal current draw.

---

## 5. AI plan specifically for ESP32-S3

### 5.1 Model-selection ladder — do not begin with the largest model

1. **Baseline:** simple compact 1D-CNN with ~10-second input windows, used to establish real performance.
2. **Preferred embedded model:** quantized, compact 1D-CNN (INT8 as supported by selected runtime), trained and calibrated with the same data protocol.
3. **Conditional upgrade:** CNN + *small* GRU if full operator support, RAM footprint, power and latency work on target board. Otherwise test compact **TCN/dilated-convolution** architecture with supported operators.
4. **Future only:** larger Transformer/second processor/cloud inference if quantified benefits justify a redesign.

Do not carry forward the earlier 335,202-parameter CNN+GRU as a **proven deployed MCU model**. It is an architectural candidate, and activations/operator availability may make it unsuitable. The prior published proposal's model/accuracy/latency table is unverified until code, data splits and actual board traces are supplied.

### 5.2 Suggested on-device inference pipeline

```text
Acquire 250 Hz -> 10 s / 2500-sample ring buffer ->
lightweight baseline/noise checks -> quality feature vector ->
optional conservative filtering -> morphology integrity check ->
quantized classifier -> calibrated decision rules -> event logging
```

A 10-second **buffered** window is not instantaneous detection: the system must first collect the window. Report separately (a) window acquisition time, (b) compute time, (c) decision refresh interval and (d) wireless/UI delay. If the final board cannot process a 10-second window with safe latency/memory headroom, reduce model size or change the window/stride after retraining and reevaluation.

### 5.3 Input and labels
- **PhysioNet/CinC 2017:** recording labels `N` (Normal), `A` (AF), `O` (Other), `~` (Noisy); use `~` carefully for uninterpretable quality, not as a rhythm class.
- **MIT-BIH:** annotated beat-level research for ectopy/morphology integrity; **not** the same target label taxonomy as CinC 2017.
- Preserve original sample rate; anti-aliasing before resampling to 250 Hz.
- Fix train/validation/test splits **by patient when available**, or record groups with the limitation documented; never mix windows from one record across splits.
- Validate deployment with **real held-out traces** as well as synthetic artifacts.

### 5.4 Calibration and triage
- Fit any decision thresholds and confidence calibration **only** on training/validation data.
- On-device implementation may use low-cost stored calibration parameters and deterministic thresholds.
- **ACCEPT:** adequate quality, supported input and calibrated confidence, no unresolved morphology concern.
- **REVIEW:** possible important rhythm, ambiguous class, signal-processing distortion, or out-of-distribution concern.
- **ABSTAIN:** unusable signal, contact fault or unsupported input. Never reinterpret an abstention as 'normal'.
- Report **coverage** together with precision/recall; a system that abstains on everything has not solved false alarms.

---

## 6. ASQI and Morphology Integrity Guard: practical embedded version

### 6.1 Algorithmic complexity and feature selection
To prevent processor starvation, all preprocessing and feature extraction modules must run in strictly bounded $\mathcal{O}(N)$ linear time:
- **ASQI v1:**
  - *Dynamic Range & Saturation:* Linear scan for ADC rail clipping ($V_{\text{min}}, V_{\text{max}}$) and flatline zero-variance conditions.
  - *Baseline Wander:* Moving median or lightweight IIR high-pass difference ($\mathcal{O}(N)$).
  - *Complexity & Noise Proxy:* Curve line-length $\sum |x[i] - x[i-1]|$ and zero-crossing count.
  - *Algorithmic Exclusions:* **Standard Sample Entropy is strictly excluded** because its $\mathcal{O}(N^2)$ complexity ($6.25 \times 10^6$ operations on $N=2,500$ samples) would monopolize the MCU.
  - *Output:* Compact C struct with `quality_score` (fixed-point Q15), `artifact_flags`, `usable`, `reason_codes`.

- **MIG v1:**
  - *Raw Preservation:* Raw input window is preserved in RAM untouched before any filtering.
  - *Morphology Comparison:* Compares raw vs candidate-filtered signals at detected QRS locations. Checks R-peak timestamp displacement ($\Delta t_R$), peak amplitude attenuation, and QRS envelope width difference.
  - *Disagreement Action:* If relative distortion exceeds the validation-calibrated boundary, automatic normal classification is suppressed and the window is routed to `REVIEW`.

- **Granular Execution Measurement:**
  Firmware must instrument and log individual execution latencies using the ESP32 hardware cycle counter:
  $$\text{Total Compute Budget} = t_{\text{ASQI}} + t_{\text{MIG}} + t_{\text{AI}} \ll 2500\text{ ms}$$
  Targeting $t_{\text{ASQI}} < 15\text{ ms}$, $t_{\text{MIG}} < 25\text{ ms}$, $t_{\text{AI}} < 120\text{ ms}$, ensuring $> 85\%$ CPU idle time for power management.

### 6.2 Precise Triage Definitions (Calibrated, not Arbitrary)
- **ABSTAIN (Uninterpretable Signal):**
  - Triggered by physical/electrical invalidity: hardware lead-off detection from ADS1292R, sustained ADC rail saturation, or severe packet drop.
  - The model does not execute. The system outputs `ABSTAIN` with explicit reason codes (`LEAD_OFF`, `RAIL_SATURATION`). It is **never** counted as normal.
- **REVIEW (Interpretable but Ambiguous):**
  - Triggered by medical or model ambiguity: prediction margin falls below temperature-calibrated confidence cutoff, or MIG flags significant filter-induced waveform discrepancy.
  - Full raw and processed waveform snapshots are preserved in PSRAM for clinical inspection.
- **Calibration Requirement:** Decision thresholds must be fitted using Platt scaling / temperature scaling on the validation split. No arbitrary hardcoded cutoffs may be claimed as clinically validated.

---

## 7. Software and firmware modules

```text
cardiosentinel/
├── README.md
├── LICENSE
├── configs/
│   ├── datasets.yaml
│   ├── model_tinycnn.yaml
│   ├── thresholds.yaml
│   └── board_esp32s3.yaml
├── data/                     # ignored raw dataset files
│   ├── raw/
│   ├── processed/
│   └── splits/              # versioned split manifests
├── research/
│   ├── ecg_io.py
│   ├── preprocessing.py
│   ├── asqi.py
│   ├── morphology_guard.py
│   ├── models_tiny.py
│   ├── train.py
│   ├── calibrate.py
│   ├── evaluate.py
│   ├── quantize_export.py
│   └── replay_reference.py
├── firmware/esp32s3/
│   ├── main/                # ESP-IDF source
│   │   ├── ecg_acquire.c
│   │   ├── ring_buffer.c
│   │   ├── signal_quality.c
│   │   ├── morphology_guard.c
│   │   ├── inference.c
│   │   ├── decision_engine.c
│   │   ├── telemetry.c
│   │   └── app_main.c
│   ├── models/              # quantized model + metadata
│   └── sdkconfig.defaults
├── dashboard/
│   ├── app.py               # Streamlit for fastest MVP
│   └── README.md
├── scripts/
│   ├── download_dataset.py
│   ├── create_splits.py
│   ├── train_baseline.py
│   ├── evaluate_ablation.py
│   ├── export_model.py
│   ├── compare_host_vs_board.py
│   └── make_demo_examples.py
├── tests/
│   ├── test_quality.py
│   ├── test_morphology.py
│   ├── test_decisions.py
│   ├── test_windowing.py
│   └── test_host_board_parity.py
└── docs/
    ├── hardware_bom.md
    ├── safety_scope.md
    ├── experimental_protocol.md
    ├── energy_budget.md
    ├── model_card.md
    └── demo_script.md
```

**Deployment tools:** Python + NumPy/SciPy/WFDB + PyTorch for research; ESP-IDF for ESP32-S3 firmware; use a **verified supported** ESP32-S3 inference backend (for example, ESP-DL where model operators are supported, or an appropriately ported embedded inference runtime). Check every operator for the final graph before deciding on GRU. Streamlit + Plotly is the fastest research dashboard path; React/FastAPI is optional later.

---

## 8. Firmware task partitioning, core allocation, and communication

| ESP32 Task | FreeRTOS Core | Suggested Responsibility | Priority Principle |
|---|:---:|---|---|
| **Acquisition Task** | Core 0 | Triggered by ADS1292R `/DRDY` GPIO ISR; reads SPI via DMA into thread-safe circular buffer; tracks dropped samples | Highest (Priority 24); hard real-time, cannot drop ECG samples |
| **Feature & ASQI** | Core 1 | Bounded $\mathcal{O}(N)$ signal-quality extraction on sliding window | Medium (Priority 10); predictable bounded compute burst |
| **MIG & Inference** | Core 1 | Morphology checks + quantized 1D-CNN tensor execution | Medium (Priority 10); executed every 2.5 s stride |
| **Decision & Triage** | Core 1 | Calibrated Accept/Review/Abstain policy; builds event payload | Medium (Priority 10); strictly deterministic |
| **Telemetry & Log** | Core 0 | BLE notifications / Wi-Fi dispatch; writes audit events to PSRAM | Low (Priority 5); transport failures must drop packets, never stall sampling |

**Implementation approach & Concurrency:**
- **Asynchronous Decoupling:** Hardware interrupt on `/DRDY` pin unblocks the high-priority acquisition task on Core 0 via a FreeRTOS stream buffer. Heavy compute tasks (ASQI, MIG, AI) are pinned to Core 1.
- **Timing and Stride:**
  - *Window Length:* 10.0 seconds (2,500 samples @ 250 Hz).
  - *Sliding Stride:* 2.5 seconds (625 samples).
  - *Cold-Start Note:* The first evaluation occurs at $t = 10\text{ s}$; thereafter, fresh evaluations arrive every 2.5 s.
- **System-level Stress Testing:** Benchmark continuous acquisition while inference is running and BLE is broadcasting. Dropped samples must remain strictly zero under sustained testing.

### Suggested wire message (illustrative, not validated medical format)

```json
{
  "device_id": "cardiosentinel_demo_01",
  "mode": "dataset_replay",
  "sample_rate_hz": 250,
  "window_samples": 2500,
  "model_version": "tinycnn_int8_v0",
  "quality": {"status": "REVIEW", "reason_codes": ["MOTION_LIKE_ARTIFACT"]},
  "classification": {"label": "UNCONFIRMED", "score": null},
  "decision": "REVIEW",
  "dropped_samples": 0
}
```

Do not transmit false values as if they were measured. Retain timestamp, dataset reference, input mode and raw/processed distinction.

---

## 9. Work plan: six practical development stages

### Stage 1 — Reproducible software baseline (Week 1)
- [ ] Set up GitHub repo, Python env and test harness.
- [ ] Load CinC 2017 and selected MIT-BIH data.
- [ ] Save immutable data/record split manifests.
- [ ] Convert to 250 Hz / 10-second windows with tested resampling.
- [ ] Implement minimal CNN; collect confusion matrix and per-class metrics.

**Done when:** one command recreates a held-out baseline report.

### Stage 2 — Quality and morphology (Week 2)
- [ ] Implement ASQI and synthetic corruption with fixed seeds.
- [ ] Preserve raw ECG before every filter.
- [ ] Add MIG disagreement tests and conservative REVIEW routing.
- [ ] Compare baseline / SQI / ASQI+MIG on identical held-out records.

**Done when:** raw and filtered waveforms, quality reasons and error examples are reproducible.

### Stage 3 — Tiny model and uncertainty policy (Week 3)
- [ ] Train compact 1D-CNN; optionally experiment with small GRU/TCN.
- [ ] Quantize and evaluate accuracy loss after compression.
- [ ] Fit calibration and decision thresholds on validation only.
- [ ] Build Accept/Review/Abstain rules; report coverage-risk curve.

**Done when:** a candidate compact model plus threshold manifest is frozen for firmware.

### Stage 4 — ESP32-S3 board integration (Week 4)
- [ ] Confirm development board's actual RAM/PSRAM/flash capacity.
- [ ] Set up ESP-IDF, inference runtime and quantized model.
- [ ] Run **digital dataset replay on the MCU** first to prove on-device AI.
- [ ] Measure p50/p95 latency, peak memory and host-vs-board output agreement.
- [ ] Use simpler CNN/TCN if GRU operator, RAM or time budget fails.

**Done when:** independent board traces prove inference is local to ESP32-S3.

### Stage 5 — Acquisition, connectivity and dashboard (Week 5)
- [ ] Interface ADS1292R with test source/ECG simulator only.
- [ ] Validate SPI rate, signal integrity and dropped-sample counters.
- [ ] Send results via BLE; build laptop Streamlit dashboard.
- [ ] Demonstrate acquisition and inference concurrently; log jitter.
- [ ] Implement model/version audit logs and artifact reason codes.

**Done when:** a labeled bench demo flows from test source to wearable MCU to dashboard.

### Stage 6 — Power, verification and TECHgium presentation (Week 6)
- [ ] Measure average and peak current in idle, continuous sampling, inference, and BLE streaming modes.
- [ ] Estimate battery life with measured duty cycles and realistic usable capacity; report assumptions.
- [ ] Run regression tests, pathological cases and held-out evaluation.
- [ ] Produce one reproducible ablation table and an honest limitation list.
- [ ] Record a 3–4 minute demo with mode labels and explicit nonclinical disclaimer.

**Done when:** submission contains code, demo, results, board trace, failure cases and documented limitations.

*Timeline is a suggested plan, not a guarantee. If time is short, cut model complexity or UI polish before cutting test integrity.*

---

## 10. Benchmarks, success gates, and the False Alarm vs. Missed Arrhythmia Proof

### 10.1 Proving False Alarm Reduction Without Missing Arrhythmias (Question E Defense)
The most critical test from judges is: *"How do you prove that reducing false alarms does not simply hide missed arrhythmias?"*
The project answers this through three formal mechanisms:

1. **Paired Benchmark on Locked Identical Splits:**
   Both the Naive Baseline (quality-blind 1D-CNN) and the full CardioSentinel pipeline are evaluated against the exact same held-out patient-disjoint test set.

2. **Selective Risk vs. Coverage (RC) Curves:**
   We report performance across coverage levels ($\phi \in [0.6, 1.0]$). As uninterpretable noise is routed to `ABSTAIN`, the false alarm rate per monitored hour must drop sharply **while arrhythmia sensitivity on the accepted cohort remains equal to or above the baseline**:

| Evaluation Metric | Baseline (Naive 1D-CNN) | CardioSentinel Edge Pipeline | Validation Pass Gate |
|---|:---:|:---:|---|
| **Coverage ($\phi$)** | 100% (Forced Guess) | e.g., 80%–85% Accepted | Must maintain $\ge 80\%$ coverage on test set |
| **Arrhythmia Sensitivity** | $S_{\text{base}}$ (e.g. 91.2%) | $S_{\text{accepted}} \ge S_{\text{base}}$ | **Zero sensitivity degradation** on accepted decisions |
| **False Alarms / Monitored Hr** | $FA_{\text{base}}$ (e.g. 4.8 / hr) | $\le 0.35 \times FA_{\text{base}}$ | Significant reduction in spurious alert burden |
| **False Abstention Audit** | Not applicable | Every missed arrhythmia logged | Full disclosure of any missed event during review |

3. **The Review Safety Valve:**
   Whenever ASQI detects moderate noise or MIG detects that filtering modified waveform features, the episode routes to `REVIEW`—**never** to Abstain or Normal. This guarantees that ambiguous abnormal beats are preserved for human inspection rather than quietly dropped.

### 10.2 System-level Success Gates

| Dimension | How to measure | Gate for release candidate |
|---|---|---|
| Diagnostic proxy performance | Held-out confusion matrix, macro F1, class sensitivity with CIs | Must be reported against frozen baseline; set final target after pilot evidence |
| False alarms | Spurious alerts / monitored hours with explicit denominator | Improvement vs baseline **without unacceptable sensitivity/coverage loss** |
| Accepted coverage | Fraction of evaluation windows accepted | Report together with performance; initial research target ≥80% on selected test distribution, subject to review |
| Morphology preservation | Before/after timing/QRS changes, missed abnormal beats | Report measured misses; unsafe transformations must route to review |
| Host-vs-board parity | Replay identical input on both platforms | Differences documented, bounded and regression-tested |
| Device compute | MCU timestamps for each stage ($t_{\text{ASQI}}, t_{\text{MIG}}, t_{\text{AI}}$) | Total burst latency $< 200\text{ ms}$; comfortably fits inside 2.5 s stride |
| MCU memory | Peak stack, heap, PSRAM and flash usage | Hot path fits in internal SRAM; external PSRAM handles logs/queues without heap crash |
| Power draw | Real meter current across states | Provide measured average mA and assumptions; battery runtime computed from measurements |
| Concurrency | Sample capture while AI and BLE operate | Zero dropped samples via `/DRDY` DMA pipeline under continuous load |
| Reproducibility | Re-run data splits, code and evaluation | Independent reviewer can regenerate main tables |

**Never claim:** 96.8% sensitivity, 97.4% specificity, 78.4% false-alarm reduction, 32.8 ms board latency or 24.6 h runtime as measured in the revised design unless experiments establish those exact values.

---

## 11. Practical test matrix

1. Clean normal ECG — accepted only if the calibrated policy supports it.
2. Clean labeled AF — evaluate class sensitivity and decision coverage.
3. Other rhythm — avoid forcing 'normal' or 'AF' where not justified.
4. Baseline drift / muscle interference / motion-like corruption — check quality explanations.
5. Contact-loss/flatline simulation — abstain with a clear reason.
6. Corrupted abnormal beat — check MIG flags suspicious distortion; do not assert 100% preservation.
7. Unknown input sample rate / dropped samples — fail safely and visibly.
8. MCU replay vs Python output — verify model, threshold and preprocessing parity.
9. SPI + inference + BLE simultaneously — track timing, queue overflow, packet loss and energy.
10. Full-length repeated replay — check thermal stability, memory fragmentation and log integrity.

---

## 12. What to show TECHgium judges

**Demo sequence:**
1. State the problem: noise can cause unnecessary alarms or hide abnormal beats.
2. Show **actual ESP32-S3 board** running a labeled, prerecorded ECG sample locally.
3. Present clean vs corrupted versions of the same record in the dashboard.
4. Show ASQI artifact flag and the original/filtered waveforms.
5. Show MIG forcing REVIEW if the correction changes important morphology.
6. Show a quantized on-device AI prediction plus Accept/Review/Abstain.
7. Display same-split evaluation, false alerts/hour, sensitivity, coverage and board memory/latency.
8. End with measured current/battery projection and explicit research-only limitations.

**One-line pitch:** *“CardioSentinel puts trustworthy ECG screening on a single low-power ESP32-S3: it checks signal quality, protects abnormal waveform evidence, and knows when to defer a decision.”*

---

## 13. Prioritized GitHub issue backlog

| Priority | Issue | Definition of done |
|---|---|---|
| P0 | Dataset loader and group-safe splits | Manifests with hashes, labels, counts |
| P0 | 250 Hz preprocessing and 10 s window tests | Verified shapes, original provenance retained |
| P0 | Quantified baseline CNN | Held-out report and checkpoint |
| P0 | ASQI v1 + synthetic artifact suite | Reason codes and artifact metrics |
| P0 | MIG v1 + before/after QA | Suspicious processing routes to review |
| P0 | Accept/Review/Abstain | Unit tests for critical cases |
| P0 | Tiny model compression/export | Artifacts, operator compatibility report |
| P0 | ESP32 replay inference | Measured board latency, RAM and parity |
| P1 | ADS1292R bench acquisition | Stable simulator/test-signal input |
| P1 | BLE telemetry and Streamlit dashboard | End-to-end demo screenshot + logs |
| P1 | Board energy profiling | Current traces and battery model |
| P1 | End-to-end ablation and failure report | Reproducible main results |
| P2 | GRU/TCN architecture comparison | Only if time and hardware budget allow |
| P2 | FHIR-shaped export demo | Validator-based structure test; no compliance overclaim |
| P3 | Hybrid accelerator or cloud inference | **Future** only if justified by measured limits |

---

## 14. Decision rule: when to reconsider hybrid hardware

**Stay ESP32-S3-only** if the board can continuously acquire ECG, execute the chosen compact model, send periodic telemetry, meet defined error/coverage targets and stay within a viable measured energy budget.

**Consider alternatives** only if documented experiments show persistent blockers after normal optimization: unsupported inference operators, unsafe latency/memory pressure, unacceptable sensitivity deterioration due to necessary model compression, or energy tradeoffs a different MCU/accelerator would materially improve. Evaluate a smaller MCU model **before** adding another processor. A laptop used only to train and visualize is not a hybrid wearable compute architecture.

---

## 15. Source, provenance and limitations

This is a design revision of:
- `CardioSentinel_100_10_Corrected_Concept.md` — research framing, ASQI, MIG, calibrated triage, evidence requirements.
- `CardioSentinel_Full_MVP_Development_Blueprint.md` — the original software-first roadmap.
- The earlier uploaded TECHgium Round 2 CardioSentinel proposal.

This revision **changes the main hardware target and deployment sequencing**. It does not assert that hardware has been assembled or the TinyCNN, GRU, ASQI or MIG have achieved validated medical performance.

Reference starting points:
- TI ADS1292R: https://www.ti.com/product/ADS1292R
- Espressif ESP32-S3: https://www.espressif.com/en/products/socs/esp32-s3
- Espressif ESP-DL: https://github.com/espressif/esp-dl
- PhysioNet/CinC 2017: https://physionet.org/content/challenge-2017/1.0.0/
- MIT-BIH: https://physionet.org/content/mitdb/1.0.0/

**Clinical disclaimer:** The MVP uses public/replayed ECGs and simulators. Nothing in this plan establishes medical-device certification or clinical effectiveness.
