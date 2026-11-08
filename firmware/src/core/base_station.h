// The whole job of the base station: find and configure the ZED-F9P, survey or take a fixed position,
// and keep its RTCM corrections flowing, straight to rovers on the same network and to an NTRIP caster as their backup.
//
// Portable C with no operating system calls beyond BSD sockets, so the same code runs on the ESP32 and, for testing,
// on a PC against a simulated module. Nothing here blocks except looking up the caster's name.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "caster.h"
#include "direct_server.h"
#include "fixed_position.h"
#include "gnss_stream.h"

typedef enum {
    BASE_MODE_SURVEY = 1,   // Same numbers as the receiver's own CFG-TMODE-MODE
    BASE_MODE_FIXED = 2,
} base_mode_kind_t;

typedef struct {
    base_mode_kind_t kind;
    uint32_t survey_accuracy_mm;
    uint32_t survey_seconds;
    fixed_position_t fixed;
    char fixed_text[64];    // As it was entered, for showing it back
} base_mode_t;

typedef struct {
    char host[64];
    uint16_t port;
    char mountpoint[48];
    char password[48];
} base_caster_settings_t;

typedef struct {
    void (*serial_write)(void *ctx, const uint8_t *data, size_t length);
    void (*serial_set_baud)(void *ctx, uint32_t baud);
    bool (*network_ready)(void *ctx);
    void (*mode_changed)(void *ctx, const base_mode_t *mode);   // Remember it across restarts
    void *ctx;
} base_hal_t;

#define BASE_ERROR_NOT_CONFIGURED (1u << 0)
#define BASE_ERROR_GPS_NOT_FOUND (1u << 1)
#define BASE_ERROR_GPS_NO_DATA (1u << 2)
#define BASE_ERROR_NETWORK_DOWN (1u << 3)
#define BASE_ERROR_CASTER (1u << 4)
#define BASE_ERROR_BANNED (1u << 5)
#define BASE_ERROR_RTCM_STALLED (1u << 6)
#define BASE_ERROR_INVALID_POSITION (1u << 7)
#define BASE_ERROR_SINGLE_BAND (1u << 8)

#define BASE_MAX_SATELLITES 64
#define BASE_MAX_SIGNALS 160

typedef struct {
    uint8_t gnss;           // u-blox numbering: 0 GPS, 1 SBAS, 2 Galileo, 3 BeiDou, 5 QZSS, 6 GLONASS
    uint8_t id;
    uint8_t cno;            // Signal strength, dB-Hz
    int8_t elevation;       // Degrees, or -91 when not known
    int16_t azimuth;        // Degrees
    bool used;              // In the position
} base_satellite_t;

// One signal from one satellite. A rover gets an RTK fix far sooner and more reliably with two bands from each
// satellite, and the corrections carry only the bands the base itself hears.
typedef struct {
    uint8_t gnss;
    uint8_t id;
    uint8_t band;           // 1 for L1, E1 and B1I; 2 for the second band, L2, E5b and B2I; 0 for any other
    uint8_t cno;            // dB-Hz
    bool used;              // In the position
} base_signal_t;

typedef struct {
    uint8_t heard;
    uint8_t used;
    uint8_t median_cno;     // Of those heard, dB-Hz
} base_band_t;

// Turning the second band on, which is asked for from the page
typedef enum {
    BASE_BANDS_IDLE,
    BASE_BANDS_WANTED,
    BASE_BANDS_WAITING,
    BASE_BANDS_SAVED,       // On, and kept by the module through a power cut
    BASE_BANDS_ON_FOR_NOW,  // On until the module loses power: it would not save it
    BASE_BANDS_REFUSED,
} base_bands_request_t;

