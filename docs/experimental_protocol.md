# CardioSentinel Edge — Experimental Protocol & Question E Proof
**TECHgium Challenge 26 Research Prototype**

## 1. Overview
The experimental protocol evaluates edge screening performance on locked, patient-disjoint splits, explicitly addressing the core jury inquiry:
> *"How do you prove that reducing false alarms does not simply hide missed arrhythmias?"*

---

## 2. Benchmark Architecture: Paired Evaluation on Locked Splits

To eliminate evaluation bias:
1. **Identical Held-Out Split:** Both the Naive Baseline (quality-blind 1D-CNN) and the CardioSentinel Edge Pipeline receive the exact same 10-second ECG windows.
2. **Standard Evaluation Metrics:**
   - **Decision Coverage ($\phi$):** Proportion of windows where a definitive screening decision is accepted:
     $$\phi = \frac{N_{\text{accepted}}}{N_{\text{total}}}$$
   - **Arrhythmia Sensitivity ($S_{\text{arr}}$):** Recall on abnormal rhythms (AF and Ventricular Ectopy/Other):
     $$S_{\text{arr}} = \frac{\text{True Positives}}{\text{True Positives} + \text{False Negatives}}$$
   - **False Alarm Rate ($FA / \text{hr}$):** Number of spurious arrhythmia alerts generated per monitored hour on true normal ECGs:
     $$FA / \text{hr} = \frac{\text{False Positives}}{\text{Monitored Hours}}$$
   - **False Alarm Reduction ($\Delta FA$):**
     $$\Delta FA = \frac{FA_{\text{base}} - FA_{\text{cardio}}}{FA_{\text{base}}} \times 100\%$$

---

## 3. The 3-Zone Triage Safety Valve Mechanism

| Triage Zone | Trigger Criteria | Action Taken | Clinical Rationale |
|:---:|---|---|---|
| **ACCEPT** | ASQI usable, zero saturation/lead-off, MIG morphology preserved, calibrated confidence $\ge 0.68$, margin $\ge 0.15$. | Outputs screening label & confidence to dashboard. | Clinician can trust the decision because signal quality and beat shape have been rigorously confirmed. |
| **REVIEW** | ASQI indicates mild/moderate noise, OR MIG flags $>28\%$ attenuation / $>16\,\text{ms}$ shift in R-peaks, OR confidence is ambiguous. | Retains raw and filtered waveforms in PSRAM; flags alert for clinician inspection. **Never silently dismissed.** | **Prevents false negatives!** Real abnormal beats distorted by noise are preserved rather than dropped. |
| **ABSTAIN** | Hardware lead-off (disconnect) or ADC rail saturation. | Outputs `ABSTAIN` with explicit hardware reason code. | **Prevents spurious alarms!** Garbage data is prevented from triggering fake emergency alerts. |
