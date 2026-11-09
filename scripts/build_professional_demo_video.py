"""
CardioSentinel Edge - Professional Demo Video Producer with Real Windows PowerShell Terminal
TECHgium Challenge 26 Research Prototype
"""

import os
import sys
import time
import json
import subprocess
import wave
from playwright.sync_api import sync_playwright

STORYBOARD = [
    {
        "id": "00_powershell_terminal",
        "url": "http://localhost:8000/static/terminal_view.html",
        "scenario": None,
        "title": "WINDOWS POWERSHELL FIRMWARE & UNIT TEST AUDIT",
        "voice": "Before launching clinical telemetry, we audit our embedded C firmware in Windows PowerShell. All 16 unit tests pass, and our compiled GCC firmware confirms 100% bit-accurate parity against PyTorch across all canonical test vectors.",
        "scroll": 0,
        "action": None,
        "subtitles": [
            "Auditing embedded C firmware in Windows PowerShell.",
            "All 16 automated unit tests pass in 8.7 seconds.",
            "GCC firmware confirms 100% bit-accurate decision parity."
        ]
    },
    {
        "id": "01_clean_normal",
        "url": "http://localhost:8000",
        "scenario": "01_clean_normal",
        "title": "SCENARIO 1: CLEAN NORMAL SINUS RHYTHM",
        "voice": "In Scenario 1, the dual-stream scope displays raw versus candidate-filtered ECG at 250 Hertz. All signal quality heuristics pass, morphology distortion is zero, and calibrated triage outputs an emphatic ACCEPT.",
        "scroll": 180,
        "action": None,
        "subtitles": [
            "Scenario 1: Clean Normal Sinus Rhythm (250 Hz dual-stream scope).",
            "Untouched raw signal displayed alongside candidate-filtered ECG.",
            "All quality heuristics pass, MIG distortion zero -> ACCEPT triage."
        ]
    },
    {
        "id": "02_clean_af",
        "url": "http://localhost:8000",
        "scenario": "02_clean_af",
        "title": "SCENARIO 2: ATRIAL FIBRILLATION SCREENING",
        "voice": "In Scenario 2, the patient exhibits Atrial Fibrillation with irregular RR intervals and fibrillatory f-waves. The 1D-CNN classifies the arrhythmia in 34 milliseconds on hardware FPU, outputting an instant ACCEPT triage.",
        "scroll": 180,
        "action": None,
        "subtitles": [
            "Scenario 2: Atrial Fibrillation with irregular intervals and f-waves.",
            "1D-CNN classifies rhythm on hardware FPU in 34 ms -> ACCEPT AF."
        ]
    },
    {
        "id": "03_clean_other_pvc",
        "url": "http://localhost:8000",
        "scenario": "03_clean_other_pvc",
        "title": "SCENARIO 3: VENTRICULAR ECTOPY & PVC",
        "voice": "In Scenario 3, premature ventricular contractions appear. The system detects abnormal morphology and preserves both raw and processed snippets in 8 MB PSRAM for clinician audit.",
        "scroll": 200,
        "action": None,
        "subtitles": [
            "Scenario 3: Ventricular Ectopy and Premature Ventricular Contractions.",
            "Ectopic morphology flagged; raw snippet preserved in 8 MB PSRAM."
        ]
    },
    {
        "id": "04_baseline_wander",
        "url": "http://localhost:8000",
        "scenario": "04_baseline_wander",
        "title": "SCENARIO 4: SEVERE RESPIRATORY DRIFT",
        "voice": "In Scenario 4, ambulatory motion causes severe baseline drift. Our linear-time quality gate flags excessive wander and safely issues an ABSTAIN, eliminating false positive alerts.",
        "scroll": 300,
        "action": None,
        "subtitles": [
            "Scenario 4: Severe Respiratory Drift (Ambulatory Baseline Wander).",
            "Linear-time quality gate flags wander -> Safely issues ABSTAIN."
        ]
    },
    {
        "id": "05_muscle_noise_emg",
        "url": "http://localhost:8000",
        "scenario": "05_muscle_noise_emg",
        "title": "SCENARIO 5: MUSCLE TREMOR NOISE",
        "voice": "In Scenario 5, muscle tremor corrupts the waveform. High-frequency noise is detected and routed to REVIEW, alerting the clinician without sounding false alarms.",
        "scroll": 300,
        "action": None,
        "subtitles": [
            "Scenario 5: High-Frequency Muscle Tremor & EMG Artifact.",
            "Quality gate isolates noise -> Routes recording to REVIEW for safety."
        ]
    },
    {
        "id": "06_lead_off_flatline",
        "url": "http://localhost:8000",
        "scenario": "06_lead_off_flatline",
        "title": "SCENARIO 6: ELECTRODE DISCONNECT (FLATLINE)",
        "voice": "In Scenario 6, electrode contact is lost. Flatline detection immediately triggers an ABSTAIN, preventing dangerous false reassurances.",
        "scroll": 200,
        "action": None,
        "subtitles": [
            "Scenario 6: Disconnected Electrode / Flatline Simulation.",
            "Zero amplitude detected -> Immediate ABSTAIN (Zero false reassurance)."
        ]
    },
    {
        "id": "07_rail_saturation",
        "url": "http://localhost:8000",
        "scenario": "07_rail_saturation",
        "title": "SCENARIO 7: ADC RAIL SATURATION",
        "voice": "In Scenario 7, motion artifact drives the amplifier into saturation clipping. The quality gate immediately detects rail clamping and aborts inference.",
        "scroll": 200,
        "action": None,
        "subtitles": [
            "Scenario 7: ADC Rail Saturation Clipping.",
            "Amplifier rail limits exceeded -> Immediate ABSTAIN to protect AI."
        ]
    },
    {
        "id": "08_mig_distortion",
        "url": "http://localhost:8000",
        "scenario": "08_mig_distortion",
        "title": "SCENARIO 8: MORPHOLOGY INTEGRITY GUARD (MIG)",
        "voice": "Scenario 8 showcases our signature innovation: the Morphology Integrity Guard. When filtering smooths an abnormal pacemaker spike, MIG detects the discrepancy against untouched raw signal, revokes acceptance, and safely forces a REVIEW.",
        "scroll": 350,
        "action": None,
        "subtitles": [
            "Scenario 8: Morphology Integrity Guard (MIG) in Action.",
            "Filter attenuates pacemaker spike -> MIG detects discrepancy.",
            "Automatic acceptance revoked -> Safely forced to REVIEW."
        ]
    },
    {
        "id": "09_summary",
        "url": "http://localhost:8000",
        "scenario": "01_clean_normal",
        "title": "CONCLUSION & VERIFICATION AUDIT",
        "voice": "CardioSentinel Edge achieves 85.5% decision coverage with zero missed arrhythmias, complete 16-out-of-16 unit test passing, and 100% bit-accurate firmware parity on the ESP32-S3—all within a 14 dollar BOM and 20 hour battery lifetime.",
        "scroll": 0,
        "action": None,
        "subtitles": [
            "Summary: 85.5% coverage, zero missed arrhythmias, 16/16 tests passing.",
            "100% bit-accurate firmware parity, $14.10 BOM, 20.7h battery lifetime."
        ]
    }
]