typedef struct {
    base_hal_t hal;
    base_caster_settings_t settings;
    base_mode_t mode;
    bool mode_change_pending;

    gnss_stream_t stream;
    caster_t caster;
    direct_server_t direct;

    int phase;
    uint32_t now_ms;
    uint32_t phase_started_ms;
    uint32_t next_action_ms;
    uint32_t last_ubx_ms;
    bool ubx_seen_since_detect;

    // Finding the module
    int baud_index;
    uint32_t detected_baud;
    bool baud_replied;

    // Sending configuration, one acknowledged message at a time
    int step;
    uint8_t ack_class;
    uint8_t ack_id;
    int ack_state;
    int attempts;
    uint32_t ack_deadline_ms;

    // Caster connection
    bool caster_configured;
    uint32_t backoff_ms;
    uint32_t next_connect_ms;
    uint32_t connected_at_ms;

    // What is reported
    uint32_t errors;
    bool have_position;
    int32_t latitude_e7;
    int32_t longitude_e7;
    int32_t height_mm;
    int8_t latitude_hp;     // 1e-9 degrees, so the position can be copied into a fixed one without losing anything
    int8_t longitude_hp;
    int8_t height_hp;       // 0.1 mm
    // Above mean sea level, by the module's own geoid model. Only for showing: a fixed position needs the ellipsoid
    // height, and the difference between the two is how a height above sea level is turned into one.
    int32_t height_msl_mm;
    int8_t height_msl_hp;
    uint32_t horizontal_accuracy_tenth_mm;
    uint8_t satellites;
    uint8_t fix_type;
    uint8_t receiver_mode;
    uint32_t survey_elapsed_s;
    uint32_t status_polls;
    base_satellite_t sky[BASE_MAX_SATELLITES];
    uint8_t sky_count;
    bool have_sky;
    uint32_t sky_at_ms;
    base_signal_t signals[BASE_MAX_SIGNALS];
    uint8_t signal_count;
    bool have_signals;
    uint32_t signals_at_ms;
    base_band_t first_band;
    base_band_t second_band;
    uint8_t single_band_readings;   // In a row, so the second band coming back after a restart is not a warning
    // Which constellations and bands the module tracks, one bit for each of the module's settings that are read
    uint32_t signal_settings;
    bool have_signal_settings;
    bool signal_settings_due;
    uint32_t signal_settings_at_ms;
    base_bands_request_t bands_request;
    int bands_layer;
    int bands_attempts;
    uint32_t bands_deadline_ms;
    uint32_t survey_mean_accuracy_tenth_mm;
    bool survey_valid;
    bool rtcm_seen;
    uint32_t last_rtcm_ms;
    uint32_t last_sent_ms;
    bool sent_any;
    uint32_t frames_sent;
    uint32_t bytes_sent;
} base_station_t;

// direct_port is where rovers on the network can connect, or 0 for nowhere.
void base_init(base_station_t *base, const base_hal_t *hal, const base_caster_settings_t *settings, const base_mode_t *mode, uint16_t direct_port);

// Bytes received from the module.
void base_on_serial(base_station_t *base, const uint8_t *data, size_t length);

// Call often, at least every 10-20 ms.
void base_tick(base_station_t *base, uint32_t now_ms);

void base_set_survey(base_station_t *base, uint32_t accuracy_mm, uint32_t seconds);

// Leaves the running mode alone and raises an error if the position is not valid. Returns whether it was accepted.
bool base_set_fixed(base_station_t *base, const char *latitude, const char *longitude, const char *height, const char **error);

// Writes the status as one JSON object. Returns its length, which is >= capacity if it did not fit.
int base_status_json(const base_station_t *base, char *out, size_t capacity);

// Writes the satellites the module sees, as {"age_ms":N,"sats":[[gnss,id,cno,elevation,azimuth,used],...]}.
// Same return as base_status_json.
int base_sky_json(const base_station_t *base, char *out, size_t capacity);

// Asks the module to track the second band of every constellation, and to keep that through a power cut. Tracking
// restarts, so corrections pause for a few seconds. Returns false if it cannot be asked now.
bool base_enable_second_band(base_station_t *base);

// Writes each signal the module hears and the module's band settings:
//   {"age_ms":N,"settings_age_ms":N,"second_band":"on|off|partly|unknown","request":"...",
//    "settings":[[gnss,constellation on,first band on,second band on],...],"signals":[[gnss,id,band,cno,used],...]}
// Same return as base_status_json.
int base_signals_json(const base_station_t *base, char *out, size_t capacity);
