# CardioSentinel — Revised Idea & Concept Plan (ESP32-S3-Only)
## TECHgium Challenge 26 | Safety-first, low-power, quality-aware wearable ECG screening

> **Version:** 3.0 | **Date:** 2026-11-09  
> **Document purpose:** Complete **idea and solution proposal**, distinct from the detailed MVP implementation plan.  
> **Chosen architecture:** One **ESP32-S3 as the wearable's only main processor**, supported by an **ADS1292R ECG analog front end (AFE)**. No Raspberry Pi/Jetson/extra AI processor in the wearable. A laptop is used for *offline model training, development and display*, not for required live inference.  
> **Status:** Research concept and engineering targets; not a completed or clinically validated medical device.  
> **“100/10”** describes the ambition to build an exceptionally well-reasoned and demonstrable competition project—not a literal evaluation score or 100% clinical accuracy.

---

## 1. Project title and one-line pitch

**Project name:** **CardioSentinel Edge**  
**Full title:** **CardioSentinel Edge: A Low-Power, Quality-Aware, Morphology-Preserving ECG Screening System with On-Device Uncertainty-Aware AI**

**One-line pitch:** A compact ECG screening prototype that checks whether an ECG can be trusted, safeguards important heartbeat evidence during noise handling, and runs a lightweight arrhythmia screening model **locally on one ESP32-S3**—then decides whether to accept, flag for review, or abstain.

**Competition pitch (30 seconds):**

> Wearable ECG classifiers can overreact to motion noise or, after aggressive denoising, overlook abnormal heartbeat features. CardioSentinel Edge proposes a low-power wearable architecture built around one ESP32-S3 and an ADS1292R ECG front end. Its adaptive signal-quality logic assesses noise, a Morphology Integrity Guard checks whether corrections distort medically relevant features, and a compact edge-AI classifier produces screening results with explicit uncertainty-aware Accept/Review/Abstain decisions. An auditable dashboard displays original waveforms, model reasoning, and evaluation evidence. We will assess whether false alerts fall without sacrificing sensitivity or usable recording coverage.

---

## 2. Core problem

### Why this matters

Arrhythmias may occur intermittently during daily life, outside a clinical ECG appointment. Wearable sensors can record extended periods, but movement, muscle interference, baseline drift and poor electrode contact can degrade the recording. Two important mistakes must be addressed **together**:

1. **False positives:** Noise looks like an arrhythmia; the system reports unnecessary alerts.
2. **False negatives or unsafe reassurance:** Filtering or automatic quality rejection obscures a genuinely abnormal waveform, or an uninterpretable segment is incorrectly described as normal.

An ordinary classifier optimizes rhythm prediction. **CardioSentinel's research question** is broader: *Can a small wearable system manage signal quality, protect waveform morphology, and express uncertainty while reducing false alerts at an acceptable rate of retained, interpretable recordings?*

### Intended audience and use

- **In MVP:** TECHgium judges, engineering researchers, signal-processing and embedded-AI developers, using public/de-identified ECG data and simulator signals.
- **Long-term potential:** Clinician-reviewed ambulatory ECG research workflows, following appropriate independent validation, electrical safety assessments and approvals.
- **Not intended for MVP:** Patient diagnosis, independent emergency decision-making, medical treatment guidance, or unapproved human-connected monitoring.

---

## 3. Final architecture choice: what we selected and why

| Question | Final choice | Rationale |
|---|---|---|
| Main embedded processor | **ESP32-S3 only** | One programmable processing device reduces system integration and helps optimize footprint and energy. |
| ECG signal acquisition | **ADS1292R AFE** | Digitizes ECG-like analog signals; **not** a second compute processor. |
| AI inference location | **ESP32-S3 on device** | No required cloud or laptop classifier for intended wearable operation. |
| Core AI | **Quantized small 1D-CNN** | First deployable baseline; measure on actual board. |
| Optional improved model | **Compact CNN+GRU or CNN+TCN**, *only if it fits and works* | Compare gains against flash, RAM, operator availability, latency and energy. |
| Signal quality + morphology guard | **Lightweight ESP32-S3 algorithms** | Small, bounded implementations before/around AI inference. |
| Data connection | **BLE preferred** | Send waveform previews, quality reasons, screening output and logs to viewer. |
| Training | **Offline on laptop/PC** | Training is compute-intensive; it is not a second wearable processor. |
| Dashboard | **PC/mobile viewer** | Display and audit only; not required for wearable inference. |
| Hybrid hardware | **Deferred future option** | Reconsider only if measured embedded constraints prevent the research goal. |

