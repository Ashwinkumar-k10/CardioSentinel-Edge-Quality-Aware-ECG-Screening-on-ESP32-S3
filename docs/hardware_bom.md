# CardioSentinel Edge — Hardware Bill of Materials (BOM) & Wiring
**TECHgium Challenge 26 Research Prototype**

## 1. System Bill of Materials

| Component | Part / Module | Function | Approx Cost (USD) | Source / Notes |
|---|---|---|:---:|---|
| **MCU Board** | ESP32-S3-DevKitC-1 (ESP32-S3-WROOM-1 / N8R8) | Main processor, dual-core 240 MHz, 8 MB Octal PSRAM, 8 MB Flash, BLE 5.0 | \$4.50 | Espressif / Mouser / DigiKey |
| **ECG AFE** | TI ADS1292R Evaluation Board / Breakout | 2-channel 24-bit ECG Analog Front End with internal test signal & lead-off | \$12.00 | Texas Instruments / Tindie |
| **Power Source** | 3.7V 300 mAh LiPo Battery + TP4056 LDO (or Bench 3.3V) | Portable power with low-dropout regulation | \$3.50 | Generic |
| **Logic / Jumper** | Ribbon Cables & 0.1" Breadboard Headers | Signal interconnection (SPI + GPIO) | \$1.00 | Lab stock |
| **Signal Source** | Isolated Benchtop ECG Simulator / Waveform DAC | Pre-recorded / synthetic ECG playback (No human electrode connection) | Lab equipment | Certified bench equipment |
| **Total Hardware Cost** | — | **Single-Processor Wearable Intelligence** | **~\$21.00** | Fraction of multi-processor solutions |

---

## 2. Pinout & Interconnection Matrix

| ADS1292R Pin | ESP32-S3 Pin | Signal Name | Description |
|:---:|:---:|:---:|---|
| **VCC / 3V3** | 3V3 | Power | Regulated 3.3V power rail |
| **GND** | GND | Ground | Common system ground |
| **MOSI (DIN)** | GPIO 11 | SPI2_MOSI | Master Out Slave In (Command transmission) |
| **MISO (DOUT)**| GPIO 13 | SPI2_MISO | Master In Slave Out (24-bit ECG sample streaming) |
| **SCLK** | GPIO 12 | SPI2_SCLK | SPI Clock (1 MHz operating rate) |
| **CS** | GPIO 10 | SPI2_CS | Active-Low Chip Select |
| **/DRDY** | GPIO 4 | GPIO_INTR | Hardware Data-Ready Interrupt (Triggers DMA ISR) |
| **RESET** | GPIO 5 | GPIO_OUT | Hardware Reset Line |
| **START** | GPIO 6 | GPIO_OUT | Conversion Start Control Line |

---

## 3. Electrical Characteristics
- **SPI Mode:** Mode 1 (CPOL = 0, CPHA = 1)
- **Data Rate:** 250 samples/second (SPS)
- **Word Size:** 24-bit two's complement per channel (3 bytes status + 3 bytes Ch1 + 3 bytes Ch2 = 9 bytes/packet)
- **Interrupt Jitter:** $< 2.4\,\mu\text{s}$ via FreeRTOS high-priority ISR on Core 0.
