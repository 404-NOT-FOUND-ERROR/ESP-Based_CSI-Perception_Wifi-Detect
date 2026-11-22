// SPDX-License-Identifier: Apache-2.0
#include "app_csi_s31.h"
#include <string.h>

#if !CONFIG_IDF_TARGET_ESP32S31 || CONFIG_SOC_WIFI_MAC_VERSION_NUM != 3
#error "This CSI adapter is specific to the pinned ESP32-S31 MAC-v3 SDK"
#endif
void app_csi_s31_config(wifi_csi_config_t *out)
{
    if (!out) return;
    memset(out, 0, sizeof(*out));
    out->enable = true;
    out->acquire_csi_legacy = true;
    out->acquire_csi_force_lltf = true;
    out->lltf_bit_mode = 1; /* Explicit 8-bit request; real layout still requires validation. */
}
bool app_csi_s31_config_matches(const wifi_csi_config_t *actual)
{
    return actual && actual->enable && actual->acquire_csi_legacy &&
        actual->acquire_csi_force_lltf && actual->lltf_bit_mode == 1 &&
        !actual->acquire_csi_ht20 && !actual->acquire_csi_ht40 &&
        !actual->acquire_csi_vht && !actual->acquire_csi_su && !actual->acquire_csi_mu &&
        !actual->acquire_csi_dcm && !actual->acquire_csi_beamformed &&
        !actual->dump_ack_en && !actual->val_scale_cfg;
}
bool app_csi_s31_offer(app_csi_probe_t *probe, uint32_t run,
    const wifi_csi_info_t *info, uint64_t callback_us)
{
    if (!info || info->rx_ctrl.rx_state) return app_csi_probe_offer(probe, run, NULL, NULL, 0);
    app_csi_metadata_t meta = {
        .callback_us = callback_us, .hardware_rx_us = info->rx_ctrl.timestamp,
        .rx_sequence = info->rx_seq, .channel = info->rx_ctrl.channel,
        .rx_format = info->rx_ctrl.cur_bb_format, .rssi_dbm = info->rx_ctrl.rssi,
        .noise_floor_dbm = info->rx_ctrl.noise_floor, .first_word_invalid = info->first_word_invalid
    };
    memcpy(meta.source, info->mac, sizeof(meta.source));
    return app_csi_probe_offer(probe, run, &meta, info->buf, info->len);
}
