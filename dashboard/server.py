"""
CardioSentinel Edge - Real-Time Clinical ECG Telemetry SaaS Backend
TECHgium Challenge 26 Research Prototype

High-performance FastAPI & WebSocket backend serving:
- 60 FPS HTML5 Canvas medical scope stream
- ASQI, MIG & TinyCNN calibrated inference
- PSRAM audit logging & FHIR R4 DiagnosticReport generation
"""

import os
import sys
import json
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from research.asqi import compute_asqi
from research.morphology_guard import evaluate_morphology_integrity, detect_qrs_peaks
from research.preprocessing import prepare_dual_stream_ecg
from research.calibrate import apply_calibrated_triage
from research.models_tiny import CardioSentinelTinyCNN, TinyCNNFusedNumPyEngine
from research.quantize_export import export_fused_c_header
import torch

app = FastAPI(
    title="CardioSentinel Cloud & Edge Gateway",
    description="Real-Time Clinical Telemetry & Triage SaaS for ESP32-S3 ECG Screening",
    version="2.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Cached Inference Engine
g_engine = None

def get_engine():
    global g_engine
    if g_engine is None:
        model = CardioSentinelTinyCNN()
        weights_path = "models/tinycnn_best.pth"
        if os.path.exists(weights_path):
            model.load_state_dict(torch.load(weights_path, weights_only=True))
        fused = export_fused_c_header(model, "firmware/esp32s3/models/tinycnn_weights.h")
        g_engine = TinyCNNFusedNumPyEngine(fused["fused_arrays"])
    return g_engine


# Serve Frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return "<h3>CardioSentinel Server Running. Static assets loading...</h3>"


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/api/health")
async def health_check():
    return {
        "status": "ONLINE",
        "gateway": "CardioSentinel_Edge_Gateway_v2.4",
        "device_target": "ESP32-S3-WROOM-1-N8R8",
        "sample_rate_hz": 250,
        "runtime_sram_kb": 33.7,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/scenarios")
async def get_scenarios():
    manifest_path = "data/demo_samples/manifest.json"
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            return json.load(f)
    return {"error": "Manifest not found. Run make_demo_examples.py first."}


@app.get("/api/scenario/{name}")
async def get_scenario_telemetry(name: str):
    npy_path = f"data/demo_samples/{name}.npy"
    if not os.path.exists(npy_path):
        raise HTTPException(status_code=404, detail=f"Scenario record '{name}' not found")

    raw_signal = np.load(npy_path).astype(np.float32)
    if len(raw_signal) < 2500:
        raw_signal = np.pad(raw_signal, (0, 2500 - len(raw_signal)), mode="edge")
    else:
        raw_signal = raw_signal[:2500]

    # Preprocessing & Dual Stream
    raw_ecg, filtered_ecg = prepare_dual_stream_ecg(raw_signal, fs=250.0)
    
    # QRS Peak Detection
    peaks = detect_qrs_peaks(filtered_ecg, fs=250.0)
    
    # Compute Instantaneous Heart Rate
    if len(peaks) > 1:
        rr_diffs = np.diff(peaks) / 250.0
        mean_rr = float(np.mean(rr_diffs))
        bpm = int(round(60.0 / mean_rr)) if mean_rr > 0 else 72
    else:
        bpm = 72

    # ASQI & MIG Evaluation
    asqi_res = compute_asqi(raw_ecg, fs=250.0)
    mig_res = evaluate_morphology_integrity(raw_ecg, filtered_ecg, fs=250.0)

    # Inference via TinyCNN
    engine = get_engine()
    norm_filt = (filtered_ecg - np.mean(filtered_ecg)) / (np.std(filtered_ecg) + 1e-6)
    logits = engine.predict(norm_filt)
    T = 1.15
    exp_l = np.exp((logits / T) - np.max(logits / T))
    probs = exp_l / np.sum(exp_l)

    # 3-Zone Triage Policy
    decision, pred_label, conf = apply_calibrated_triage(
        probabilities=probs,
        asqi_usable=asqi_res.usable,
        asqi_flags=asqi_res.flags,
        mig_passed=mig_res.passed
    )

    telemetry_payload = {
        "device_id": "CS-ESP32S3-N8R8-7F2A",
        "scenario": name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sample_rate_hz": 250,
        "window_samples": 2500,
        "heart_rate_bpm": bpm,
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
            "reasons": asqi_res.reasons,
            "variance": round(float(asqi_res.metrics.get("variance", 0)), 5),
            "peak_to_peak": round(float(asqi_res.metrics.get("peak_to_peak", 0)), 3),
            "drift_span": round(float(asqi_res.metrics.get("drift_span", 0)), 3),
            "line_length_norm": round(float(asqi_res.metrics.get("line_length_norm", 0)), 4)
        },
        "morphology_guard": {
            "passed": mig_res.passed,
            "flags": mig_res.flags,
            "max_shift_ms": round(float(mig_res.metrics.get("max_shift_ms", 0)), 2),
            "max_attenuation": round(float(mig_res.metrics.get("max_attenuation", 0)), 3),
            "envelope_rmse": round(float(mig_res.metrics.get("envelope_rmse", 0)), 3)
        },
        "dropped_samples": 0
    }

    return {
        "raw": raw_ecg.tolist(),
        "filtered": filtered_ecg.tolist(),
        "peaks": peaks.tolist(),
        "telemetry": telemetry_payload
    }


@app.get("/api/export_fhir/{name}")
async def export_fhir_diagnostic_report(name: str):
    """
    Generates an international HL7 / FHIR R4 DiagnosticReport resource
    representing the edge screening impression, ASQI quality, and triage decision.
    """
    res = await get_scenario_telemetry(name)
    tel = res["telemetry"]

    fhir_report = {
        "resourceType": "DiagnosticReport",
        "id": f"cardiosentinel-rep-{name}-{int(datetime.now().timestamp())}",
        "status": "preliminary",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                        "code": "CG",
                        "display": "Cardiology / Ambulatory Screening"
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "8601-7",
                    "display": "Ambulatory single-lead ECG telemetry panel"
                }
            ],
            "text": "CardioSentinel Single-SoC Edge Screening Evaluation"
        },
        "subject": {
            "reference": "Patient/PT-84920",
            "display": "TECHgium Evaluation Subject #04"
        },
        "effectiveDateTime": tel["timestamp"],
        "issued": datetime.now(timezone.utc).isoformat(),
        "performer": [
            {
                "display": "CardioSentinel Edge MCU (ESP32-S3 + ADS1292R)"
            }
        ],
        "conclusion": f"Edge Screening Impression: {tel['classification']['label']} (Triage Zone: {tel['decision']})",
        "conclusionCode": [
            {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "426783006" if "AF" in tel['classification']['label'] else "251146004",
                        "display": tel['classification']['label']
                    }
                ]
            }
        ],
        "contained": [
            {
                "resourceType": "Observation",
                "id": "obs-hr",
                "status": "final",
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}]
                },
                "valueQuantity": {
                    "value": tel["heart_rate_bpm"],
                    "unit": "beats/minute",
                    "system": "http://unitsofmeasure.org",
                    "code": "/min"
                }
            },
            {
                "resourceType": "Observation",
                "id": "obs-asqi",
                "status": "final",
                "code": {
                    "text": "Adaptive Signal Quality Index (ASQI)"
                },
                "valueQuantity": {
                    "value": tel["quality"]["score"],
                    "unit": "score [0-1]"
                },
                "interpretation": [
                    {"text": "USABLE" if tel["quality"]["usable"] else "UNINTERPRETABLE"}
                ]
            },
            {
                "resourceType": "Observation",
                "id": "obs-mig",
                "status": "final",
                "code": {
                    "text": "Morphology Integrity Guard (MIG)"
                },
                "interpretation": [
                    {"text": "MORPHOLOGY_PRESERVED" if tel["morphology_guard"]["passed"] else "DISTORTION_DETECTED"}
                ]
            }
        ],
        "extension": [
            {
                "url": "https://cardiosentinel.org/fhir/triage-zone",
                "valueString": tel["decision"]
            },
            {
                "url": "https://cardiosentinel.org/fhir/confidence-calibrated",
                "valueDecimal": tel["classification"]["confidence"] or 0.0
            }
        ]
    }

    return JSONResponse(content=fhir_report, media_type="application/fhir+json")


def start_server(host: str = "0.0.0.0", port: int = 8000):
    print("=" * 75)
    print("CardioSentinel Edge - Real-Time Telemetry SaaS Server")
    print(f"Launching on: http://localhost:{port}")
    print("=" * 75)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server(host="127.0.0.1", port=8000)
