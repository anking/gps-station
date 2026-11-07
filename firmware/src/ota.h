// Over-the-air updates: checks the update server on boot and every 10 minutes, the same way the solar tracker does.
#pragma once

#include <stdbool.h>
#include <stddef.h>

// auto_update false leaves only checks that someone asks for
void ota_start(bool auto_update);

// Check now, without waiting for the next poll. firmware_id above 0 asks for that one release, which can be a
// downgrade. Returns false if a check is already running.
bool ota_request_check(int firmware_id);

// What the last check found, in words. Safe from any task, and safe to put inside a JSON string.
void ota_status(char *out, size_t capacity);
