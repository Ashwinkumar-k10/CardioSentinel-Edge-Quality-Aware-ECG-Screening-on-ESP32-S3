/**
 * CardioSentinel Edge - Native Host Harness for Firmware Algorithms
 * Compiles with standard GCC for bit-accurate unit testing and host-board parity verification.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../firmware/esp32s3/main/ring_buffer.h"
#include "../firmware/esp32s3/main/signal_quality.h"
#include "../firmware/esp32s3/main/morphology_guard.h"
#include "../firmware/esp32s3/main/inference.h"
#include "../firmware/esp32s3/main/decision_engine.h"

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <path_to_raw_ecg_floats.bin>\n", argv[0]);
        return 1;
    }

    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        fprintf(stderr, "Cannot open input file: %s\n", argv[1]);
        return 1;
    }

    float raw[2500];
    size_t read_count = fread(raw, sizeof(float), 2500, f);
    fclose(f);

    if (read_count != 2500) {
        fprintf(stderr, "Expected 2500 float32 samples, read %zu\n", read_count);
        return 1;
    }

    // 1. Dual-stream conservative filter
    float filt[2500];
    for (size_t i = 2; i < 2498; i++) {
        filt[i] = 0.1f * raw[i - 2] + 0.2f * raw[i - 1] + 0.4f * raw[i] + 0.2f * raw[i + 1] + 0.1f * raw[i + 2];
    }
    filt[0] = raw[0];
    filt[1] = raw[1];
    filt[2498] = raw[2498];
    filt[2499] = raw[2499];

    // 2. ASQI
    asqi_init();
    asqi_result_t asqi_res = asqi_evaluate_window(raw, 2500, 250.0f);

    // 3. MIG
    mig_init();
    mig_result_t mig_res = mig_evaluate_window(raw, filt, 2500, 250.0f);

    // 4. Inference
    tinycnn_inference_init();
    inference_result_t infer_res = tinycnn_predict(filt, 2500);

    // 5. Decision
    screening_event_t event = evaluate_screening_decision(
        &asqi_res,
        &mig_res,
        &infer_res,
        0,
        1
    );

    // Print standardized JSON
    char json_buf[512];
    format_telemetry_json(&event, &infer_res, json_buf, sizeof(json_buf));
    printf("%s\n", json_buf);

    return 0;
}
