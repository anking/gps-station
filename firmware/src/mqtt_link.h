// Reports to the monitoring service over MQTT, and takes its one command: check for a firmware update now.
//
//   bases/<mac>/status     {"online":true}, retained, and {"online":false} as the last will
//   bases/<mac>/info       model, firmware and the address of the web UI, retained
//   bases/<mac>/telemetry  the status the web UI shows, every 5 seconds
//   bases/<mac>/cmd        {"id":"...","action":"update_firmware","params":{"firmware_id":7}}
//   bases/<mac>/responses  {"id":"...","ok":true}
#pragma once

#include "base_station.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "settings.h"

// Does nothing when no broker is set
void mqtt_link_start(base_station_t *base, SemaphoreHandle_t base_lock, const settings_t *settings);