**What “ESP32-S3-only” means:** The *wearable processor* is a single ESP32-S3. The ADS1292R, battery charger, regulator and electrode interface are supporting hardware—not additional AI processors. A laptop for training or for a graphical display does not contradict the single-processor embedded architecture.

**Power caveat:** A one-processor design offers a simpler route to low power, but **does not automatically guarantee** a particular runtime. Measure AFE + MCU + radio + storage + power losses under the real sampling/inference/telemetry schedule.

---

## 4. Proposed end-to-end system

```text
    Public ECG data / isolated ECG simulator / AFE test source (MVP)
                              |
                              v
                    ADS1292R ECG AFE
                      (digital SPI)
                              |
                              v
             +------------------------------------+
             |        ESP32-S3 — ONE MCU          |
             |                                    |
             |  1. Sampling + original data buf   |
             |  2. Lightweight preprocessing      |
             |  3. Adaptive Signal Quality (ASQI) |
             |  4. Morphology Integrity Guard     |
             |  5. Small quantized AI classifier  |
             |  6. Calibration / decision policy  |
             |     ACCEPT / REVIEW / ABSTAIN      |
             |  7. Event log + BLE telemetry      |
             +------------------------------------+
                              |
                              v
                 Clinician-style demo dashboard
               raw + processed ECG, flags, logs
               (display / review; no AI required)

 OFFLINE: public datasets -> train/test -> quantize -> board profile
```

### Essential system behavior

- Never label an unusable signal as confidently normal.
- Keep the **raw signal** alongside any processed representation used for classification or review.
- If correction changes suspicious beat shape or timing too much, **do not trust it automatically**; route to review.
- If the model is uncertain, show **Review** or **Abstain**, with a reason code.
- Report **missed events, false alerts, and fraction of data classified** together; abstaining on everything is not a win.

---

## 5. Five distinct innovations / subsystems

### A. Adaptive Signal Quality Intelligence (ASQI)

Rather than a fixed “good/bad” threshold, ASQI estimates different interference modes, e.g. baseline drift, high-frequency muscle interference, transient motion-like corruption, clipping and contact-loss proxies. It returns a quality score and reason codes, with low-cost features appropriate for MCU deployment. Artifact labels produced by synthetic noise injection must be described as **synthetic labels**.

**Example output (illustrative, not measured):** `quality=0.73`, `artifact=baseline_wander`, `action=check_correction`.

### B. Morphology Integrity Guard (MIG)

A safeguard for noise-correction side effects. Compare original and candidate-processed signal features: beat timing, R-peak displacement, QRS shape and suspicious-event preservation. If changes exceed conservative, experimentally calibrated boundaries, decline automatic acceptance and flag the segment for review. MIG is **not** proof that the system will catch or preserve every dangerous event.

### C. Tiny, deployable arrhythmia screening AI

Start with a 1D-CNN and an honest per-dataset label scheme. Use the PhysioNet/CinC 2017 recording-level labels (Normal / AF / Other / Noisy) for the initial task, treating Noisy as interpretability, not a heart rhythm. Evaluate MIT-BIH annotated beat data as a *separate* beat-focused study; do not silently merge incompatible labels. Upgrade to quantized CNN+GRU/TCN only if the better model demonstrably fits the ESP32-S3 and improves outcomes.

### D. Calibrated uncertainty and three-zone screening

- **ACCEPT:** Quality adequate; prediction within validated confidence and morphology criteria. Report *research screening impression*, not definitive diagnosis.
- **REVIEW:** Model disagreement, potential dangerous morphology, questionable filtering, borderline quality, or out-of-distribution concern. Preserve all evidence.
- **ABSTAIN:** Input too corrupted, unsupported, or otherwise uninterpretable. No “normal” conclusion.

Calibration can use held-out validation data; do not assume high neural-network confidence means clinical reliability. Implement a simple calibrated threshold system first, and add evidential modeling only when measured value outweighs compute cost.

### E. Traceable, transparent dashboard

Display input source, original/processed waveform, reason for quality decisions, approximate confidence/calibration, final decision, model version and repeatable case IDs. A **FHIR R4-shaped demonstration export** is optional; generating structured JSON is not equivalent to regulatory compliance or full interoperability certification.

---

## 6. Why not choose full hybrid hardware now?

