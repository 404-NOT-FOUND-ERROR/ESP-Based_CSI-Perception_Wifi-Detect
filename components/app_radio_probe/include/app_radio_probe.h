// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "app_network_link.h"
#include <stddef.h>

#define APP_RADIO_PROBE_CAPACITY 1200U
#define APP_RADIO_PROBE_DISTANCE_MAX_MM 100000U
#define APP_RADIO_TREND_WINDOW 8U
#define APP_RADIO_TREND_DELTA_DB 6
#define APP_RADIO_TREND_STABLE_DB 2
#define APP_RADIO_TREND_CONFIRM 3U

typedef enum { APP_RADIO_UNKNOWN, APP_RADIO_STABLE, APP_RADIO_WEAKENING,
    APP_RADIO_STRENGTHENING } app_radio_trend_t;
typedef enum { APP_RADIO_ROLE_UNSPECIFIED, APP_RADIO_ROLE_FIXED,
    APP_RADIO_ROLE_CARRIED } app_radio_role_t;
typedef enum { APP_RADIO_LABEL_UNKNOWN, APP_RADIO_LABEL_QUIET, APP_RADIO_LABEL_AWAY,
    APP_RADIO_LABEL_TOWARD, APP_RADIO_LABEL_TURN, APP_RADIO_LABEL_POCKET,
    APP_RADIO_LABEL_OCCLUDED, APP_RADIO_LABEL_BODY_MOTION } app_radio_label_t;
typedef struct app_radio_probe app_radio_probe_t;
typedef struct {
    uint32_t id;
    app_network_link_snapshot_t link;
    uint32_t distance_mm; /**< Human label; zero means unspecified. */
    uint8_t label, trend;
    bool paired;
} app_radio_record_t;
typedef struct {
    uint32_t run, oldest, latest, count, overwritten, missed_reads;
    bool recording;
    app_radio_role_t role;
    app_radio_label_t label;
    uint32_t distance_mm;
    app_radio_trend_t trend;
} app_radio_probe_snapshot_t;

/** Caller supplies zero-initializable, suitably aligned storage; no heap or I/O. */
size_t app_radio_probe_storage_bytes(void);
app_radio_probe_t *app_radio_probe_init(void *storage, size_t bytes);
/** Starts a new run, discarding the previous run. Caller confirms expected run. */
bool app_radio_probe_start(app_radio_probe_t *s, app_radio_role_t role);
void app_radio_probe_stop(app_radio_probe_t *s);
bool app_radio_probe_mark(app_radio_probe_t *s, app_radio_label_t label, uint32_t distance_mm);
/** Feed copied snapshots under the caller's single owner/lock. Duplicate IDs are ignored. */
void app_radio_probe_ingest(app_radio_probe_t *s, const app_network_link_snapshot_t *link,
    uint32_t now, bool paired);
void app_radio_probe_read(const app_radio_probe_t *s, app_radio_probe_snapshot_t *out);
/** False means overwritten, not yet recorded, or another run; no synthetic fill. */
bool app_radio_probe_record(const app_radio_probe_t *s, uint32_t run, uint32_t id,
    app_radio_record_t *out);
const char *app_radio_probe_trend_name(app_radio_trend_t trend);
