// SPDX-License-Identifier: Apache-2.0
/* Host boundary double. Target object check uses the real pinned SDK headers. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#define CONFIG_IDF_TARGET_ESP32S31 1
#define CONFIG_SOC_WIFI_MAC_VERSION_NUM 3
typedef struct {
    bool enable, acquire_csi_legacy, acquire_csi_force_lltf, acquire_csi_ht20;
    bool acquire_csi_ht40, acquire_csi_vht, acquire_csi_su, acquire_csi_mu;
    bool acquire_csi_dcm, acquire_csi_beamformed, dump_ack_en;
    unsigned lltf_bit_mode, val_scale_cfg;
} wifi_csi_config_t;
typedef struct {
    struct { uint32_t timestamp; uint8_t rx_state, channel, cur_bb_format;
        int8_t rssi, noise_floor; } rx_ctrl;
    uint8_t mac[6];
    bool first_word_invalid;
    int8_t *buf;
    uint16_t len, rx_seq;
} wifi_csi_info_t;
