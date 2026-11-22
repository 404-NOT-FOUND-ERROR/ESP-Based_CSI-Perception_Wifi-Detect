// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <stdbool.h>
#include <stdint.h>

#define APP_NETWORK_LINK_INTERVAL_MS 500U
#define APP_NETWORK_LINK_MAX_AGE_MS 1500U

typedef struct {
    uint32_t sequence; /**< Nonzero read-attempt ID, including unsuccessful reads. */
    uint32_t generation; /**< Network connection attempt owning this observation. */
    uint32_t read_ms; /**< Monotonic API-read time, wrapping uint32 milliseconds. */
    int32_t error;
    uint8_t bssid[6];
    int8_t rssi_dbm;
    uint8_t channel;
    bool valid;
    bool ftm_responder;
    /* The driver does not expose the age of its underlying RSSI measurement. */
} app_network_link_snapshot_t;
