// SPDX-License-Identifier: Apache-2.0
/* Emit labelled N1 data through the real historical recorder for offline parity checks. */
#include "app_radio_probe.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    void *storage = calloc(1, app_radio_probe_storage_bytes());
    assert(storage);
    app_radio_probe_t *probe = app_radio_probe_init(storage, app_radio_probe_storage_bytes());
    app_radio_record_t *row = calloc(1, sizeof(*row));
    assert(row);
    assert(app_radio_probe_start(probe, APP_RADIO_ROLE_CARRIED));
    app_network_link_snapshot_t link = {
        .generation = 1, .rssi_dbm = -45, .channel = 6,
        .valid = true, .bssid = {2, 3, 4, 5, 6, 7},
    };
    const uint32_t base = UINT32_MAX - 20000U;
    for (unsigned i = 0; i < 160; ++i) {
        const bool paired = i < 130 || i >= 140;
        const app_radio_label_t label = i < 30 ? APP_RADIO_LABEL_QUIET :
            i < 65 ? APP_RADIO_LABEL_AWAY : i < 100 ? APP_RADIO_LABEL_TOWARD :
            i < 120 ? APP_RADIO_LABEL_TURN : APP_RADIO_LABEL_POCKET;
        assert(app_radio_probe_mark(probe, label, i < 30 ? 500U : 0));
        link.sequence = i + 1U;
        link.read_ms = base + i * 500U;
        link.rssi_dbm = i < 30 ? -45 : i < 65 ? -45 - 2 * (int)(i - 30) :
            i < 100 ? -115 + 2 * (int)(i - 65) : i < 120 ? -48 : -65;
        if (i >= 110U) {
            link.sequence += 2U;
        }
        link.valid = i < 135U || i >= 140U;
        link.error = link.valid ? 0 : 1;
        if (i >= 140U) {
            link.generation = 2;
        }
        app_radio_probe_ingest(probe, &link, link.read_ms, paired);
    }
    app_radio_probe_stop(probe);
    app_radio_probe_snapshot_t view;
    app_radio_probe_read(probe, &view);
    printf("{\"schema\":\"airboat.hotspot-probe.v1\",\"boot\":\"00000000000000000000000000000022\","
        "\"measurement_age_known\":false,\"meta\":{\"simulated\":true,\"measurement_age_known\":false,"
        "\"recording\":false,\"run\":1,\"role\":2,\"count\":%lu,\"capacity\":1200,"
        "\"oldest\":%lu,\"latest\":%lu,\"overwritten\":%lu,\"missed_reads\":%lu,"
        "\"parameters\":{\"interval_ms\":500,\"window\":8,\"median_points\":3,\"delta_db\":6,\"stable_db\":2,\"confirm_reads\":3}},"
        "\"trend_parameters\":{\"interval_ms\":500,\"window\":8,\"median_points\":3,\"delta_db\":6,\"stable_db\":2,\"confirm_reads\":3},\"records\":[",
        (unsigned long)view.count, (unsigned long)view.oldest, (unsigned long)view.latest,
        (unsigned long)view.overwritten, (unsigned long)view.missed_reads);
    for (uint32_t id = view.oldest; id <= view.latest; ++id) {
        assert(app_radio_probe_record(probe, view.run, id, row));
        printf("%s{\"id\":%lu,\"sample_seq\":%lu,\"read_ms\":%lu,\"network_generation\":%lu,"
            "\"valid\":%u,\"rssi_dbm\":%d,\"channel\":6,\"bssid\":\"020304050607\",\"ftm_responder\":0,"
            "\"read_error\":%ld,\"label\":%u,\"distance_mm\":%lu,\"trend\":%u,\"paired\":%u}",
            id == view.oldest ? "" : ",", (unsigned long)id, (unsigned long)row->link.sequence,
            (unsigned long)row->link.read_ms, (unsigned long)row->link.generation,
            row->link.valid ? 1U : 0U, row->link.rssi_dbm, (long)row->link.error, row->label,
            (unsigned long)row->distance_mm, row->trend, row->paired ? 1U : 0U);
    }
    puts("]}");
    free(row);
    free(storage);
}
