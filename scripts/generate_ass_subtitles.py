"""
Refined Subtitle Generator with Short Phrases and Compact Modern Typography
"""

import os
import wave
import glob

# The 10 segments with their detailed sentences broken into short, punchy lines
SEGMENTS = [
    {
        "seg_idx": 0,
        "wav": "demo_audio/seg_00.wav",
        "phrases": [
            "Welcome to CardioSentinel Edge — Single-SoC Wearable ECG Screening.",
            "Hosted on ESP32-S3 (Xtensa Dual-Core) paired with TI ADS1292R AFE.",
            "Linear-time quality verification, morphology protection & 3-zone triage."
        ]
    },
    {
        "seg_idx": 1,
        "wav": "demo_audio/seg_01.wav",
        "phrases": [
            "Scenario 1: Clean Normal Sinus Rhythm (250 Hz continuous sampling).",
            "Dual-stream scope displays raw vs candidate-filtered waveform.",
            "All ASQI heuristics pass, MIG distortion zero -> ACCEPT triage."
        ]
    },
    {
        "seg_idx": 2,
        "wav": "demo_audio/seg_02.wav",
        "phrases": [
            "Scenario 2: Atrial Fibrillation with irregular RR intervals & f-waves.",
            "On-device FP32 1D-CNN infers in 34 ms on ESP32-S3 hardware FPU.",
            "Classified accurately with high confidence -> ACCEPT AF."
        ]
    },
    {
        "seg_idx": 3,
        "wav": "demo_audio/seg_03.wav",
        "phrases": [
            "Scenario 3: Ventricular Ectopy & Premature Ventricular Contractions.",
            "Abnormal beat shape identified; raw snippet preserved in 8 MB PSRAM."
        ]
    },
    {
        "seg_idx": 4,
        "wav": "demo_audio/seg_04.wav",
        "phrases": [
            "Scenario 4: Severe Respiratory Drift (Ambulatory Baseline Wander).",
            "Linear-time quality gate flags drift -> Safely routes to ABSTAIN.",
            "Prevents false alarms without unneeded emergency notifications."
        ]
    },
    {
        "seg_idx": 5,
        "wav": "demo_audio/seg_05.wav",
        "phrases": [
            "Scenario 5: High-Frequency Muscle Tremor & EMG Artifact.",
            "Quality gate isolates noise -> Routes recording to REVIEW for safety."
        ]
    },
    {
        "seg_idx": 6,
        "wav": "demo_audio/seg_06.wav",
        "phrases": [
            "Scenario 6: Disconnected Electrode / Flatline Simulation.",
            "Zero amplitude detected -> Immediate ABSTAIN (Zero false reassurance)."
        ]
    },
    {
        "seg_idx": 7,
        "wav": "demo_audio/seg_07.wav",
        "phrases": [
            "Scenario 7: ADC Rail Saturation Clipping.",
            "Amplifier rail limits exceeded -> Immediate ABSTAIN to protect AI."
        ]
    },
    {
        "seg_idx": 8,
        "wav": "demo_audio/seg_08.wav",
        "phrases": [
            "Scenario 8: Morphology Integrity Guard (MIG) in Action.",
            "Digital filter attenuates pacemaker spike -> MIG detects discrepancy.",
            "Automatic acceptance revoked -> Safely forced to REVIEW."
        ]
    },
    {
        "seg_idx": 9,
        "wav": "demo_audio/seg_09.wav",
        "phrases": [
            "Summary: 85.5% coverage, zero missed arrhythmias, 16/16 tests passing.",
            "100% bit-accurate firmware parity, $14.10 BOM, 20.7h battery lifetime."
        ]
    }
]

def format_ass_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int((sec - int(sec)) * 100)
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"

def generate_ass_subtitles():
    ass_header = """[Script Info]
Title: CardioSentinel Edge Clinical Telemetry Demo
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ModernCaption,Segoe UI,28,&H00FFFFFF,&H000000FF,&H00000000,&HB0080C14,-1,0,0,0,100,100,0,0,3,1.5,0,2,40,40,25,1
Style: TopBadge,Segoe UI,22,&H0000F5FF,&H000000FF,&H00000000,&HB00F172A,-1,0,0,0,100,100,0,0,3,1.2,0,8,40,40,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    current_time = 0.5  # matches recording start offset

    for seg in SEGMENTS:
        wav_path = seg["wav"]
        with wave.open(wav_path) as w:
            dur = w.getnframes() / float(w.getframerate())
        total_display_time = dur + 1.2
        
        phrases = seg["phrases"]
        n_phrases = len(phrases)
        phrase_dur = dur / n_phrases

        for p_idx, text in enumerate(phrases):
            p_start = current_time + (p_idx * phrase_dur)
            p_end = p_start + phrase_dur - 0.15
            start_str = format_ass_time(p_start)
            end_str = format_ass_time(p_end)
            events.append(f"Dialogue: 0,{start_str},{end_str},ModernCaption,,0,0,0,,{text}")

        current_time += total_display_time

    ass_content = ass_header + "\n".join(events) + "\n"
    with open("CardioSentinel_Modern_Subtitles.ass", "w", encoding="utf-8") as f:
        f.write(ass_content)
    print("Created CardioSentinel_Modern_Subtitles.ass successfully!")

if __name__ == "__main__":
    generate_ass_subtitles()
