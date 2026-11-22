// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "app_csi_probe.h"
#include "esp_wifi.h"

/** Only prepares a value. Network owner registers/enables the sole CSI callback. */
void app_csi_s31_config(wifi_csi_config_t *out);
bool app_csi_s31_config_matches(const wifi_csi_config_t *actual);
/** Copies supported metadata/raw payload. Caller passes its captured run token. */
bool app_csi_s31_offer(app_csi_probe_t *probe, uint32_t run,
    const wifi_csi_info_t *info, uint64_t callback_us);
