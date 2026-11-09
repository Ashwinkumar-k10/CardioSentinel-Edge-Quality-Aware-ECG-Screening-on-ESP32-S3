"""
CardioSentinel Edge - Automated Demo Video Generator
Uses Playwright to capture a comprehensive, high-resolution walkthrough
of the Real-Time Clinical ECG Telemetry SaaS Dashboard across all 8 scenarios,
and compiles it into a high-quality MP4 using ffmpeg.
"""

import os
import sys
import time
import subprocess
from playwright.sync_api import sync_playwright

def record_demo():
    print("=" * 80)
    print("CardioSentinel Edge: Automated Demo Video Recording")
    print("=" * 80)

    raw_video_dir = os.path.abspath("recordings_raw")
    os.makedirs(raw_video_dir, exist_ok=True)
    final_output_mp4 = os.path.abspath("CardioSentinel_Edge_Complete_Demo.mp4")

    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not os.path.exists(chrome_path):
        chrome_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

    print(f"[1/4] Launching Browser ({chrome_path}) with 1920x1080 Viewport...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=chrome_path,
            headless=True,
            args=["--disable-gpu", "--no-sandbox"]
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=raw_video_dir,
            record_video_size={"width": 1920, "height": 1080}
        )

        page = context.new_page()
        print("[2/4] Connecting to Clinical Telemetry Gateway (http://localhost:8000)...")
        page.goto("http://localhost:8000", wait_until="networkidle")
        time.sleep(2)

        scenarios = [
            ("01_clean_normal", "1. Clean Normal Sinus Rhythm (ACCEPT)", 4),
            ("02_clean_af", "2. Atrial Fibrillation with f-waves (ACCEPT AF)", 4),
            ("03_clean_other_pvc", "3. Ventricular Ectopy / PVC (ACCEPT/REVIEW)", 4),
            ("04_baseline_wander", "4. Severe Respiratory Drift (ABSTAIN Drift)", 4),
            ("05_muscle_noise_emg", "5. Muscle Tremor / EMG Noise (REVIEW EMG)", 4),
            ("06_lead_off_flatline", "6. Disconnected Electrode / Flatline (ABSTAIN)", 4),
            ("07_rail_saturation", "7. ADC Rail Saturation (ABSTAIN Rail)", 4),
            ("08_mig_distortion", "8. Filter Distortion Pacemaker Spike (REVIEW MIG)", 5),
        ]

        print("[3/4] Exploring Dashboard Features across All 8 Clinical Scenarios...")

        for scenario_id, desc, duration in scenarios:
            print(f"  -> Demonstrating: {desc}...")
            # Select scenario
            page.select_option("#scenarioSelector", scenario_id)
            time.sleep(1.0)

            # Scroll slightly to view scope and metrics
            page.evaluate("window.scrollTo({top: 150, behavior: 'smooth'});")
            time.sleep(duration / 2)

            # Scroll to hardware execution and ASQI metrics
            page.evaluate("window.scrollTo({top: 450, behavior: 'smooth'});")
            time.sleep(duration / 2)

            # Scroll back to top
            page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'});")
            time.sleep(1.0)

        # Test View Mode switch to Sweep
        print("  -> Testing Sweep Mode & Freeze Controls...")
        try:
            page.click("#viewModeSweep")
            time.sleep(2.0)
            page.click("#viewModeWindow")
            time.sleep(1.5)
        except Exception as e:
            print(f"     View mode toggle note: {e}")

        # Final showcase
        page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'});")
        time.sleep(2)

        video_path = page.video.path()
        context.close()
        browser.close()

    print(f"[4/4] Video captured: {video_path}")
    print("[PROCESSING] Converting and optimizing to final MP4 with ffmpeg...")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        final_output_mp4
    ]

    subprocess.check_call(cmd)
    file_size_mb = os.path.getsize(final_output_mp4) / (1024 * 1024)
    print("=" * 80)
    print(f"[SUCCESS] Demo Video Generated Successfully!")
    print(f"File Path: {final_output_mp4}")
    print(f"Size: {file_size_mb:.2f} MB")
    print("=" * 80)

if __name__ == "__main__":
    record_demo()
