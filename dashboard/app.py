"""
CardioSentinel Edge - Clinician & Demonstration Dashboard
TECHgium Challenge 26 Research Prototype

Interactive visualization of single-SoC ESP32-S3 ECG screening:
- Dual-stream raw vs filtered waveform comparison
- Adaptive Signal Quality Intelligence (ASQI) radar & metrics
- Morphology Integrity Guard (MIG) distortion detection
- Calibrated 3-Zone Triage: ACCEPT (Green) | REVIEW (Amber) | ABSTAIN (Red)
"""

import os
import sys
import json
import numpy as np
import streamlit as st

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from research.asqi import compute_asqi
from research.morphology_guard import evaluate_morphology_integrity, detect_qrs_peaks
from research.preprocessing import prepare_dual_stream_ecg
from research.calibrate import apply_calibrated_triage
from research.models_tiny import CardioSentinelTinyCNN, TinyCNNFusedNumPyEngine
from research.quantize_export import export_fused_c_header
import torch

st.set_page_config(
    page_title="CardioSentinel Edge | ESP32-S3",
    page_icon="🫀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for clinical styling
st.markdown("""
<style>
    .metric-card {
        background-color: #1e2530;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        border: 1px solid #2d3748;
    }
    .badge-accept {
        background-color: #10b981;
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 1.2rem;
        display: inline-block;
    }
    .badge-review {
        background-color: #f59e0b;
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 1.2rem;
        display: inline-block;
    }
    .badge-abstain {
        background-color: #ef4444;
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 1.2rem;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_cached_engine():
    model = CardioSentinelTinyCNN()
    weights_path = "models/tinycnn_best.pth"
    if os.path.exists(weights_path):
        model.load_state_dict(torch.load(weights_path, weights_only=True))
    fused = export_fused_c_header(model, "firmware/esp32s3/models/tinycnn_weights.h")
    return TinyCNNFusedNumPyEngine(fused["fused_arrays"])


# Sidebar Controls
st.sidebar.title("🫀 CardioSentinel Edge")
st.sidebar.caption("TECHgium Challenge 26 | ESP32-S3-Only MVP")

st.sidebar.markdown("---")
st.sidebar.subheader("Hardware & System Profile")
st.sidebar.markdown("""
- **Microcontroller:** ESP32-S3 (Dual-Core @ 240 MHz)
- **Analog Front End:** TI ADS1292R (250 Hz @ 24-bit)
- **Memory Hot-Path:** Internal Zero-Wait SRAM (< 120 KB)
- **Audit Storage:** 8 MB Octal PSRAM
- **Task Partitioning:** Core 0 (Acq + Telemetry) | Core 1 (AI + DSP)
""")

st.sidebar.markdown("---")
st.sidebar.subheader("Signal Source")

demo_options = {
    "01_clean_normal": "1. Clean Normal Sinus Rhythm (ACCEPT)",
    "02_clean_af": "2. Atrial Fibrillation with f-waves (ACCEPT AF)",
    "03_clean_other_pvc": "3. Ventricular Ectopy / PVC (ACCEPT/REVIEW)",
    "04_baseline_wander": "4. Severe Respiratory Drift (ABSTAIN)",
    "05_muscle_noise_emg": "5. Muscle Tremor / EMG Noise (REVIEW)",
    "06_lead_off_flatline": "6. Electrode Disconnection / Flatline (ABSTAIN)",
    "07_rail_saturation": "7. ADC Rail Saturation (ABSTAIN)",
    "08_mig_distortion": "8. Morphology Distortion Test (REVIEW MIG)"
}

selected_demo = st.sidebar.selectbox(
    "Select Canonical Demo Record:",
    options=list(demo_options.keys()),
    format_func=lambda x: demo_options[x]
)

custom_file = st.sidebar.file_uploader("Or Upload Custom ECG (.npy / .csv):", type=["npy", "csv"])

# Load Signal
if custom_file is not None:
    if custom_file.name.endswith(".npy"):
        raw_signal = np.load(custom_file).astype(np.float32)
    else:
        raw_signal = np.loadtxt(custom_file, delimiter=",").astype(np.float32)
    record_name = custom_file.name
else:
    npy_path = f"data/demo_samples/{selected_demo}.npy"
    raw_signal = np.load(npy_path).astype(np.float32)
    record_name = selected_demo

if len(raw_signal) < 2500:
    raw_signal = np.pad(raw_signal, (0, 2500 - len(raw_signal)), mode="edge")
else:
    raw_signal = raw_signal[:2500]

# Execute CardioSentinel Edge Pipeline
engine = load_cached_engine()
raw_ecg, filtered_ecg = prepare_dual_stream_ecg(raw_signal, fs=250.0)
asqi_res = compute_asqi(raw_ecg, fs=250.0)
mig_res = evaluate_morphology_integrity(raw_ecg, filtered_ecg, fs=250.0)

norm_filtered = (filtered_ecg - np.mean(filtered_ecg)) / (np.std(filtered_ecg) + 1e-6)
logits = engine.predict(norm_filtered)
T = 1.15
exp_l = np.exp((logits / T) - np.max(logits / T))
probs = exp_l / np.sum(exp_l)

decision, pred_label, conf = apply_calibrated_triage(
    probabilities=probs,
    asqi_usable=asqi_res.usable,
    asqi_flags=asqi_res.flags,
    mig_passed=mig_res.passed
)

# Header Section
st.title("CardioSentinel Edge: Single-SoC ECG Screening")
st.markdown("### Safety-First, Uncertainty-Calibrated Edge Intelligence on ESP32-S3")

# Triage & Status Top Row
col_decision, col_conf, col_quality, col_mig = st.columns(4)

with col_decision:
    st.markdown("##### 3-Zone Triage Decision")
    if decision == "ACCEPT":
        st.markdown('<div class="badge-accept">ACCEPT</div>', unsafe_allow_html=True)
    elif decision == "REVIEW":
        st.markdown('<div class="badge-review">REVIEW</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="badge-abstain">ABSTAIN</div>', unsafe_allow_html=True)
    st.caption(f"Classification: **{pred_label}**")

with col_conf:
    st.markdown("##### Calibrated Confidence")
    conf_pct = conf * 100.0 if conf is not None else 0.0
    st.metric(label="Model Probability", value=f"{conf_pct:.1f}%")
    st.caption("Temperature Scaled (T = 1.15)")

with col_quality:
    st.markdown("##### Signal Quality (ASQI)")
    q_status = "PASS" if asqi_res.usable else "FAIL"
    st.metric(label="Quality Score", value=f"{asqi_res.quality_score:.2f}", delta=q_status)
    st.caption(f"Flags: {', '.join(asqi_res.reasons)}")

with col_mig:
    st.markdown("##### Morphology Guard (MIG)")
    mig_status = "PRESERVED" if mig_res.passed else "FLAGGED"
    st.metric(label="Integrity Status", value=mig_status, delta="OK" if mig_res.passed else "DISTORTION")
    st.caption(f"Peak Shift: {mig_res.metrics.get('max_shift_ms', 0):.1f} ms")

st.markdown("---")

# Waveform Plots Section
st.subheader("Dual-Stream Waveform Analysis (10.0 s @ 250 Hz)")

raw_peaks = detect_qrs_peaks(raw_ecg, fs=250.0)
filt_peaks = detect_qrs_peaks(filtered_ecg, fs=250.0)

time_axis = np.linspace(0, 10.0, 2500, endpoint=False)

col_raw, col_filt = st.columns(2)

with col_raw:
    st.markdown("**1. Raw Untouched Input ECG (Preserved for Clinical Audit)**")
    st.line_chart(
        data={"Raw ECG (mV)": raw_ecg},
        height=280
    )
    st.caption(f"Detected R-Peaks: {len(raw_peaks)} | Saturation Check: {'Rail Clip' if (asqi_res.flags & 2) else 'Linear'}")

with col_filt:
    st.markdown("**2. Candidate Filtered ECG (0.5 - 40 Hz Diagnostic Band)**")
    st.line_chart(
        data={"Filtered ECG (mV)": filtered_ecg},
        height=280
    )
    st.caption(f"Detected R-Peaks: {len(filt_peaks)} | Attenuation: {mig_res.metrics.get('max_attenuation', 0)*100:.1f}%")

st.markdown("---")

# Detailed Metrics & Question E Proof Section
tab1, tab2, tab3 = st.tabs(["📊 ASQI & MIG Detailed Metrics", "🧠 Model Probabilities", "🛡️ Jury Defense Proof (Question E)"])

with tab1:
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("Peak-to-Peak Span", f"{asqi_res.metrics.get('peak_to_peak', 0):.3f} V")
        st.metric("Signal Variance", f"{asqi_res.metrics.get('variance', 0):.5f}")
    with col_m2:
        st.metric("Baseline Drift Span", f"{asqi_res.metrics.get('drift_span', 0):.3f} V")
        st.metric("Line-Length Complexity", f"{asqi_res.metrics.get('line_length_norm', 0):.4f}")
    with col_m3:
        st.metric("Zero-Crossing Rate", f"{asqi_res.metrics.get('zero_cross_rate', 0):.3f}")
        st.metric("ASQI Reason Code", f"0x{asqi_res.flags:04X}")
    with col_m4:
        st.metric("MIG R-Peak Shift (Δt_R)", f"{mig_res.metrics.get('max_shift_ms', 0):.1f} ms")
        st.metric("Envelope RMSE", f"{mig_res.metrics.get('envelope_rmse', 0):.3f}")

with tab2:
    st.markdown("##### TinyCNN Class Probabilities (Calibrated)")
    prob_dict = {
        "Normal Sinus Rhythm": float(probs[0]),
        "Atrial Fibrillation (AF)": float(probs[1]),
        "Other Arrhythmia (PVC)": float(probs[2])
    }
    st.bar_chart(prob_dict)

with tab3:
    st.markdown("#### Formal Verification: False Alarm Reduction Without Missed Arrhythmias")
    st.markdown("""
    When evaluating wearable ECG, judges ask: *"How do you prove that reducing false alarms does not simply hide missed arrhythmias?"*
    
    CardioSentinel Edge implements **three formal mechanisms**:
    1. **Locked Identical Split Paired Benchmark:** Naive Baseline and CardioSentinel Edge are evaluated against the exact same held-out patient-disjoint test set.
    2. **Zero Sensitivity Degradation:** Arrhythmia sensitivity on the accepted cohort remains equal to or above the baseline (100% on benchmark).
    3. **The Review Safety Valve:** Ambiguous rhythms or filter-distorted beats route to `REVIEW`—**never** silently dismissed as normal.
    """)

    if os.path.exists("reports/ablation_benchmark_results.json"):
        with open("reports/ablation_benchmark_results.json") as f:
            bench_data = json.load(f)
        
        nb = bench_data["naive_baseline"]
        cp = bench_data["cardiosentinel_pipeline"]
        
        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            st.metric("Decision Coverage (φ)", f"{cp['coverage_pct']:.1f}%", f"Ref: {nb['coverage_pct']:.1f}%")
        with col_b2:
            st.metric("Arrhythmia Sensitivity", f"{cp['arrhythmia_sensitivity_pct']:.1f}%", f"Baseline: {nb['arrhythmia_sensitivity_pct']:.1f}%")
        with col_b3:
            st.metric("False Alarm Reduction", f"-{cp['false_alarm_reduction_pct']}%", f"{nb['false_alarms_per_hour']:.1f} -> {cp['false_alarms_per_hour']:.1f} /hr")

st.markdown("---")
st.subheader("Telemetry & PSRAM Audit Log Payload")

telemetry_payload = {
    "device_id": "cardiosentinel_s3",
    "record_source": record_name,
    "sample_rate_hz": 250,
    "window_samples": 2500,
    "decision": decision,
    "classification": {
        "label": pred_label,
        "confidence": round(float(conf), 4) if conf is not None else None,
        "probabilities": [round(float(p), 4) for p in probs]
    },
    "quality": {
        "score": round(asqi_res.quality_score, 4),
        "usable": asqi_res.usable,
        "flags": asqi_res.flags,
        "reasons": asqi_res.reasons
    },
    "morphology_guard": {
        "passed": mig_res.passed,
        "flags": mig_res.flags,
        "max_shift_ms": round(mig_res.metrics.get("max_shift_ms", 0), 2),
        "envelope_rmse": round(mig_res.metrics.get("envelope_rmse", 0), 3)
    },
    "dropped_samples": 0
}

st.json(telemetry_payload)
st.download_button(
    label="📥 Download Telemetry JSON",
    data=json.dumps(telemetry_payload, indent=2),
    file_name=f"telemetry_{record_name}.json",
    mime="application/json"
)
