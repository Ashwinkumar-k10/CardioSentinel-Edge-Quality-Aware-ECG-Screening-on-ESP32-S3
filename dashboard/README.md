# CardioSentinel Edge Dashboard

Clinician-style demonstration and research visualization dashboard for the ESP32-S3 CardioSentinel Edge prototype.

## Features
- **3-Zone Calibrated Triage:** Real-time visual indicator for ACCEPT (Green), REVIEW (Amber), and ABSTAIN (Red).
- **Dual-Stream Waveform Viewer:** Side-by-side comparison of untouched Raw ECG and candidate Filtered ECG with detected R-peaks.
- **ASQI Radar & Metrics:** Detailed linear-time feature breakdown (drift, line-length EMG complexity, clipping, variance).
- **Morphology Integrity Guard:** Real-time warning when digital filtering distorts abnormal waveform morphology.
- **Model Confidence:** Calibrated probability bars for Normal, AF, and Other rhythms.
- **Jury Defense Table:** Live presentation of the paired ablation benchmark proving false alarm reduction without missing real arrhythmias.
- **Telemetry Downloader:** Export JSON telemetry packets aligned with FHIR R4 demonstration structures.

## How to Run

From the project root:
```bash
streamlit run dashboard/app.py
```
Or specify port:
```bash
streamlit run dashboard/app.py --server.port 8501
```
