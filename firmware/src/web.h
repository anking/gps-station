// The web UI and its small JSON API.
#pragma once

#include "base_station.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "settings.h"

// The base must only be touched while holding the lock, which is also held by the main loop.
void web_start(base_station_t *base, SemaphoreHandle_t base_lock, const settings_t *settings);
