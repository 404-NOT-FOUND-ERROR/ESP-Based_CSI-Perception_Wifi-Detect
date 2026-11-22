// SPDX-License-Identifier: Apache-2.0
#include "app_csi_s31.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const app_csi_source_t source = {.network_generation=7,.bssid={2,1,2,3,4,5},.channel=6};
static app_csi_probe_t *create(void)
{
    void *storage = calloc(1, app_csi_probe_storage_bytes());
    assert(storage);
    app_csi_probe_t *s = app_csi_probe_init(storage, app_csi_probe_storage_bytes());
    assert(s); return s;
}
static void fill_meta(app_csi_metadata_t *m, uint64_t at)
{
    memset(m, 0, sizeof(*m));
    m->callback_us=at; m->hardware_rx_us=(uint32_t)at; m->channel=6;
    m->rssi_dbm=-50; memcpy(m->source,source.bssid,6);
}
static void fixture(void)
{
    app_csi_probe_t *s=create();
    app_csi_frame_t *f=calloc(1,sizeof(*f));
    uint8_t *payload=malloc(128);
    char *line=malloc(APP_CSI_JSON_BYTES);
    assert(f && payload && line);
    uint32_t run;
    assert(app_csi_probe_begin(s,&source,&run));
    puts("{\"schema\":\"airboat.csi.session.v1\",\"capture_id\":\"host-fixture-20261121\",\"simulated\":true,\"target\":\"esp32s31\",\"sdk_commit\":\"7b9cc1ac79f865983f59bb8ff3ff43eb74ff1dbe\",\"requested_iq_bits\":8,\"layout_verified\":false,\"transport\":\"host-fixture\"}");
    for (unsigned i=0;i<120;++i) {
        app_csi_metadata_t m;
        fill_meta(&m,1000000ULL+i*50000ULL);
        m.hardware_rx_us=(uint32_t)(UINT32_MAX-300000ULL+i*50000ULL);
        m.rx_sequence=(uint16_t)(4090U+i);
        m.first_word_invalid=i%7U==0;
        app_csi_motion_t motion={.at_us=m.callback_us,.epoch=i<80?1:2,
            .head_locked=true,.stationary=i<80,.commanded_motion=i>=80};
        assert(app_csi_probe_motion(s,&motion));
        assert(app_csi_probe_mark(s,i<40?APP_CSI_QUIET:i<80?APP_CSI_WALKING:APP_CSI_SELF_MOVING));
        for (unsigned j=0;j<128;++j) payload[j]=(uint8_t)(j+(i<40?0:i));
        assert(app_csi_probe_offer(s,run,&m,payload,128));
        assert(app_csi_probe_pop(s,f)==APP_CSI_FRAME);
        assert(app_csi_frame_json(f,true,line,APP_CSI_JSON_BYTES)); fputs(line,stdout);
    }
    assert(app_csi_probe_stop(s));
    puts("{\"schema\":\"airboat.csi.end.v1\",\"exported_frames\":120,\"accepted\":120,\"full_drops\":0,\"contended_drops\":0,\"source_drops\":0,\"invalid_drops\":0,\"old_run_drops\":0,\"discarded\":0,\"queued\":0}");
    free(line); free(payload); free(f); free(s);
}
int main(int argc, char **argv)
{
    if (argc==2 && !strcmp(argv[1],"--fixture")) { fixture(); return 0; }
    app_csi_probe_t *s=create();
    app_csi_frame_t *f=calloc(1,sizeof(*f));
    uint8_t *payload=malloc(APP_CSI_PAYLOAD_MAX+1U);
    char *line=malloc(APP_CSI_JSON_BYTES);
    assert(f && payload && line);
    memset(payload,0xa5,APP_CSI_PAYLOAD_MAX+1U);
    assert(!app_csi_probe_init(NULL,0));
    uint32_t run;
    assert(app_csi_probe_begin(s,&source,&run) && run==1);
    assert(!app_csi_probe_begin(s,&source,&run));
    app_csi_metadata_t m; fill_meta(&m,1000000);
    assert(app_csi_probe_offer(s,run,&m,payload,128));
    payload[0]=0;
    assert(app_csi_probe_pop(s,f)==APP_CSI_FRAME && f->payload[0]==0xa5);
    assert(!f->motion_eligible && f->label==APP_CSI_UNLABELLED);
    assert(app_csi_probe_pop(s,f)==APP_CSI_EMPTY);
    puts("PASS callback payload is copied; default motion is unknown");

    app_csi_motion_t motion={.at_us=m.callback_us,.epoch=1,.head_locked=true,.stationary=true};
    assert(app_csi_probe_motion(s,&motion));
    assert(app_csi_probe_mark(s,APP_CSI_QUIET));
    assert(app_csi_probe_offer(s,run,&m,payload,128));
    assert(app_csi_probe_pop(s,f)==APP_CSI_FRAME && f->motion_eligible && f->label==APP_CSI_QUIET);
    m.callback_us+=APP_CSI_MOTION_FRESH_US+1U;
    assert(app_csi_probe_offer(s,run,&m,payload,128));
    assert(app_csi_probe_pop(s,f)==APP_CSI_FRAME && !f->motion_eligible);
    motion.at_us=m.callback_us+1U;
    assert(app_csi_probe_motion(s,&motion));
    assert(app_csi_probe_offer(s,run,&m,payload,128));
    assert(app_csi_probe_pop(s,f)==APP_CSI_FRAME && !f->motion_eligible);
    motion.at_us=m.callback_us; motion.commanded_motion=true;
    assert(app_csi_probe_motion(s,&motion));
    assert(app_csi_probe_offer(s,run,&m,payload,128));
    assert(app_csi_probe_pop(s,f)==APP_CSI_FRAME && !f->motion_eligible);
    puts("PASS stationary context expires; future/stale/self-moving samples stay ineligible");

    m.source[5]++; assert(!app_csi_probe_offer(s,run,&m,payload,128));
    m.source[5]--; m.channel=11; assert(!app_csi_probe_offer(s,run,&m,payload,128));
    m.channel=6;
    assert(!app_csi_probe_offer(s,run,&m,payload,APP_CSI_PAYLOAD_MAX+1U));
    assert(!app_csi_probe_offer(s,run,&m,NULL,128));
    for (unsigned i=0;i<APP_CSI_QUEUE_CAPACITY;++i)
        assert(app_csi_probe_offer(s,run,&m,payload,128));
    assert(!app_csi_probe_offer(s,run,&m,payload,128));
    app_csi_snapshot_t view;
    assert(app_csi_probe_read(s,&view) && view.full_drops==1 && view.source_drops==2 && view.invalid_drops==2);
    assert(app_csi_probe_stop(s));
    const uint32_t old=run;
    assert(app_csi_probe_begin(s,&source,&run) && run==2);
    assert(!app_csi_probe_offer(s,old,&m,payload,128));
    assert(app_csi_probe_read(s,&view) && view.discarded==APP_CSI_QUEUE_CAPACITY);
    assert(app_csi_probe_offer(s,run,&m,payload,APP_CSI_PAYLOAD_MAX));
    assert(app_csi_probe_pop(s,f)==APP_CSI_FRAME && f->network_generation==7);
    assert(app_csi_frame_json(f,true,line,APP_CSI_JSON_BYTES)>1024);
    assert(strstr(line,"\"actual_layout_verified\":false"));
    assert(!app_csi_frame_json(f,true,line,100) && !line[0]);
    puts("PASS source filter, bounded queue, oversize rejection, old-run fence and JSON bounds");

    wifi_csi_config_t config;
    app_csi_s31_config(&config); assert(app_csi_s31_config_matches(&config));
    config.lltf_bit_mode=0; assert(!app_csi_s31_config_matches(&config));
    wifi_csi_info_t *info=calloc(1,sizeof(*info)); assert(info);
    memcpy(info->mac,source.bssid,6); info->buf=(int8_t *)payload; info->len=128;
    info->rx_ctrl.channel=6; info->rx_ctrl.cur_bb_format=3;
    info->rx_ctrl.timestamp=UINT32_MAX; info->rx_seq=4095; info->first_word_invalid=true;
    assert(app_csi_s31_offer(s,run,info,100));
    assert(app_csi_probe_pop(s,f)==APP_CSI_FRAME && f->meta.first_word_invalid &&
        f->meta.rx_sequence==4095 && f->meta.hardware_rx_us==UINT32_MAX && f->meta.rx_format==3);
    info->rx_ctrl.rx_state=1; assert(!app_csi_s31_offer(s,run,info,101));
    puts("PASS S31 config requests LLTF8; adapter preserves hardware metadata and invalid prefix");
    printf("storage_bytes=%zu frame_bytes=%zu json_capacity=%u\n",app_csi_probe_storage_bytes(),sizeof(*f),APP_CSI_JSON_BYTES);
    free(info); free(line); free(payload); free(f); free(s);
}
