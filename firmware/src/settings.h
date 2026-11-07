// Settings kept in flash. Everything is entered through the web UI, none of it is compiled in.
#pragma once

#include <stdbool.h>

#include "base_station.h"

typedef struct {
    char wifi_ssid[33];
    char wifi_password[65];
    char ui_password[65];
    base_caster_settings_t caster;
    base_mode_t mode;
} settings_t;

void settings_load(settings_t *settings);

// Saves everything except the mode, which is saved on its own whenever it changes.
bool settings_save(const settings_t *settings);

void settings_save_mode(const base_mode_t *mode);

// True once the device can join a network and the UI is protected.
bool settings_complete(const settings_t *settings);

// Forgets everything. The device starts its setup network on the next boot.
void settings_erase(void);
