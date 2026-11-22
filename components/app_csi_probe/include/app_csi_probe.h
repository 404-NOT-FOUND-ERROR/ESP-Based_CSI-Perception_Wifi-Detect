// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define APP_CSI_QUEUE_CAPACITY 32U
#define APP_CSI_PAYLOAD_MAX 512U
#define APP_CSI_JSON_BYTES 2048U
#define APP_CSI_MOTION_FRESH_US 250000U

typedef struct app_csi_probe app_csi_probe_t;
typedef enum {
    APP_CSI_UNLABELLED, APP_CSI_QUIET, APP_CSI_WALKING,
    APP_CSI_SELF_MOVING, APP_CSI_OCCLUDED
} app_csi_label_t;
typedef enum { APP_CSI_EMPTY, APP_CSI_FRAME, APP_CSI_BUSY } app_csi_read_t;
typedef struct {
    uint32_t network_generation;
    uint8_t bssid[6];
    uint8_t channel;
} app_csi_source_t;
typedef struct {
    uint64_t at_us; /**< Local monotonic observation time. */
    uint32_t epoch;
    bool head_locked, stationary, commanded_motion;
} app_csi_motion_t;
typedef struct {
    uint64_t callback_us;
    uint32_t hardware_rx_us; /**< Driver timestamp; wraps at 32 bits. */
    uint16_t rx_sequence;
    uint8_t source[6], channel, rx_format;
    int8_t rssi_dbm, noise_floor_dbm;
    bool first_word_invalid;
} app_csi_metadata_t;
typedef struct {
    uint32_t id, run, network_generation;
    app_csi_motion_t motion;
    app_csi_metadata_t meta;
    uint16_t length;
    uint8_t label;
    bool motion_eligible; /**< Fresh stationary/locked/no-command context only. */
    uint8_t payload[APP_CSI_PAYLOAD_MAX];
} app_csi_frame_t;
typedef struct {
    uint32_t run, queued, accepted, full_drops, contended_drops;
    uint32_t source_drops, invalid_drops, old_run_drops, discarded;
    bool active, exhausted;
} app_csi_snapshot_t;

/** Caller owns suitably aligned storage for the full callback lifetime. */
size_t app_csi_probe_storage_bytes(void);
app_csi_probe_t *app_csi_probe_init(void *storage, size_t bytes);
/** Owner calls; false means busy/invalid, retry later. Start only after stop. */
bool app_csi_probe_begin(app_csi_probe_t *s, const app_csi_source_t *source, uint32_t *run);
bool app_csi_probe_stop(app_csi_probe_t *s);
bool app_csi_probe_mark(app_csi_probe_t *s, app_csi_label_t label);
bool app_csi_probe_motion(app_csi_probe_t *s, const app_csi_motion_t *motion);
/** Callback: one try-lock, bounded copy, no wait/allocation/I/O. Run is admission token. */
bool app_csi_probe_offer(app_csi_probe_t *s, uint32_t run,
    const app_csi_metadata_t *meta, const void *payload, size_t bytes);
/** One consumer. Oversized output frame belongs in instance/heap storage. */
app_csi_read_t app_csi_probe_pop(app_csi_probe_t *s, app_csi_frame_t *out);
bool app_csi_probe_read(app_csi_probe_t *s, app_csi_snapshot_t *out);
/** Call outside Wi-Fi callback/real-time tasks. Zero means insufficient buffer/invalid. */
size_t app_csi_frame_json(const app_csi_frame_t *frame, bool simulated, char *out, size_t capacity);