| Trade-off | Single ESP32-S3 (chosen) | Wearable hybrid compute (deferred) |
|---|---|---|
| Development risk | Fewer embedded integration interfaces | More communication/synchronization/power issues |
| Energy | Easier to audit as one main compute budget | Extra processing and interconnect may increase energy |
| Model capacity | Smaller/quantized models | Potentially larger models |
| Demonstration clarity | Strong one-board edge-AI story | More complex to debug and explain |
| Expansion | Model optimization and future redesign possible | Useful only after demonstrated need |

**Decision rule:** If an optimized, measured ESP32-S3 model fails to meet a defined sensitivity/coverage target or cannot fit memory/latency bounds, first simplify the model or move noncritical dashboard features off-device. Propose hybrid wearable hardware only after recording the failed measurements and trade-offs.

---

## 7. What counts as success? (Targets, NOT claims)

The corrected original proposal reported **96.8% sensitivity, 97.4% specificity, 78.4% fewer false alarms, 32.8 ms edge latency, and >24.6 h battery life**. Those numbers are **historical claims from the earlier submission**, not established findings of this revised plan. Do not copy them into the competition presentation as validated outcomes without full reproducible evidence.

**Proposed evidence-driven success criteria:**

1. A public-dataset test set separated by patient where possible (otherwise rigorously record-disjoint), with locked splits and consistent labels.
2. **Reduced false alerts at a stated minimum coverage** compared with a frozen baseline, without materially degrading relevant arrhythmia sensitivity.
3. Calibration and risk-versus-coverage curves; confidence intervals for sensitivity and specificity.
4. Evidence that MIG catches or flags correction-induced changes on a defined test suite; disclose any high-risk events lost or missed.
5. On-board proof: final model actually executes on ESP32-S3, with reported **flash/RAM, latency distribution and energy/current measurements**.
6. A traceable demo from an original ECG window to final review/abstain outcome.

**Example engineering thresholds to refine after pilots:** >=80% accepted coverage on a clearly specified test distribution; below a chosen p95 processing deadline; measured battery runtime for a fixed radio duty cycle. These are not clinical safety thresholds and are not achieved results.

**Primary comparison:**

- (1) Plain 1D-CNN, no quality gate.
- (2) Baseline + static SQI gate.
- (3) ASQI + morphology guard + same classifier.
- (4) Same as (3) + calibrated Accept / Review / Abstain.

All four variants must use the same test records and fixed event definitions. Show sensitivity, specificity, macro F1, false alerts per monitored hour, coverage, selective risk, and performance in noisy subsets.

---

## 8. Hardware, timing, and memory architecture

**Proposed bench hardware:**

- **Main MCU:** One ESP32-S3 development board (recommended: **ESP32-S3-WROOM-1 with 8 MB Octal PSRAM / N8R8**). Provides zero-wait internal SRAM for the hot path with PSRAM as a safe buffer for telemetry and trace logging.
- **Analog Front End:** One TI ADS1292R ECG AFE, interfaced via SPI with hardware `/DRDY` line triggering interrupt-driven FreeRTOS acquisition tasks.
- **Power management:** Dedicated 3.3V LDO regulator, LiPo/LiFePO4 battery in later portable prototype, with shunt-resistor/current-sense probe for active power logging.
- **Telemetry:** BLE preferred for low-power periodic status and compressed alert snippets; Wi-Fi optional for bench demo.
- **Signal test modes (bench only):** Public ECG digital replay (algorithm validation), AFE internal square-wave test (SPI/acquisition integrity), and bench ECG simulator (analog chain check). These prove different things and are labeled separately.

### Window configuration and acquisition mechanics
- **Sampling rate:** 250 Hz (industry-standard diagnostic screening baseline).
- **Window size:** **10.0 seconds (2,500 samples)**. Captures sufficient continuous beat history (typically 10–16 beats) to evaluate rhythm irregularity, ectopic clusters, and rate variability (crucial for atrial fibrillation screening).
- **Sliding stride:** **2.5 seconds (625 samples)**, providing a 75% sliding overlap. After a 10-second cold-start fill, a fresh evaluation occurs every 2.5 seconds.
- **Acquisition path:** The ADS1292R `/DRDY` pin fires an active-low GPIO interrupt upon conversion completion. The ISR signals a dedicated FreeRTOS acquisition task via a task notification or stream buffer, reading multi-byte SPI transfers via DMA. This decouples hardware sampling from AI inference on Core 1 to prevent sample dropping.

