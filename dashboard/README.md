# CardioSentinel Edge — Clinical Telemetry SaaS Dashboard

An industry-grade, enterprise medical telemetry dashboard for the CardioSentinel single-SoC ESP32-S3 ECG screening system.

---

## Two Available Enterprise Modes

### Option A: Real-Time 60 FPS Medical Scope SaaS (FastAPI + HTML5 Canvas)
A high-frequency web application mimicking ICU/telemetry hospital patient monitors:
* **Silky-smooth 60 FPS Sweep Oscilloscope:** Decaying phosphor persistence trace on an official IEC standard $25\,\text{mm/s}$, $10\,\text{mm/mV}$ calibration grid.
* **Dual-Stream Overlay:** View raw untouched ECG in cyan overlaid with candidate-filtered diagnostic ECG in neon emerald.
* **Real-Time Web Audio Synthesizer:** Heartbeat QRS pulse chirps and alarm tones.
* **Live 3-Zone Triage Console:** Real-time glowing indicators for `ACCEPT`, `REVIEW`, and `ABSTAIN`.
* **PSRAM Audit Ring:** Tabular view of preserved raw/filtered episodes with JSON inspection.
* **HL7 / FHIR R4 Export:** Direct download of clinical `DiagnosticReport` / `Observation` bundles.

#### How to Launch:
```bash
python dashboard/server.py
```
Open **[http://localhost:8000](http://localhost:8000)** in any modern web browser.

---

### Option B: Deep Research & Verification Console (Streamlit + Plotly)
An interactive analytical station with:
* Plotly zoomable dual-stream ECG waveforms.
* ASQI signal quality multi-meter cockpit.
* Question E jury defense table & verification proof.
* TinyCNN class distribution & Xtensa LX7 cycle latency breakdown.

#### How to Launch:
```bash
streamlit run dashboard/app.py
```
Open **[http://localhost:8501](http://localhost:8501)** in your browser.
