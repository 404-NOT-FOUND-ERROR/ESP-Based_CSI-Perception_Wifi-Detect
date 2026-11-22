// SPDX-License-Identifier: Apache-2.0
#include "app_radio_probe.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

static app_network_link_snapshot_t sample = {
    .generation = 1, .rssi_dbm = -50, .channel = 6, .valid = true,
    .bssid = {2, 3, 4, 5, 6, 7}
};
static void feed(app_radio_probe_t *p, int rssi, bool paired)
{
    ++sample.sequence; sample.read_ms += 500;
    sample.rssi_dbm = (int8_t)rssi;
    app_radio_probe_ingest(p, &sample, sample.read_ms, paired);
}
int main(void)
{
    void *storage = malloc(app_radio_probe_storage_bytes());
    app_radio_probe_t *p = app_radio_probe_init(storage, app_radio_probe_storage_bytes());
    assert(p && !app_radio_probe_init(storage, 1));
    app_radio_probe_snapshot_t view;
    app_radio_record_t row;
    assert(app_radio_probe_start(p, APP_RADIO_ROLE_CARRIED));
    assert(app_radio_probe_mark(p, APP_RADIO_LABEL_QUIET, 500));
    for (unsigned i = 0; i < 20; ++i) feed(p, -50 + (int)(i % 3U) - 1, true);
    app_radio_probe_read(p, &view); assert(view.trend == APP_RADIO_STABLE);
    for (int i = 0; i < 14; ++i) feed(p, -50 - i * 2, true);
    app_radio_probe_read(p, &view); assert(view.trend == APP_RADIO_WEAKENING);
    puts("radio: sustained change and stable noise use distinct outcomes");
    sample.bssid[5] = 8; feed(p, -85, true);
    app_radio_probe_read(p, &view); assert(view.trend == APP_RADIO_UNKNOWN);
    for (unsigned i = 0; i < 12; ++i) feed(p, -85, true);
    ++sample.generation; feed(p, -45, true);
    app_radio_probe_read(p, &view); assert(view.trend == APP_RADIO_UNKNOWN);
    sample.channel = 11; feed(p, -65, true);
    sample.valid = false; feed(p, 0, true);
    app_radio_probe_read(p, &view); assert(view.trend == APP_RADIO_UNKNOWN);
    sample.valid = true;
    for (unsigned i = 0; i < 12; ++i) feed(p, -60, true);
    app_radio_probe_read(p, &view); assert(view.trend == APP_RADIO_STABLE);
    const uint32_t count = view.count;
    app_radio_probe_ingest(p, &sample, sample.read_ms + 2000, true);
    app_radio_probe_read(p, &view); assert(view.count == count && view.trend == APP_RADIO_UNKNOWN);
    puts("radio: AP, generation, channel, invalid reads and stale duplicates clear trend");
    sample.sequence+=4; feed(p,-60,true);
    app_radio_probe_read(p,&view);
    assert(view.missed_reads==4U && view.trend==APP_RADIO_UNKNOWN);
    feed(p, -61, false);
    assert(app_radio_probe_record(p, view.run, view.latest + 1U, &row));
    assert(row.label == APP_RADIO_LABEL_UNKNOWN && !row.distance_mm && !row.paired);
    feed(p, -61, true);
    app_radio_probe_read(p, &view);
    assert(view.label == APP_RADIO_LABEL_UNKNOWN);
    assert(!app_radio_probe_mark(p, APP_RADIO_LABEL_QUIET, 100001));
    const uint32_t old_run = view.run;
    assert(app_radio_probe_start(p, APP_RADIO_ROLE_FIXED));
    sample.read_ms = UINT32_MAX - 300U;
    for (unsigned i = 0; i < APP_RADIO_PROBE_CAPACITY + 5U; ++i) feed(p, -60, true);
    app_radio_probe_read(p, &view);
    assert(view.count == APP_RADIO_PROBE_CAPACITY && view.overwritten == 5 && view.oldest == 6);
    assert(!app_radio_probe_record(p, old_run, 6, &row));
    assert(!app_radio_probe_record(p, view.run, 5, &row));
    assert(app_radio_probe_record(p, view.run, 6, &row));
    assert(view.trend == APP_RADIO_STABLE);
    app_radio_probe_stop(p); feed(p, -65, true);
    app_radio_probe_read(p, &view); assert(view.latest == APP_RADIO_PROBE_CAPACITY + 5U);
    puts("radio: lost labels, time wrap, bounded overwrite, run isolation and frozen export passed");
    printf("radio storage: %zu bytes; network link: %zu bytes\n", app_radio_probe_storage_bytes(), sizeof(sample));
    free(storage);
}