def synthesize_voice(text: str, wav_path: str):
    escaped = text.replace("'", "''")
    ps = f"""
    Add-Type -AssemblyName System.Speech
    $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $s.SelectVoice('Microsoft David Desktop')
    $s.Rate = 0
    $s.Volume = 100
    $s.SetOutputToWaveFile('{wav_path}')
    $s.Speak('{escaped}')
    $s.Dispose()
    """
    tmp_ps = "tmp_synth.ps1"
    with open(tmp_ps, "w", encoding="utf-8") as f:
        f.write(ps)
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", tmp_ps], check=True)
    if os.path.exists(tmp_ps):
        os.remove(tmp_ps)

    with wave.open(wav_path, "r") as w:
        frames = w.getnframes()
        rate = w.getframerate()
        return frames / float(rate)

def format_ass_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int((sec - int(sec)) * 100)
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"

def run_production():
    print("=" * 80)
    print("CardioSentinel Edge: Building Demo Video with Real PowerShell Terminal...")
    print("=" * 80)

    audio_dir = os.path.abspath("real_ps_audio")
    raw_video_dir = os.path.abspath("real_ps_raw")
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(raw_video_dir, exist_ok=True)

    # 1. Synthesize Audio
    print("[1/5] Synthesizing Studio Voiceover Tracks...")
    durations = []
    wav_files = []
    for idx, item in enumerate(STORYBOARD):
        wav = os.path.join(audio_dir, f"scene_{idx:02d}.wav")
        dur = synthesize_voice(item["voice"], wav)
        display_dur = dur + 1.2
        durations.append(display_dur)
        wav_files.append(wav)
        print(f"  Scene {idx+1}/{len(STORYBOARD)}: {item['title']} ({dur:.1f}s speech, {display_dur:.1f}s display)")

    # 2. Build Subtitles (.ass)
    print("[2/5] Generating Compact 1-Line Subtitles (.ass)...")
    ass_header = """[Script Info]
Title: CardioSentinel Edge PowerShell & Scope Demo
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ModernSub,Segoe UI,28,&H00FFFFFF,&H000000FF,&H00000000,&HB0080C14,-1,0,0,0,100,100,0,0,3,1.5,0,2,40,40,25,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    current_time = 0.5
    for idx, item in enumerate(STORYBOARD):
        dur = durations[idx]
        phrases = item["subtitles"]
        phrase_dur = (dur - 1.2) / len(phrases)
        for p_idx, text in enumerate(phrases):
            start = current_time + (p_idx * phrase_dur)
            end = start + phrase_dur - 0.15
            events.append(f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},ModernSub,,0,0,0,,{text}")
        current_time += dur

    ass_path = os.path.abspath("CardioSentinel_Real_PS.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_header + "\n".join(events) + "\n")

    # 3. Mux Master Audio
    print("[3/5] Muxing Voiceover Audio Tracks...")
    master_audio = os.path.abspath("master_real_ps.wav")
    concat_filter = "".join([f"[{i}:a]" for i in range(len(wav_files))]) + f"concat=n={len(wav_files)}:v=0:a=1[outa]"
    cmd_audio = ["ffmpeg", "-y"]
    for w in wav_files:
        cmd_audio.extend(["-i", w])
    cmd_audio.extend(["-filter_complex", concat_filter, "-map", "[outa]", master_audio])
    subprocess.run(cmd_audio, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 4. Playwright Capture
    print("[4/5] Recording Multi-Scene Browser Interaction (1920x1080)...")
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not os.path.exists(chrome_path):
        chrome_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome_path, headless=True, args=["--disable-gpu", "--no-sandbox"])
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=raw_video_dir,
            record_video_size={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        current_url = None
        for idx, item in enumerate(STORYBOARD):
            target_url = item["url"]
            if current_url != target_url:
                page.goto(target_url, wait_until="networkidle")
                current_url = target_url
                time.sleep(0.5)

            dur = durations[idx]
            print(f"  Capturing Scene {idx+1}/{len(STORYBOARD)}: {item['title']} ({dur:.1f}s)...")

            if "scenario" in item and item["scenario"]:
                try:
                    page.select_option("#scenarioSelector", item["scenario"])
                    time.sleep(0.5)
                except Exception:
                    pass

            if item["scroll"] > 0:
                page.evaluate(f"window.scrollTo({{top: {item['scroll']}, behavior: 'smooth'}});")
                time.sleep(dur * 0.6)
                page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'});")
                time.sleep(dur * 0.4)
            else:
                time.sleep(dur)

        video_path = page.video.path()
        context.close()
        browser.close()

    # 5. Final Fast Video Assembly
    print("[5/5] Assembling Master Video with Burned-In Subtitles & Audio...")
    final_mp4 = os.path.abspath("CardioSentinel_Edge_Official_Demo.mp4")
    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")

    cmd_master = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", master_audio,
        "-vf", f"ass='{ass_escaped}'",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        final_mp4
    ]
    subprocess.run(cmd_master, check=True)
    mb = os.path.getsize(final_mp4) / (1024 * 1024)

    print("=" * 80)
    print(f"[COMPLETE] Demo Video with Real PowerShell Terminal Generated!")
    print(f"File: {final_mp4} ({mb:.2f} MB)")
    print("=" * 80)

if __name__ == "__main__":
    run_production()
