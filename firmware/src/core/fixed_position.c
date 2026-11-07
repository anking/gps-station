#include "fixed_position.h"

#include <stddef.h>
#include <string.h>

// Reads a plain decimal number as an integer count of 10^-decimals units, rounding any further digits.
static bool parse_scaled(const char *text, int decimals, int64_t *value)
{
    if (text == NULL) return false;

    while (*text == ' ') text++;

    bool negative = false;
    if (*text == '-') {
        negative = true;
        text++;
    }

    if (*text < '0' || *text > '9') return false;

    int64_t result = 0;
    int integer_digits = 0;
    while (*text >= '0' && *text <= '9') {
        if (++integer_digits > 6) return false;
        result = result * 10 + (*text++ - '0');
    }

    int seen = 0;
    bool round_up = false;
    if (*text == '.') {
        text++;
        if (*text < '0' || *text > '9') return false;
        while (*text >= '0' && *text <= '9') {
            if (seen < decimals) {
                result = result * 10 + (*text - '0');
            } else if (seen == decimals) {
                round_up = *text >= '5';
            }
            seen++;
            text++;
        }
    }

    while (*text == ' ') text++;
    if (*text != '\0') return false;

    for (; seen < decimals; seen++) result *= 10;
    if (round_up) result++;

    *value = negative ? -result : result;
    return true;
}

static void split(int64_t fine, int32_t *main_part, int8_t *remainder)
{
    int64_t main_value = fine / 100; // Rounds toward zero, so the remainder keeps the sign
    *main_part = (int32_t)main_value;
    *remainder = (int8_t)(fine - main_value * 100);
}

bool fixed_position_parse(const char *latitude, const char *longitude, const char *height,
                          fixed_position_t *position, const char **error)
{
    int64_t lat, lon, meters;

    if (!parse_scaled(latitude, 9, &lat) || lat < -90000000000LL || lat > 90000000000LL) {
        *error = "latitude must be a decimal number of degrees between -90 and 90";
        return false;
    }

    if (!parse_scaled(longitude, 9, &lon) || lon < -180000000000LL || lon > 180000000000LL) {
        *error = "longitude must be a decimal number of degrees between -180 and 180";
        return false;
    }

    if (!parse_scaled(height, 4, &meters) || meters < -5000000LL || meters > 90000000LL) {
        *error = "height must be a decimal number of meters above the ellipsoid, between -500 and 9000";
        return false;
    }

    if (lat == 0 && lon == 0) {
        *error = "latitude and longitude are both zero";
        return false;
    }

    split(lat, &position->latitude_e7, &position->latitude_hp);
    split(lon, &position->longitude_e7, &position->longitude_hp);
    split(meters, &position->height_cm, &position->height_hp);
    return true;
}

bool fixed_position_parse_combined(const char *text, fixed_position_t *position, const char **error)
{
    char copy[64];
    if (text == NULL || strlen(text) >= sizeof(copy)) {
        *error = "expected latitude:longitude:height";
        return false;
    }
    strcpy(copy, text);

    char *first = strchr(copy, ':');
    char *second = first ? strchr(first + 1, ':') : NULL;
    if (second == NULL || strchr(second + 1, ':') != NULL) {
        *error = "expected latitude:longitude:height";
        return false;
    }

    *first = '\0';
    *second = '\0';
    return fixed_position_parse(copy, first + 1, second + 1, position, error);
}