### Memory layout strategy
| Memory component | Preferred location | Sizing & Rationale |
|---|---|---|
| **SPI DMA acquisition buffers** | Internal DMA-capable RAM | Dual ping-pong buffers (~2 KB); required for hardware DMA |
| **Active 10 s sliding circular buffer** | Internal SRAM | 2,500 samples × 4 bytes (float) ≈ 10 KB |
| **ASQI and MIG working structures** | Internal SRAM | Peak ~15–20 KB scratch space for linear-time feature extraction |
| **TFLite Micro / ESP-DL tensor arena** | Internal SRAM (if fits) | Target ≤ 120–160 KB for INT8 quantized 1D-CNN |
| **Long-term trace logs & BLE queues** | External PSRAM | Multi-megabyte buffer; prevents heap starvation of real-time tasks |
| **Raw audit episodes (Review/Abstain)** | External PSRAM / SPI Flash | Preserved uncompressed for auditable dashboard export |

**Safety boundary:** Do not connect a homemade USB-/mains-associated ECG circuit to a person. Human-connected ECG engineering requires qualified supervision, electrical isolation and applicable medical safety assessment. Simulator-only demonstration is enough for a credible competition MVP.

---

## 9. Key project deliverables

### Concept and research deliverables

1. Refined problem statement, intended-use boundary and system/block diagram.
2. Innovation statement distinguishing ASQI + MIG + calibrated triage from a generic arrhythmia classifier.
3. Related-work table: published SQI, artifact remediation, edge ECG classification and uncertainty methods; cite sources and avoid unsupported novelty claims.
4. Risk register and evaluation plan with exact outcome definitions.

### Demonstrable engineering deliverables

1. Reproducible dataset loader, annotation mapping and train/test manifest.
2. Baseline classifier, ASQI, MIG and comparison study.
3. Small quantized model and **measured** on-board ESP32-S3 inference.
4. Recorded ECG playback and dashboard showing raw/processed signals, confidence/reason codes and decisions.
5. Bench acquisition demonstration (if equipment available), latency/memory/power table and reproducible test report.

---

## 10. Project development stages (high-level idea roadmap)

**Stage 0 — Verify what exists.** Audit the repository, datasets, actual trained checkpoints and hardware available. Reclassify earlier performance claims as target/preliminary/verified according to evidence.

**Stage 1 — Demonstrate the essential problem.** On public prerecorded ECG, show a naive classifier's behavior on clean and artificially noisy signals. Establish a frozen baseline.

**Stage 2 — Demonstrate the differentiator.** Add ASQI and MIG, log their decisions and stress-test whether noise correction destroys morphology or misses abnormal events.

**Stage 3 — Reduce to ESP32-S3.** Quantize and deploy a lightweight CNN; measure board-level feasibility before considering CNN+GRU. Calibrate decision thresholds on held-out validation data.

**Stage 4 — Integrate the demo.** Provide dashboard playback, Accept/Review/Abstain, raw-data provenance and clear indication of simulated vs recorded input.

**Stage 5 — Prove the claim.** Reproduce paired baseline comparisons; measure false-alert burden, sensitivity, coverage, errors, memory, latency and battery/current. Present limitations honestly.

For commands, folder structure, software interfaces, test cases and detailed milestone checklists, see the companion **`CardioSentinel_ESP32S3_Only_Revised_MVP_Plan.md`**.

---

## 11. Technical Risk Register & Five Critical Architectural Questions Answered

### Question A: Will ASQI + MIG overload the ESP32-S3?
**Verdict:** No, provided features use deterministic $\mathcal{O}(N)$ bounded linear-time heuristics rather than quadratic algorithms.
- **ASQI heuristics:** Baseline drift (moving median / linear detrending), amplitude saturation / clipping, signal variance, zero-crossing rate, line-length / curve-length complexity, and high-frequency noise proxies. 
  > *Note on complexity:* Standard sample entropy is $\mathcal{O}(N^2)$ (for $N=2,500$, $6.25 \times 10^6$ comparisons), which would consume excessive cycles. Do not treat sample entropy as cheap; replace it with $\mathcal{O}(N)$ line-length or fixed-point approximations.
- **MIG heuristics:** Lightweight peak tracking: timing shifts in dominant R-peaks, QRS duration changes, and mean absolute difference between raw and candidate-filtered signals around peak regions.
- **Measurement discipline:** Instrument firmware to record and report cycle counts and execution times separately:
  $$\text{Total Window Latency} = t_{\text{ASQI}} + t_{\text{MIG}} + t_{\text{AI}} + t_{\text{Triage}}$$
  All three must comfortably execute well within the 2.5-second stride deadline (targeting $< 200\text{ ms}$ total compute burst, leaving $> 90\%$ CPU idle time for power management).

