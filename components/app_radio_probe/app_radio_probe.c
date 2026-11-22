// SPDX-License-Identifier: Apache-2.0
#include "app_radio_probe.h"
#include <string.h>

#define TREND_MAX_GAP_MS 1000U

struct app_radio_probe {
    app_radio_probe_snapshot_t view;
    app_radio_record_t records[APP_RADIO_PROBE_CAPACITY];
    app_network_link_snapshot_t previous;
    int8_t history[APP_RADIO_TREND_WINDOW];
    uint8_t history_count, candidate_hits;
    app_radio_trend_t candidate;
    uint32_t last_sequence;
};

size_t app_radio_probe_storage_bytes(void) { return sizeof(app_radio_probe_t); }
app_radio_probe_t *app_radio_probe_init(void *storage, size_t bytes)
{
    if (!storage || bytes < sizeof(app_radio_probe_t)) return NULL;
    memset(storage, 0, sizeof(app_radio_probe_t)); return storage;
}
static void reset_trend(app_radio_probe_t *s)
{
    s->history_count = s->candidate_hits = 0;
    s->candidate = s->view.trend = APP_RADIO_UNKNOWN;
}
bool app_radio_probe_start(app_radio_probe_t *s, app_radio_role_t role)
{
    if (!s || (role != APP_RADIO_ROLE_FIXED && role != APP_RADIO_ROLE_CARRIED) ||
        s->view.run == UINT32_MAX) return false;
    ++s->view.run;
    s->view.oldest = s->view.latest = s->view.count = s->view.overwritten = 0;
    s->view.missed_reads = 0;
    s->view.role = role; s->view.label = APP_RADIO_LABEL_UNKNOWN;
    s->view.distance_mm = 0; s->view.recording = true;
    s->last_sequence = 0; memset(&s->previous, 0, sizeof(s->previous));
    reset_trend(s); return true;
}
void app_radio_probe_stop(app_radio_probe_t *s) { if (s) s->view.recording = false; }
bool app_radio_probe_mark(app_radio_probe_t *s, app_radio_label_t label, uint32_t distance_mm)
{
    if (!s || !s->view.recording || (int)label < 0 || label > APP_RADIO_LABEL_BODY_MOTION ||
        distance_mm > APP_RADIO_PROBE_DISTANCE_MAX_MM) return false;
    s->view.label = label; s->view.distance_mm = distance_mm; return true;
}
static int median3(int a, int b, int c)
{
    if (a > b) { int t = a; a = b; b = t; }
    if (b > c) { b = c; if (a > b) b = a; }
    return b;
}
static void trend(app_radio_probe_t *s, const app_network_link_snapshot_t *p)
{
    if (!p->valid || !s->previous.valid || p->generation != s->previous.generation ||
        p->channel != s->previous.channel || memcmp(p->bssid, s->previous.bssid, 6) ||
        (uint32_t)(p->sequence - s->previous.sequence) != 1U ||
        (uint32_t)(p->read_ms - s->previous.read_ms) > TREND_MAX_GAP_MS) reset_trend(s);
    if (!p->valid) return;
    if (s->history_count == APP_RADIO_TREND_WINDOW) {
        memmove(s->history, s->history + 1, APP_RADIO_TREND_WINDOW - 1U);
        --s->history_count;
    }
    s->history[s->history_count++] = p->rssi_dbm;
    if (s->history_count < APP_RADIO_TREND_WINDOW) return;
    const int delta = median3(s->history[5], s->history[6], s->history[7]) -
        median3(s->history[0], s->history[1], s->history[2]);
    const app_radio_trend_t next = delta >= APP_RADIO_TREND_DELTA_DB ? APP_RADIO_STRENGTHENING :
        delta <= -APP_RADIO_TREND_DELTA_DB ? APP_RADIO_WEAKENING :
        delta >= -APP_RADIO_TREND_STABLE_DB && delta <= APP_RADIO_TREND_STABLE_DB ? APP_RADIO_STABLE : APP_RADIO_UNKNOWN;
    if (next != s->candidate) { s->candidate = next; s->candidate_hits = 1; }
    else if (s->candidate_hits < APP_RADIO_TREND_CONFIRM) ++s->candidate_hits;
    /* A changed trend becomes unknown while its sustained evidence builds. */
    s->view.trend = s->candidate_hits >= APP_RADIO_TREND_CONFIRM ? next : APP_RADIO_UNKNOWN;
}
void app_radio_probe_ingest(app_radio_probe_t *s, const app_network_link_snapshot_t *link,
    uint32_t now, bool paired)
{
    if (!s || !s->view.recording || !link || !link->sequence) return;
    if (s->last_sequence == link->sequence) {
        if ((uint32_t)(now - link->read_ms) > APP_NETWORK_LINK_MAX_AGE_MS) reset_trend(s);
        return;
    }
    if (s->view.latest == UINT32_MAX) { app_radio_probe_stop(s); return; }
    if (s->last_sequence) {
        const uint32_t step = link->sequence - s->last_sequence;
        if (step > 1U && step < 0x80000000U) s->view.missed_reads += step - 1U;
    }
    s->last_sequence = link->sequence;
    const uint32_t id = ++s->view.latest;
    app_radio_record_t *record = &s->records[(id - 1U) % APP_RADIO_PROBE_CAPACITY];
    record->id = id; record->link = *link;
    if ((uint32_t)(now - link->read_ms) > APP_NETWORK_LINK_MAX_AGE_MS ||
        link->rssi_dbm >= 0 || link->rssi_dbm < -127 || !link->channel) record->link.valid = false;
    trend(s, &record->link); s->previous = record->link;
    if (!paired) { s->view.label = APP_RADIO_LABEL_UNKNOWN; s->view.distance_mm = 0; }
    record->paired = paired; record->label = (uint8_t)s->view.label;
    record->distance_mm = s->view.distance_mm; record->trend = (uint8_t)s->view.trend;
    if (s->view.count < APP_RADIO_PROBE_CAPACITY) ++s->view.count;
    else ++s->view.overwritten;
    s->view.oldest = id - s->view.count + 1U;
}
void app_radio_probe_read(const app_radio_probe_t *s, app_radio_probe_snapshot_t *out)
{
    if (out) { if (s) *out = s->view; else memset(out, 0, sizeof(*out)); }
}
bool app_radio_probe_record(const app_radio_probe_t *s, uint32_t run, uint32_t id,
    app_radio_record_t *out)
{
    if (!s || !out || run != s->view.run || !id || id < s->view.oldest || id > s->view.latest) return false;
    *out = s->records[(id - 1U) % APP_RADIO_PROBE_CAPACITY]; return true;
}
const char *app_radio_probe_trend_name(app_radio_trend_t value)
{
    switch (value) {
    case APP_RADIO_STABLE: return "stable";
    case APP_RADIO_WEAKENING: return "weakening";
    case APP_RADIO_STRENGTHENING: return "strengthening";
    default: return "unknown";
    }
}
