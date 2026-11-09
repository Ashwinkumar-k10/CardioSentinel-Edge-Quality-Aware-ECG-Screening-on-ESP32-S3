"""
CardioSentinel Edge - True Hardware Serial/UART Loopback Verification Tool
TECHgium Challenge 26 Research Prototype

Connects to a physical ESP32-S3 development board over USB-UART, streams raw
250 Hz ECG windows, and measures live on-chip execution latency and decision outputs.
"""

import os
import sys
import time
import json
import argparse
import numpy as np

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)


def main():
    parser = argparse.ArgumentParser(description="CardioSentinel Edge - Hardware Serial Loopback Test")
    parser.add_argument("--port", type=str, default=None, help="ESP32-S3 Serial Port (e.g., COM3, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="UART Baud Rate (default: 115200)")
    parser.add_argument("--sample", type=str, default="data/demo_samples/01_clean_normal.npy", help="Test vector .npy")
    parser.add_argument("--mock-dry-run", action="store_true", help="Perform dry run without physical serial connection")
    args = parser.parse_args()

    print("=" * 80)
    print("CardioSentinel Edge - Physical ESP32-S3 Hardware Loopback Verification")
    print("=" * 80)

    try:
        import serial
        import serial.tools.list_ports
    except ImportError:
        print("[WARN] 'pyserial' package not installed. Run: pip install pyserial")
        return

    # Check available ports if not provided
    if not args.port:
        available_ports = [p.device for p in serial.tools.list_ports.comports()]
        print(f"[SCAN] Detected Serial Ports: {available_ports if available_ports else 'None detected'}")
        if not available_ports:
            print("\n[INFO] No physical ESP32-S3 board detected on USB ports.")
            print("       Connect your ESP32-S3-WROOM-1 board via USB-C to run physical bench verification.")
            print("       Example command once connected: python scripts/test_board_hardware_loopback.py --port COM3\n")
            return
        args.port = available_ports[0]
        print(f"[INFO] Auto-selected primary port: {args.port}")

    sample_path = os.path.join(REPO_ROOT, args.sample) if not os.path.isabs(args.sample) else args.sample
    if not os.path.exists(sample_path):
        print(f"[ERROR] Sample vector not found: {sample_path}")
        return

    raw_ecg = np.load(sample_path).astype(np.float32)
    print(f"[VECTOR] Loaded {len(raw_ecg)} float32 samples from: {os.path.basename(sample_path)}")

    print(f"[CONNECT] Opening UART connection to ESP32-S3 on {args.port} @ {args.baud} baud...")
    try:
        ser = serial.Serial(args.port, args.baud, timeout=3.0)
        time.sleep(1.0)  # Reset settle time

        # Flush buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        print("[TX] Streaming 2,500 float samples to ESP32-S3 circular buffer...")
        t_tx_start = time.perf_counter()
        ser.write(raw_ecg.tobytes())
        ser.flush()

        print("[RX] Awaiting on-chip inference and telemetry JSON packet...")
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        t_rx_end = time.perf_counter()

        ser.close()

        if line and line.startswith("{"):
            telemetry = json.loads(line)
            print("\n" + "-" * 80)
            print("ON-CHIP HARDWARE TELEMETRY RECEIVED:")
            print("-" * 80)
            print(json.dumps(telemetry, indent=2))
            print("-" * 80)
            print(f"[SUCCESS] Total Round-Trip Latency: {(t_rx_end - t_tx_start)*1000:.2f} ms")
            print(f"[SUCCESS] Board Decision: {telemetry.get('decision')} | Class: {telemetry.get('classification', {}).get('label')}")
        else:
            print(f"[RESP] Raw board response: {line if line else 'No response within timeout'}")

    except Exception as e:
        print(f"[HARDWARE ERROR] Failed serial communication: {e}")


if __name__ == "__main__":
    main()
