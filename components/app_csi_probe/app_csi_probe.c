// SPDX-License-Identifier: Apache-2.0
#include "app_csi_probe.h"
#include <limits.h>
#include <stdatomic.h>
#include <string.h>

_Static_assert(ATOMIC_INT_LOCK_FREE == 2, "CSI callback requires lock-free counters");
struct app_csi_probe {
    atomic_flag guard;
    atomic_uint contended;
    app_csi_snapshot_t view;
    app_csi_source_t source;
    app_csi_motion_t motion;
    app_csi_frame_t queue[APP_CSI_QUEUE_CAPACITY];
    uint32_t write, read, next_id;
    app_csi_label_t label;
};
static bool enter(app_csi_probe_t *s)
{
    return s && !atomic_flag_test_and_set_explicit(&s->guard, memory_order_acquire);
}
static void leave(app_csi_probe_t *s)
{
    atomic_flag_clear_explicit(&s->guard, memory_order_release);
}
size_t app_csi_probe_storage_bytes(void) { return sizeof(app_csi_probe_t); }
app_csi_probe_t *app_csi_probe_init(void *storage, size_t bytes)
{
    if (!storage || bytes < sizeof(app_csi_probe_t) ||
        (uintptr_t)storage % _Alignof(app_csi_probe_t)) return NULL;
    app_csi_probe_t *s = storage;
    memset(s, 0, sizeof(*s));
    atomic_flag_clear(&s->guard);
    atomic_init(&s->contended, 0U);
    return s;
}
static bool valid_source(const app_csi_source_t *source)
{
    static const uint8_t zero[6];
    return source && source->network_generation && source->channel &&
        !(source->bssid[0] & 1U) && memcmp(source->bssid, zero, sizeof(zero));
}
bool app_csi_probe_begin(app_csi_probe_t *s, const app_csi_source_t *source, uint32_t *run)
{
    if (!run || !valid_source(source) || !enter(s)) return false;
    if (s->view.active || s->view.run == UINT32_MAX || s->view.exhausted) {
        leave(s); return false;
    }
    s->view.discarded += s->view.queued;
    s->view.queued = s->read = s->write = 0;
    ++s->view.run;
    s->source = *source;
    s->label = APP_CSI_UNLABELLED;
    memset(&s->motion, 0, sizeof(s->motion));
    s->view.active = true;
    *run = s->view.run;
    leave(s); return true;
}
bool app_csi_probe_stop(app_csi_probe_t *s)
{
    if (!enter(s)) return false;
    s->view.active = false;
    leave(s); return true;
}
bool app_csi_probe_mark(app_csi_probe_t *s, app_csi_label_t label)
{
    if ((int)label < 0 || label > APP_CSI_OCCLUDED || !enter(s)) return false;
    const bool active = s->view.active;
    if (active) s->label = label;
    leave(s); return active;
}
bool app_csi_probe_motion(app_csi_probe_t *s, const app_csi_motion_t *motion)
{
    if (!motion || !enter(s)) return false;
    const bool active = s->view.active;
    if (active) s->motion = *motion;
    leave(s); return active;
}
bool app_csi_probe_offer(app_csi_probe_t *s, uint32_t run,
    const app_csi_metadata_t *meta, const void *payload, size_t bytes)
{
    if (!s) return false;
    if (!enter(s)) {
        atomic_fetch_add_explicit(&s->contended, 1U, memory_order_relaxed);
        return false;
    }
    if (!s->view.active || run != s->view.run) {
        ++s->view.old_run_drops; leave(s); return false;
    }
    if (!meta || !payload || !bytes || bytes > APP_CSI_PAYLOAD_MAX) {
        ++s->view.invalid_drops; leave(s); return false;
    }
    if (meta->channel != s->source.channel || memcmp(meta->source, s->source.bssid, 6)) {
        ++s->view.source_drops; leave(s); return false;
    }
    if (s->next_id == UINT32_MAX) {
        s->view.active = false; s->view.exhausted = true; leave(s); return false;
    }
    /* IDs include full-queue attempts, making a later accepted gap visible. */
    const uint32_t id = ++s->next_id;
    if (s->view.queued == APP_CSI_QUEUE_CAPACITY) {
        ++s->view.full_drops; leave(s); return false;
    }
    app_csi_frame_t *frame = &s->queue[s->write];
    frame->id = id; frame->run = run;
    frame->network_generation = s->source.network_generation;
    frame->motion = s->motion;
    frame->meta = *meta;
    frame->length = (uint16_t)bytes;
    frame->label = (uint8_t)s->label;
    frame->motion_eligible = s->motion.epoch && s->motion.at_us <= meta->callback_us &&
        meta->callback_us - s->motion.at_us <= APP_CSI_MOTION_FRESH_US &&
        s->motion.head_locked && s->motion.stationary && !s->motion.commanded_motion;
    memcpy(frame->payload, payload, bytes);
    s->write = (s->write + 1U) % APP_CSI_QUEUE_CAPACITY;
    ++s->view.queued; ++s->view.accepted;
    leave(s); return true;
}
app_csi_read_t app_csi_probe_pop(app_csi_probe_t *s, app_csi_frame_t *out)
{
    if (!s || !out) return APP_CSI_EMPTY;
    if (!enter(s)) return APP_CSI_BUSY;
    if (!s->view.queued) { leave(s); return APP_CSI_EMPTY; }
    *out = s->queue[s->read];
    s->read = (s->read + 1U) % APP_CSI_QUEUE_CAPACITY;
    --s->view.queued;
    leave(s); return APP_CSI_FRAME;
}
bool app_csi_probe_read(app_csi_probe_t *s, app_csi_snapshot_t *out)
{
    if (!out || !enter(s)) return false;
    *out = s->view;
    out->contended_drops = atomic_load_explicit(&s->contended, memory_order_relaxed);
    leave(s); return true;
}
