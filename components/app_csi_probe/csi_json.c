// SPDX-License-Identifier: Apache-2.0
#include "app_csi_probe.h"
#include <inttypes.h>
#include <stdio.h>

size_t app_csi_frame_json(const app_csi_frame_t *f, bool simulated, char *out, size_t capacity)
{
    if (!f || !out || !f->length || f->length > APP_CSI_PAYLOAD_MAX || !capacity) return 0;
    const app_csi_metadata_t *m = &f->meta;
    int n = snprintf(out, capacity,
        "{\"schema\":\"airboat.csi.raw.v1\",\"simulated\":%s,\"id\":%"PRIu32",\"run\":%"PRIu32","
        "\"network_generation\":%"PRIu32",\"motion_epoch\":%"PRIu32",\"callback_us\":%"PRIu64","
        "\"motion_at_us\":%"PRIu64",\"head_locked\":%s,\"stationary\":%s,\"commanded_motion\":%s,"
        "\"hardware_rx_us\":%"PRIu32",\"rx_sequence\":%u,\"source\":\"%02x%02x%02x%02x%02x%02x\","
        "\"channel\":%u,\"rx_format\":%u,\"rssi_dbm\":%d,\"noise_floor_dbm\":%d,"
        "\"first_word_invalid\":%s,\"length\":%u,\"label\":%u,\"motion_eligible\":%s,"
        "\"requested_iq_bits\":8,\"actual_layout_verified\":false,\"carrier_mask_known\":false,\"payload_hex\":\"",
        simulated ? "true" : "false", f->id, f->run, f->network_generation, f->motion.epoch,
        m->callback_us, f->motion.at_us, f->motion.head_locked ? "true" : "false",
        f->motion.stationary ? "true" : "false", f->motion.commanded_motion ? "true" : "false",
        m->hardware_rx_us, m->rx_sequence, m->source[0], m->source[1],
        m->source[2], m->source[3], m->source[4], m->source[5], m->channel, m->rx_format,
        m->rssi_dbm, m->noise_floor_dbm, m->first_word_invalid ? "true" : "false",
        f->length, f->label, f->motion_eligible ? "true" : "false");
    if (n < 0 || (size_t)n >= capacity || capacity - (size_t)n < (size_t)f->length * 2U + 4U) {
        out[0] = '\0'; return 0;
    }
    static const char hex[] = "0123456789abcdef";
    size_t used = (size_t)n;
    for (unsigned i = 0; i < f->length; ++i) {
        out[used++] = hex[f->payload[i] >> 4U];
        out[used++] = hex[f->payload[i] & 15U];
    }
    out[used++] = '"'; out[used++] = '}'; out[used++] = '\n'; out[used] = '\0';
    return used;
}