### Question B: Will the ESP32-S3 have enough memory?
**Verdict:** Yes, by designing the zero-wait-state critical path to fit inside internal SRAM, while utilizing external PSRAM as a safe buffer.
- The ESP32-S3 contains 512 KB internal SRAM, but Bluetooth/Wi-Fi stacks, FreeRTOS kernel, DMA pools, and application overhead leave approximately 250–320 KB usable heap.
- **Realistic placement policy:**
  - *Internal DMA RAM:* SPI ping-pong buffers (~2 KB).
  - *Internal SRAM:* Active 2,500-sample circular buffer (~10 KB), ASQI/MIG working variables (~20 KB), and quantized TFLite Micro / ESP-DL tensor arena (~120–160 KB).
  - *External PSRAM (ESP32-S3 N8R8 with 8 MB Octal PSRAM):* Large circular historical logs, BLE event queues, and uncompressed raw waveform buffers for dashboard export.
- **Strategy:** Target internal SRAM for all time-critical inferencing. Having external PSRAM provides essential headroom against stack/heap fragmentation without requiring an auxiliary coprocessor.

### Question C: What window size and acquisition schedule should be used?
**Verdict:** 250 Hz sampling, 10.0-second window (2,500 samples), 2.5-second stride (75% overlap).
- **Why 10 seconds?** Atrial fibrillation and significant rhythm irregularities require observing consecutive RR-interval patterns (typically 10–16 cycles). Shorter windows (e.g., 2.5s) capture only 2–4 beats, which is insufficient for reliable rhythm entropy.
- **Why 2.5s stride?** Allows refreshed screening inferences every 2.5 seconds once the first 10-second buffer is primed.
- **Acquisition mechanics:** The ADS1292R `/DRDY` interrupt asserts when a conversion is ready, notifying a high-priority FreeRTOS acquisition task. Samples are transferred over SPI via DMA into a thread-safe circular stream buffer. The inference pipeline runs on Core 1 at a lower priority, ensuring zero dropped samples.
- **Timing transparency:** A 10-second window inherently introduces a 10-second cold-start latency before the first complete evaluation.

### Question D: What is the formal boundary between REVIEW and ABSTAIN?
**Verdict:** Strictly decouple *physical signal uninterpretability* (Abstain) from *epistemic / model uncertainty* (Review).
- **ABSTAIN (Uninterpretable):**
  - Triggers: Hardware lead-off detection, continuous amplifier rail saturation/clipping, excessive baseline drift exceeding ADC dynamic range, or missing sample packets.
  - Action: No rhythm inference is attempted. The system asserts *“signal uninterpretable”* with diagnostic reason codes. It is **never** counted or reported as normal.
- **REVIEW (Interpretable but Ambiguous):**
  - Triggers: Signal quality passes basic usability, but (a) model prediction margin is low / calibration confidence is below validation threshold, (b) classifier flags a potentially dangerous rhythm with moderate certainty, or (c) MIG detects that filtering modified QRS amplitude or timing beyond conservative bounds.
  - Action: The episode is tagged for human inspection; raw and processed waveform snapshots are preserved in PSRAM/flash for clinician review.
- **Calibration note:** Thresholds for Accept/Review/Abstain must be fitted exclusively on held-out validation sets (e.g., Platt scaling or temperature scaling), never hand-tuned ad-hoc or claimed as medically validated cutoffs.

### Question E: How will you prove that reducing false alarms does not increase missed arrhythmias?
**Verdict:** This is the most critical scientific validation in the project. It is proven through **paired evaluation on identical held-out test splits** using **Risk-Coverage (RC) curves**.

```text
               EVALUATION BENCHMARK (PAIRED HELD-OUT SPLIT)
┌──────────────────────────────────────┬────────────────────────┬────────────────────────┐
│ Metric                               │ Naive Baseline CNN     │ CardioSentinel Edge    │
├──────────────────────────────────────┼────────────────────────┼────────────────────────┤
│ Test Split Provenance                │ Locked CinC 2017 Split │ Locked CinC 2017 Split │
│ Total Monitored Coverage             │ 100% (Forced Guess)    │ e.g., 82% (18% Abstain)│
│ Arrhythmia Sensitivity (on Accepted) │ 91.2%                  │ ≥ 91.2% (Preserved)    │
│ False Alarms per Monitored Hour      │ 4.8 / hr               │ ≤ 1.2 / hr (-75%)      │
│ False Abstention Audit (Missed PVCs) │ N/A                    │ Fully Audited / Disclosed│
└──────────────────────────────────────┴────────────────────────┴────────────────────────┘
```

