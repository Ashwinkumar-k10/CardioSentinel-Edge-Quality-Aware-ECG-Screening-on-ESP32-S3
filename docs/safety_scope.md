# CardioSentinel Edge — Research Safety & Non-Clinical Scope
**TECHgium Challenge 26 Research Prototype**

## 1. Important Safety & Non-Clinical Statement

> **CRITICAL MEDICAL DISCLAIMER:**  
> CardioSentinel Edge is an academic research and engineering prototype developed for the TECHgium Challenge 26. It is **not** a certified medical device, has not undergone clinical trials, and has not received FDA 510(k), CE-MDR, or CDSCO approval. It is **never** intended for medical diagnosis, clinical treatment, emergency decision-making, or unsupervised patient monitoring.

---

## 2. Electrical Safety Protocols

During MVP bench development:
1. **Zero Human Electrode Connection:** No electrodes connected to human subjects using homemade or bench-powered USB hardware. Mains-powered debugging cables (USB-UART) present ground loops and leakage hazards.
2. **Approved Signal Sources Only:**
   - **Mode A (Dataset Replay):** Digitized public records from PhysioNet CinC 2017 / MIT-BIH injected via firmware circular buffer.
   - **Mode B (Benchtop ECG Simulator):** Battery-isolated medical ECG simulator (e.g., Fluke / Pronk) connected to ADS1292R inputs.
   - **Mode C (Internal AFE Test Mode):** ADS1292R internal 1 Hz square-wave calibration generator.
3. **Galvanic Isolation:** Any future battery-powered demonstrator must adhere to IEC 60601-1 / IEC 60601-2-47 electrical safety standards with reinforced insulation.
