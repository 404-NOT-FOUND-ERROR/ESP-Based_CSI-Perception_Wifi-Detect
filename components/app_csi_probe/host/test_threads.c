// SPDX-License-Identifier: Apache-2.0
#include "app_csi_probe.h"
#include <assert.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <windows.h>

#define ATTEMPTS 20000U
typedef struct { app_csi_probe_t *s; atomic_bool done; uint32_t consumed; } fixture_t;
static DWORD WINAPI produce(void *arg)
{
    fixture_t *f=arg;
    uint8_t *bytes=malloc(128); assert(bytes);
    for (unsigned i=0;i<128;++i) bytes[i]=(uint8_t)i;
    app_csi_metadata_t m={.source={2,1,2,3,4,5},.channel=6};
    for (unsigned i=0;i<ATTEMPTS;++i) {
        m.callback_us=i; (void)app_csi_probe_offer(f->s,1,&m,bytes,128);
    }
    atomic_store_explicit(&f->done,true,memory_order_release);
    free(bytes); return 0;
}
int main(void)
{
    fixture_t f={0}; atomic_init(&f.done,false);
    void *storage=calloc(1,app_csi_probe_storage_bytes()); assert(storage);
    f.s=app_csi_probe_init(storage,app_csi_probe_storage_bytes()); assert(f.s);
    app_csi_source_t src={.network_generation=1,.bssid={2,1,2,3,4,5},.channel=6};
    uint32_t run; assert(app_csi_probe_begin(f.s,&src,&run));
    app_csi_frame_t *row=calloc(1,sizeof(*row)); assert(row);
    HANDLE thread=CreateThread(NULL,0,produce,&f,0,NULL); assert(thread);
    uint32_t previous=0;
    for (;;) {
        const app_csi_read_t result=app_csi_probe_pop(f.s,row);
        if (result==APP_CSI_FRAME) {
            assert(row->id>previous && row->run==1 && row->length==128);
            previous=row->id;
            for(unsigned i=0;i<128;++i) assert(row->payload[i]==(uint8_t)i);
            ++f.consumed;
        } else if (atomic_load_explicit(&f.done,memory_order_acquire)) {
            /* A producer may have published its final item after the empty read. */
            app_csi_snapshot_t v;
            if (app_csi_probe_read(f.s,&v) && !v.queued) break;
        }
    }
    assert(WaitForSingleObject(thread,5000)==WAIT_OBJECT_0); CloseHandle(thread);
    app_csi_snapshot_t v; assert(app_csi_probe_read(f.s,&v));
    assert(v.accepted==f.consumed && v.accepted>0);
    assert(v.accepted+v.full_drops+v.contended_drops==ATTEMPTS);
    printf("PASS concurrent callback/consumer: %lu accepted, %lu full, %lu contended; exact accounting\n",
        (unsigned long)v.accepted,(unsigned long)v.full_drops,(unsigned long)v.contended_drops);
    free(row); free(storage);
}