1. **Locked Paired Test Sets:** Both the baseline classifier and the CardioSentinel pipeline are evaluated against the exact same patient-disjoint test records.
2. **Selective Risk vs. Coverage ($\phi$):** Plot arrhythmia sensitivity and false-positive rate across varying coverage levels. We show that false alarms decrease as uninterpretable noise is routed to *Abstain*, while sensitivity on the retained accepted cohort remains equal to or higher than baseline.
3. **The Review Safety Valve:** When in doubt, ambiguous or potentially abnormal signals are routed to *Review* rather than *Abstain*, ensuring genuine arrhythmias are never silently ignored or misclassified as normal. Every missed event on the test set is documented in the final report.

---

## 12. Judges' live demonstration story

1. Present the challenge: noisy ECG can cause false alarms or obscure true abnormalities.
2. Play a **labeled clean** public ECG record; show original trace and baseline output.
3. Replay a **synthetically corrupted copy** of that record; show the baseline failure if observed.
4. Turn on ASQI; show detected artifact type and quality information.
5. Turn on MIG; show original-vs-processed comparison and whether correction is accepted or flagged.
6. Show lightweight screening on the **ESP32-S3** and Accept/Review/Abstain decision, with on-board latency/memory measurements.
7. Show a paired benchmark chart: false alarms and sensitivity **at equal reported coverage**; disclose observed misses.
8. Explain that the dashboard is a demonstration viewer and not a clinical diagnosis system.

**The strongest judge-facing sentence:** *“Our innovation is not making AI predict on every ECG; it is engineering the system to know when the recording is unreliable, preserve suspicious evidence, and justify when it refuses a confident answer—on a single small wearable processor.”*

---

## 13. Concise submission abstract

**CardioSentinel Edge** proposes a low-power, quality-aware ECG screening platform built around a single ESP32-S3 processor and ADS1292R ECG analog front end. Ambulatory ECG signals can be corrupted by movement, muscle interference or poor sensor contact, producing false alarms and potentially obscuring genuine abnormal heartbeat features. Our proposed system combines Adaptive Signal Quality Intelligence (ASQI) with a Morphology Integrity Guard (MIG) that checks whether attempted correction changes important rhythm evidence. A small quantized neural network performs on-device rhythm screening, while calibrated uncertainty handling selects one of three outcomes: Accept, Review or Abstain. The accompanying dashboard retains original and processed ECG views, quality reasons and traceable decisions. Validation will compare quality-blind, SQI-only and proposed variants using public ECG datasets with separated test records, noise stress tests, false-alert burden, event sensitivity and accepted-recording coverage. ESP32-S3 benchmarking will measure memory, latency and energy rather than assume low-power performance. The initial device is a **simulator-driven research prototype**, not a clinically validated diagnostic system.

---

## 14. Project positioning and final recommendation

**Choose:** **ESP32-S3-only wearable + ADS1292R + compact edge AI**, with ASQI and MIG as the primary novelty. **Do not choose a second wearable AI processor merely to support a larger network**. Larger models belong in controlled experiments until proven worthwhile for the actual task and hardware.

**Priority order:** reliability and evidence preservation → honest sensitivity/false-alert/coverage evaluation → successful on-board execution → measured energy → feature expansion.

**Companion document:** `CardioSentinel_ESP32S3_Only_Revised_MVP_Plan.md` is the detailed *how to build it* plan. **This document is the *what and why* idea plan.**

### References to verify or cite in the submission

- PhysioNet/CinC 2017 dataset: https://physionet.org/content/challenge-2017/1.0.0/
- MIT-BIH Arrhythmia Database: https://physionet.org/content/mitdb/1.0.0/
- TI ADS1292R: https://www.ti.com/product/ADS1292R
- Espressif ESP32-S3: https://www.espressif.com/en/products/socs/esp32-s3
- For clinical software standards, research IEC 60601-1, IEC 60601-2-47, IEC 62304, ISO 14971 and HL7 FHIR R4 with qualified advisors; **no compliance is claimed**.

