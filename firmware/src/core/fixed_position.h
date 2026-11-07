// A surveyed base position in the units UBX-CFG-TMODE3 expects.
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    int32_t latitude_e7;    // 1e-7 degrees
    int8_t latitude_hp;     // 1e-9 degrees
    int32_t longitude_e7;
    int8_t longitude_hp;
    int32_t height_cm;      // above the ellipsoid
    int8_t height_hp;       // 0.1 mm
} fixed_position_t;

// Parses decimal text exactly, without going through floating point, which would lose digits of a surveyed position.
// Degrees, degrees, meters above the ellipsoid. On failure returns false and sets *error to the reason.
bool fixed_position_parse(const char *latitude, const char *longitude, const char *height,
                          fixed_position_t *position, const char **error);

// Parses "latitude:longitude:height".
bool fixed_position_parse_combined(const char *text, fixed_position_t *position, const char **error);
