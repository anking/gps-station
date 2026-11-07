// WiFi: joins the configured network, and offers a setup network when there is none or it cannot be reached.
#pragma once

#include <stdbool.h>
#include <stddef.h>

#include "settings.h"

#define SETUP_AP_PASSWORD "gps-base-setup"

void net_start(const settings_t *settings);

bool net_has_internet_path(void);

// The current station address as text, or an empty string.
void net_address(char *out, size_t capacity);

int net_rssi(void);

const char *net_setup_ssid(void);

bool net_setup_network_active(void);
