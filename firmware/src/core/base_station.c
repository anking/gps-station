#include "base_station.h"

#include <stdio.h>
#include <string.h>

enum {
    PHASE_DETECT,
    PHASE_SET_BAUD,
    PHASE_CONFIGURE,
    PHASE_SURVEY,
    PHASE_ENABLE_RTCM,
    PHASE_RUN,
    PHASE_RETRY,
};

enum { ACK_IDLE, ACK_WAITING, ACK_DONE, ACK_REFUSED };

#define TARGET_BAUD 230400u
#define DETECT_WAIT_MS 300u
#define SET_BAUD_SETTLE_MS 150u
#define ACK_TIMEOUT_MS 1000u
#define ACK_ATTEMPTS 3
#define RETRY_DELAY_MS 5000u
#define STATUS_POLL_MS 1000u
#define GPS_SILENCE_MS 5000u
#define RTCM_STALL_MS 5000u
#define SKY_POLL_EVERY 5   // Status polls, so about every 5 seconds: it is long, and only for people looking at the page
#define SIGNALS_POLL_OFFSET 2          // The signal list is asked for between satellite lists, as often
#define SIGNAL_SETTINGS_POLL_EVERY 60  // About once a minute: they change only when someone changes them
#define SINGLE_BAND_MIN_FIRST 8        // First-band signals before the second band can be judged against them
#define SINGLE_BAND_READINGS 3         // In a row, about 15 seconds, so a second band still coming back is not a warning

// Public casters count failed connections per IP and ban the address
#define BACKOFF_FIRST_MS 15000u
#define BACKOFF_MAX_MS 900000u
#define BANNED_DELAY_MS 3600000u
#define HEALTHY_CONNECTION_MS 60000u

static const uint32_t BAUD_RATES[] = { TARGET_BAUD, 38400, 115200, 460800, 9600 };
#define BAUD_RATE_COUNT (sizeof(BAUD_RATES) / sizeof(BAUD_RATES[0]))

// MSM4 for each constellation, the station position, and the GLONASS biases every 10 seconds
static const struct { uint8_t id; uint8_t rate; } RTCM_MESSAGES[] = {
    { 0x05, 1 },    // 1005
    { 0x4A, 1 },    // 1074
    { 0x54, 1 },    // 1084
    { 0x5E, 1 },    // 1094
    { 0x7C, 1 },    // 1124
    { 0xE6, 10 },   // 1230
};
#define RTCM_MESSAGE_COUNT 6

// The module's band settings that are read, for each constellation: the constellation itself, its first band and its
// second band. QZSS is shown but not judged, since it is seen only around Japan and Australia.
static const struct { uint8_t gnss; bool judged; uint32_t keys[3]; } SIGNAL_SETTINGS[] = {
    { 0, true, { 0x1031001F, 0x10310001, 0x10310003 } },     // GPS: L1C/A, L2C
    { 2, true, { 0x10310021, 0x10310007, 0x1031000A } },     // Galileo: E1, E5b
    { 3, true, { 0x10310022, 0x1031000D, 0x1031000E } },     // BeiDou: B1I, B2I
    { 6, true, { 0x10310025, 0x10310018, 0x1031001A } },     // GLONASS: L1, L2
    { 5, false, { 0x10310024, 0x10310012, 0x10310015 } },    // QZSS: L1C/A, L2C
};
#define SIGNAL_SETTINGS_COUNT 5

// Where turning the second band on is kept: battery-backed RAM and flash as well as RAM, so it lasts through a power
// cut, or failing that RAM alone, until the module loses power
static const uint8_t BANDS_LAYERS[] = { 0x07, 0x01 };
#define BANDS_LAYER_COUNT 2
#define LAYER_FLASH 0x04

static uint32_t u32_le(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void put_u32_le(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
    p[2] = (uint8_t)(v >> 16);
    p[3] = (uint8_t)(v >> 24);
}

static void send_ubx(base_station_t *base, uint8_t cls, uint8_t id, const uint8_t *payload, uint16_t length)
{
    uint8_t frame[128];
    size_t total = ubx_frame(frame, sizeof(frame), cls, id, payload, length);
    if (total > 0) base->hal.serial_write(base->hal.ctx, frame, total);
}

static void set_phase(base_station_t *base, int phase)
{
    base->phase = phase;
    base->phase_started_ms = base->now_ms;
    base->next_action_ms = base->now_ms;
    base->step = 0;
    base->ack_state = ACK_IDLE;
    base->attempts = 0;
}

static uint32_t next_backoff(base_station_t *base)
{
    uint32_t delay = base->backoff_ms;
    base->backoff_ms = (delay * 2 > BACKOFF_MAX_MS) ? BACKOFF_MAX_MS : delay * 2;
    return delay;
}

static void start_detect(base_station_t *base)
{
    if (caster_is_open(&base->caster)) {
        // Not the caster's fault, but a module that keeps dropping out must not mean rapid reconnects
        if (base->now_ms - base->connected_at_ms >= HEALTHY_CONNECTION_MS) base->backoff_ms = BACKOFF_FIRST_MS;
        base->next_connect_ms = base->now_ms + next_backoff(base);
        caster_close(&base->caster);
    }

    gnss_stream_reset(&base->stream);
    base->rtcm_seen = false;
    base->baud_index = 0;
    base->baud_replied = false;
    base->ubx_seen_since_detect = false;
    base->hal.serial_set_baud(base->hal.ctx, BAUD_RATES[0]);
    set_phase(base, PHASE_DETECT);
}

// ------------------------------------------------------------------------------------------------
// Bands
// ------------------------------------------------------------------------------------------------

// Which band a signal is on, from u-blox's signal numbers. SBAS and anything else is 0: none of it is in the corrections.
static uint8_t signal_band(uint8_t gnss, uint8_t signal)
{
    switch (gnss) {
    case 0: return signal == 0 ? 1 : (signal == 3 || signal == 4) ? 2 : 0;    // GPS: L1C/A; L2C
    case 2: return signal <= 1 ? 1 : (signal == 5 || signal == 6) ? 2 : 0;    // Galileo: E1; E5b
    case 3: return signal <= 1 ? 1 : (signal == 2 || signal == 3) ? 2 : 0;    // BeiDou: B1I; B2I
    case 5: return signal <= 1 ? 1 : (signal == 4 || signal == 5) ? 2 : 0;    // QZSS: L1C/A, L1S; L2C
    case 6: return signal == 0 ? 1 : signal == 2 ? 2 : 0;                     // GLONASS: L1; L2
    default: return 0;
    }
}

// The middle strength, from how many signals there are at each
static uint8_t median_strength(const uint8_t counts[64], unsigned total)
{
    unsigned seen = 0;
    for (uint8_t cno = 0; cno < 64 && total > 0; cno++) {
        seen += counts[cno];
        if (seen > total / 2u) return cno;
    }
    return 0;
}

static void read_signals(base_station_t *base, const uint8_t *payload)
{
    uint8_t count = payload[5];
    uint8_t strengths[2][64] = { { 0 } };
    base_band_t bands[2] = { { 0 } };

    base->signal_count = 0;
    for (unsigned i = 0; i < count && base->signal_count < BASE_MAX_SIGNALS; i++) {
        const uint8_t *entry = payload + 8 + 16 * i;
        if (entry[6] == 0) continue;    // Searched for, not heard
        base_signal_t *signal = &base->signals[base->signal_count++];
        signal->gnss = entry[0];
        signal->id = entry[1];
        signal->band = signal_band(entry[0], entry[2]);
        signal->cno = entry[6];
        signal->used = (entry[10] & 0x08u) != 0;
        if (signal->band == 0) continue;

        base_band_t *band = &bands[signal->band - 1];
        band->heard++;
        if (signal->used) band->used++;
        strengths[signal->band - 1][signal->cno < 63 ? signal->cno : 63]++;
    }
    for (int b = 0; b < 2; b++) bands[b].median_cno = median_strength(strengths[b], bands[b].heard);

    base->first_band = bands[0];
    base->second_band = bands[1];
    base->have_signals = true;
    base->signals_at_ms = base->now_ms;

    // A sky full of first-band signals and few or none on the second: corrections a rover can hardly fix with
    bool single = bands[0].heard >= SINGLE_BAND_MIN_FIRST && bands[1].heard * 2u < bands[0].heard;
    if (!single) {
        base->single_band_readings = 0;
        base->errors &= ~BASE_ERROR_SINGLE_BAND;
    } else if (++base->single_band_readings >= SINGLE_BAND_READINGS) {
        base->single_band_readings = SINGLE_BAND_READINGS;
        base->errors |= BASE_ERROR_SINGLE_BAND;
    }
}

static bool setting_on(const base_station_t *base, int constellation, int which)
{
    return (base->signal_settings >> (3 * constellation + which)) & 1u;
}

static void read_signal_settings(base_station_t *base, const uint8_t *payload, uint16_t length)
{
    // Version, layer and position, then each setting's key and value: one byte, as these are all on or off
    uint32_t settings = 0;
    int found = 0;
    for (uint16_t at = 4; at + 5u <= length; at += 5) {
        uint32_t key = u32_le(payload + at);
        if (((key >> 28) & 7u) != 1) return;   // Not an on or off setting, so not an answer to this firmware's question
        for (int i = 0; i < SIGNAL_SETTINGS_COUNT; i++) {
            for (int which = 0; which < 3; which++) {
                if (SIGNAL_SETTINGS[i].keys[which] != key) continue;
                found++;
                if (payload[at + 4]) settings |= 1u << (3 * i + which);
            }
        }
    }
    if (found != 3 * SIGNAL_SETTINGS_COUNT) return;

    base->signal_settings = settings;
    base->have_signal_settings = true;
    base->signal_settings_at_ms = base->now_ms;
}

static void poll_signal_settings(base_station_t *base)
{
    // Version 0, the settings in use, from the first; then the keys
    uint8_t payload[4 + 4 * 3 * SIGNAL_SETTINGS_COUNT] = { 0 };
    size_t at = 4;
    for (int i = 0; i < SIGNAL_SETTINGS_COUNT; i++) {
        for (int which = 0; which < 3; which++, at += 4) put_u32_le(payload + at, SIGNAL_SETTINGS[i].keys[which]);
    }
    send_ubx(base, UBX_CLASS_CFG, UBX_CFG_VALGET, payload, (uint16_t)at);
}

static void send_second_band(base_station_t *base)
{
    // Both bands of every constellation, since a second band is refused without its first, but the constellations
    // themselves left as they are
    uint8_t payload[4 + 5 * 2 * SIGNAL_SETTINGS_COUNT] = { 0 };
    payload[1] = BANDS_LAYERS[base->bands_layer];
    size_t at = 4;
    for (int i = 0; i < SIGNAL_SETTINGS_COUNT; i++) {
        for (int which = 1; which <= 2; which++, at += 5) {
            put_u32_le(payload + at, SIGNAL_SETTINGS[i].keys[which]);
            payload[at + 4] = 1;
        }
    }
    send_ubx(base, UBX_CLASS_CFG, UBX_CFG_VALSET, payload, (uint16_t)at);
    base->bands_request = BASE_BANDS_WAITING;
    base->bands_deadline_ms = base->now_ms + ACK_TIMEOUT_MS;
}

static void bands_answered(base_station_t *base, bool accepted)
{
    if (accepted) {
        base->bands_request = (BANDS_LAYERS[base->bands_layer] & LAYER_FLASH) ? BASE_BANDS_SAVED : BASE_BANDS_ON_FOR_NOW;
        base->signal_settings_due = true;
    } else if (base->bands_layer + 1 < BANDS_LAYER_COUNT) {
        // A module that will not save it can still have it until it loses power
        base->bands_layer++;
        base->bands_attempts = 0;
        base->bands_request = BASE_BANDS_WANTED;
    } else {
        base->bands_request = BASE_BANDS_REFUSED;
    }
}

static void run_bands_request(base_station_t *base)
{
    if (base->bands_request == BASE_BANDS_WAITING && (int32_t)(base->now_ms - base->bands_deadline_ms) >= 0) {
        base->bands_request = ++base->bands_attempts >= ACK_ATTEMPTS ? BASE_BANDS_REFUSED : BASE_BANDS_WANTED;
    }
    if (base->bands_request == BASE_BANDS_WANTED) send_second_band(base);
}

// ------------------------------------------------------------------------------------------------
// Messages from the module
// ------------------------------------------------------------------------------------------------

static void on_ubx(void *ctx, uint8_t cls, uint8_t id, const uint8_t *payload, uint16_t length)
{
    base_station_t *base = ctx;
    base->last_ubx_ms = base->now_ms;
    base->ubx_seen_since_detect = true;
    base->errors &= ~BASE_ERROR_GPS_NO_DATA;

    if (cls == UBX_CLASS_CFG || cls == UBX_CLASS_ACK) base->baud_replied = true;

    if (cls == UBX_CLASS_ACK && length >= 2) {
        if (base->bands_request == BASE_BANDS_WAITING && payload[0] == UBX_CLASS_CFG && payload[1] == UBX_CFG_VALSET) {
            bands_answered(base, id == UBX_ACK_ACK);
        }
        if (base->ack_state == ACK_WAITING && payload[0] == base->ack_class && payload[1] == base->ack_id) {
            base->ack_state = (id == UBX_ACK_ACK) ? ACK_DONE : ACK_REFUSED;
        }
        return;
    }

    if (cls == UBX_CLASS_CFG && id == UBX_CFG_VALGET) {
        read_signal_settings(base, payload, length);
        return;
    }

    if (cls != UBX_CLASS_NAV) return;

    if (id == UBX_NAV_PVT && length == 92) {
        base->fix_type = payload[20];
        base->satellites = payload[23];
    } else if (id == UBX_NAV_HPPOSLLH && length == 36) {
        base->longitude_e7 = (int32_t)u32_le(payload + 8);
        base->latitude_e7 = (int32_t)u32_le(payload + 12);
        base->height_mm = (int32_t)u32_le(payload + 16);
        base->height_msl_mm = (int32_t)u32_le(payload + 20);
        base->longitude_hp = (int8_t)payload[24];
        base->latitude_hp = (int8_t)payload[25];
        base->height_hp = (int8_t)payload[26];
        base->height_msl_hp = (int8_t)payload[27];
        base->horizontal_accuracy_tenth_mm = u32_le(payload + 28);
        base->have_position = true;
    } else if (id == UBX_NAV_SVIN && length == 40) {
        base->survey_elapsed_s = u32_le(payload + 8);
        base->survey_mean_accuracy_tenth_mm = u32_le(payload + 28);
        base->survey_valid = payload[36] != 0;
    } else if (id == UBX_NAV_SAT && length >= 8 && length >= 8u + 12u * payload[5]) {
        uint8_t count = payload[5];
        base->sky_count = 0;
        for (uint8_t i = 0; i < count && base->sky_count < BASE_MAX_SATELLITES; i++) {
            const uint8_t *entry = payload + 8 + 12 * i;
            base_satellite_t *satellite = &base->sky[base->sky_count++];
            satellite->gnss = entry[0];
            satellite->id = entry[1];
            satellite->cno = entry[2];
            satellite->elevation = (int8_t)entry[3];
            satellite->azimuth = (int16_t)(entry[4] | (entry[5] << 8));
            satellite->used = (u32_le(entry + 8) & 0x08u) != 0;
        }
        base->have_sky = true;
        base->sky_at_ms = base->now_ms;
    } else if (id == UBX_NAV_SIG && length >= 8 && length >= 8u + 16u * payload[5]) {
        read_signals(base, payload);
    }
}

static void on_rtcm(void *ctx, const uint8_t *frame, uint16_t length)
{
    base_station_t *base = ctx;
    base->rtcm_seen = true;
    base->last_rtcm_ms = base->now_ms;

    // Whole frames go out as soon as they are complete, so corrections are as fresh as they can be.
    // Rovers first: sending to a slow caster can wait, and this cannot.
    direct_server_send(&base->direct, frame, length);

    if (caster_is_streaming(&base->caster) && caster_send(&base->caster, frame, length)) {
        base->frames_sent++;
        base->bytes_sent += length;
        base->sent_any = true;
        base->last_sent_ms = base->now_ms;
    }
}

// ------------------------------------------------------------------------------------------------
// Configuration steps
// ------------------------------------------------------------------------------------------------

static void build_port_config(uint8_t *payload, uint32_t baud)
{
    memset(payload, 0, 20);
    payload[0] = 1;                     // UART1
    put_u32_le(payload + 4, 0x000008D0);// 8 data bits, no parity, 1 stop bit
    put_u32_le(payload + 8, baud);
    payload[12] = 0x23;                 // In: UBX, NMEA, RTCM3
    payload[14] = 0x21;                 // Out: UBX, RTCM3. No NMEA noise.
}

static void build_tmode3(const base_station_t *base, uint8_t *payload, int mode)
{
    memset(payload, 0, 40);
    payload[2] = (uint8_t)mode;

    if (mode == BASE_MODE_FIXED) {
        const fixed_position_t *p = &base->mode.fixed;
        payload[3] = 1;                 // The position is latitude, longitude, height rather than ECEF
        put_u32_le(payload + 4, (uint32_t)p->latitude_e7);
        put_u32_le(payload + 8, (uint32_t)p->longitude_e7);
        put_u32_le(payload + 12, (uint32_t)p->height_cm);
        payload[16] = (uint8_t)p->latitude_hp;
        payload[17] = (uint8_t)p->longitude_hp;
        payload[18] = (uint8_t)p->height_hp;
    } else if (mode == BASE_MODE_SURVEY) {
        put_u32_le(payload + 24, base->mode.survey_seconds);
        put_u32_le(payload + 28, base->mode.survey_accuracy_mm * 10); // In 0.1 mm
    }
}

static void build_rtcm_rate(uint8_t *payload, uint8_t id, uint8_t rate)
{
    memset(payload, 0, 8);
    payload[0] = 0xF5;
    payload[1] = id;
    payload[3] = rate;                  // UART1 is the second of the six port rates
}

// Sends the given step of the current phase and returns true, or returns false when there are no more.
static bool send_step(base_station_t *base)
{
    uint8_t payload[40];

    if (base->phase == PHASE_ENABLE_RTCM) {
        if (base->step >= RTCM_MESSAGE_COUNT) return false;
        build_rtcm_rate(payload, RTCM_MESSAGES[base->step].id, RTCM_MESSAGES[base->step].rate);
        base->ack_id = UBX_CFG_MSG;
        send_ubx(base, UBX_CLASS_CFG, UBX_CFG_MSG, payload, 8);
    } else {
        // Start from a known state: the module keeps its last mode for as long as it has power
        int step = base->step;
        if (step == 0) {
            build_port_config(payload, TARGET_BAUD);
            base->ack_id = UBX_CFG_PRT;
            send_ubx(base, UBX_CLASS_CFG, UBX_CFG_PRT, payload, 20);
        } else if (step == 1) {
            memset(payload, 0, 6);
            payload[0] = 0xE8;          // One measurement per 1000 ms: more would only multiply the upload
            payload[1] = 0x03;
            payload[2] = 1;
            payload[4] = 1;
            base->ack_id = UBX_CFG_RATE;
            send_ubx(base, UBX_CLASS_CFG, UBX_CFG_RATE, payload, 6);
        } else if (step < 2 + RTCM_MESSAGE_COUNT) {
            build_rtcm_rate(payload, RTCM_MESSAGES[step - 2].id, 0);
            base->ack_id = UBX_CFG_MSG;
            send_ubx(base, UBX_CLASS_CFG, UBX_CFG_MSG, payload, 8);
        } else if (step == 2 + RTCM_MESSAGE_COUNT) {
            build_tmode3(base, payload, 0);
            base->ack_id = UBX_CFG_TMODE3;
            send_ubx(base, UBX_CLASS_CFG, UBX_CFG_TMODE3, payload, 40);
        } else if (step == 3 + RTCM_MESSAGE_COUNT) {
            build_tmode3(base, payload, base->mode.kind);
            base->ack_id = UBX_CFG_TMODE3;
            send_ubx(base, UBX_CLASS_CFG, UBX_CFG_TMODE3, payload, 40);
        } else {
            return false;
        }
    }

    base->ack_class = UBX_CLASS_CFG;
    base->ack_state = ACK_WAITING;
    base->ack_deadline_ms = base->now_ms + ACK_TIMEOUT_MS;
    return true;
}

static void configuration_failed(base_station_t *base)
{
    base->errors |= BASE_ERROR_GPS_NOT_FOUND;
    set_phase(base, PHASE_RETRY);
}

// Runs the steps of the current phase. Returns true once they are all acknowledged.
static bool run_steps(base_station_t *base)
{
    if (base->ack_state == ACK_DONE) {
        base->step++;
        base->attempts = 0;
        base->ack_state = ACK_IDLE;
    } else if (base->ack_state == ACK_REFUSED ||
               (base->ack_state == ACK_WAITING && (int32_t)(base->now_ms - base->ack_deadline_ms) >= 0)) {
        if (++base->attempts >= ACK_ATTEMPTS) {
            configuration_failed(base);
            return false;
        }
        base->ack_state = ACK_IDLE;
    }

    if (base->ack_state == ACK_IDLE) return !send_step(base);

    return false;
}

static void poll_nav(base_station_t *base, uint8_t id)
{
    send_ubx(base, UBX_CLASS_NAV, id, NULL, 0);
}

static void poll_status(base_station_t *base)
{
    if ((int32_t)(base->now_ms - base->next_action_ms) < 0) return;
    base->next_action_ms = base->now_ms + STATUS_POLL_MS;

    if (base->phase == PHASE_SURVEY) poll_nav(base, UBX_NAV_SVIN);
    poll_nav(base, UBX_NAV_HPPOSLLH);
    poll_nav(base, UBX_NAV_PVT);

    uint32_t poll = base->status_polls++;
    if (poll % SKY_POLL_EVERY == 0) poll_nav(base, UBX_NAV_SAT);
    if (poll % SKY_POLL_EVERY == SIGNALS_POLL_OFFSET) poll_nav(base, UBX_NAV_SIG);
    if (base->signal_settings_due || poll % SIGNAL_SETTINGS_POLL_EVERY == 1) {
        base->signal_settings_due = false;
        poll_signal_settings(base);
    }
}

// ------------------------------------------------------------------------------------------------
// Caster connection
// ------------------------------------------------------------------------------------------------

static void maintain_caster(base_station_t *base)
{
    uint32_t now = base->now_ms;

    switch (caster_poll(&base->caster, now)) {
    case CASTER_EVENT_CONNECTED:
        base->errors &= ~(BASE_ERROR_CASTER | BASE_ERROR_BANNED);
        base->connected_at_ms = now;
        break;

    case CASTER_EVENT_FAILED:
        if (base->caster.reply == CASTER_REPLY_BANNED) {
            base->errors |= BASE_ERROR_BANNED;
            base->next_connect_ms = now + BANNED_DELAY_MS;
        } else {
            base->errors |= BASE_ERROR_CASTER;
            base->next_connect_ms = now + next_backoff(base);
        }
        break;

    case CASTER_EVENT_LOST:
        // Only a connection that lasted counts as a fresh start
        if (now - base->connected_at_ms >= HEALTHY_CONNECTION_MS) base->backoff_ms = BACKOFF_FIRST_MS;
        base->errors |= BASE_ERROR_CASTER;
        base->next_connect_ms = now + next_backoff(base);
        break;

    default:
        break;
    }

    bool rtcm_flowing = base->rtcm_seen && now - base->last_rtcm_ms < RTCM_STALL_MS;

    if (rtcm_flowing) base->errors &= ~BASE_ERROR_RTCM_STALLED;
    else if (now - base->phase_started_ms >= RTCM_STALL_MS) base->errors |= BASE_ERROR_RTCM_STALLED;

    bool network = base->hal.network_ready(base->hal.ctx);
    if (network) base->errors &= ~BASE_ERROR_NETWORK_DOWN;
    else base->errors |= BASE_ERROR_NETWORK_DOWN;

    // Only while corrections are flowing: a source that connects and sends nothing is dropped and counted against the IP
    if (base->caster_configured && !caster_is_open(&base->caster) && network && rtcm_flowing && (int32_t)(now - base->next_connect_ms) >= 0) {
        caster_open(&base->caster, base->settings.host, base->settings.port, base->settings.mountpoint, base->settings.password, now);
        // Reaching it or not, the next attempt waits until something reschedules it
        base->next_connect_ms = now + HEALTHY_CONNECTION_MS;
    }
}

// ------------------------------------------------------------------------------------------------
// State machine
// ------------------------------------------------------------------------------------------------

static void run_detect(base_station_t *base)
{
    uint32_t now = base->now_ms;

    if (base->baud_replied) {
        base->detected_baud = BAUD_RATES[base->baud_index];
        base->errors &= ~BASE_ERROR_GPS_NOT_FOUND;

        if (base->detected_baud == TARGET_BAUD) {
            base->last_ubx_ms = now;
            set_phase(base, PHASE_CONFIGURE);
        } else {
            uint8_t payload[20];
            build_port_config(payload, TARGET_BAUD);
            send_ubx(base, UBX_CLASS_CFG, UBX_CFG_PRT, payload, 20);
            set_phase(base, PHASE_SET_BAUD);
        }
        return;
    }

    if ((int32_t)(now - base->next_action_ms) < 0) return;

    if (now != base->phase_started_ms && base->step > 0) {
        // That rate got no answer: try the next
        base->baud_index = (int)(((size_t)base->baud_index + 1) % BAUD_RATE_COUNT);
        if (base->baud_index == 0) base->errors |= BASE_ERROR_GPS_NOT_FOUND;
        base->hal.serial_set_baud(base->hal.ctx, BAUD_RATES[base->baud_index]);
        gnss_stream_reset(&base->stream);
    }

    base->step = 1;
    send_ubx(base, UBX_CLASS_CFG, UBX_CFG_RATE, NULL, 0);
    base->next_action_ms = now + DETECT_WAIT_MS;
}

static void check_module_alive(base_station_t *base)
{
    if (base->now_ms - base->last_ubx_ms >= GPS_SILENCE_MS) {
        // Unplugged or power cycled. It may be back at its default speed, with its settings gone, so start over.
        base->errors |= BASE_ERROR_GPS_NO_DATA;
        start_detect(base);
    }
}

void base_tick(base_station_t *base, uint32_t now_ms)
{
    base->now_ms = now_ms;

    direct_server_poll(&base->direct, now_ms);

    if (base->mode_change_pending) {
        base->mode_change_pending = false;
        caster_close(&base->caster);
        base->rtcm_seen = false;
        base->survey_valid = false;
        base->survey_elapsed_s = 0;
        base->last_ubx_ms = now_ms;
        // The new position changes every rover fix: reconnect promptly, this is not a failure
        base->next_connect_ms = now_ms;
        set_phase(base, PHASE_CONFIGURE);
    }

    switch (base->phase) {
    case PHASE_DETECT:
        run_detect(base);
        break;

    case PHASE_SET_BAUD:
        if (now_ms - base->phase_started_ms >= SET_BAUD_SETTLE_MS) {
            base->hal.serial_set_baud(base->hal.ctx, TARGET_BAUD);
            gnss_stream_reset(&base->stream);
            start_detect(base);
        }
        break;

    case PHASE_CONFIGURE:
        check_module_alive(base);
        if (base->phase == PHASE_CONFIGURE && run_steps(base)) {
            base->receiver_mode = (uint8_t)base->mode.kind;
            set_phase(base, base->mode.kind == BASE_MODE_SURVEY ? PHASE_SURVEY : PHASE_ENABLE_RTCM);
        }
        break;

    case PHASE_SURVEY:
        check_module_alive(base);
        if (base->phase != PHASE_SURVEY) break;
        poll_status(base);
        run_bands_request(base);
        if (base->survey_valid) set_phase(base, PHASE_ENABLE_RTCM);
        break;

    case PHASE_ENABLE_RTCM:
        check_module_alive(base);
        if (base->phase == PHASE_ENABLE_RTCM && run_steps(base)) set_phase(base, PHASE_RUN);
        break;

    case PHASE_RUN:
        check_module_alive(base);
        if (base->phase != PHASE_RUN) break;
        poll_status(base);
        run_bands_request(base);
        maintain_caster(base);
        break;

    case PHASE_RETRY:
        if (now_ms - base->phase_started_ms >= RETRY_DELAY_MS) start_detect(base);
        break;

    default:
        break;
    }
}

void base_on_serial(base_station_t *base, const uint8_t *data, size_t length)
{
    gnss_stream_feed(&base->stream, data, length);
}

void base_init(base_station_t *base, const base_hal_t *hal, const base_caster_settings_t *settings, const base_mode_t *mode, uint16_t direct_port)
{
    memset(base, 0, sizeof(*base));
    base->hal = *hal;
    base->settings = *settings;
    base->mode = *mode;
    base->backoff_ms = BACKOFF_FIRST_MS;

    gnss_stream_init(&base->stream, on_ubx, on_rtcm, base);
    caster_init(&base->caster);
    direct_server_init(&base->direct, direct_port);

    // Connecting with empty settings would only count as a bad connection against this IP on a public caster.
    // It is only the backup, so rovers on the network can still be served without it.
    base->caster_configured = settings->host[0] != '\0' && settings->mountpoint[0] != '\0' && settings->password[0] != '\0';
    if (!base->caster_configured) base->errors |= BASE_ERROR_NOT_CONFIGURED;

    start_detect(base);
}

void base_set_survey(base_station_t *base, uint32_t accuracy_mm, uint32_t seconds)
{
    base->mode.kind = BASE_MODE_SURVEY;
    base->mode.survey_accuracy_mm = accuracy_mm;
    base->mode.survey_seconds = seconds;
    base->errors &= ~BASE_ERROR_INVALID_POSITION;
    base->mode_change_pending = true;
    if (base->hal.mode_changed) base->hal.mode_changed(base->hal.ctx, &base->mode);
}

bool base_set_fixed(base_station_t *base, const char *latitude, const char *longitude, const char *height, const char **error)
{
    fixed_position_t position;
    if (!fixed_position_parse(latitude, longitude, height, &position, error)) {
        base->errors |= BASE_ERROR_INVALID_POSITION;
        return false;
    }

    base->mode.kind = BASE_MODE_FIXED;
    base->mode.fixed = position;
    snprintf(base->mode.fixed_text, sizeof(base->mode.fixed_text), "%s:%s:%s", latitude, longitude, height);
    base->errors &= ~BASE_ERROR_INVALID_POSITION;
    base->mode_change_pending = true;
    if (base->hal.mode_changed) base->hal.mode_changed(base->hal.ctx, &base->mode);
    return true;
}

bool base_enable_second_band(base_station_t *base)
{
    // Only to a module that is configured and answering, and not twice at once
    if (base->phase != PHASE_RUN && base->phase != PHASE_SURVEY) return false;
    if (base->bands_request == BASE_BANDS_WANTED || base->bands_request == BASE_BANDS_WAITING) return false;

    base->bands_request = BASE_BANDS_WANTED;
    base->bands_layer = 0;
    base->bands_attempts = 0;
    return true;
}

// ------------------------------------------------------------------------------------------------
// Status
// ------------------------------------------------------------------------------------------------

static const char *phase_name(int phase)
{
    switch (phase) {
    case PHASE_DETECT:
    case PHASE_SET_BAUD: return "finding_module";
    case PHASE_CONFIGURE:
    case PHASE_ENABLE_RTCM: return "configuring";
    case PHASE_SURVEY: return "surveying";
    case PHASE_RUN: return "running";
    default: return "retrying";
    }
}

static void json_safe(char *out, size_t capacity, const char *text)
{
    size_t used = 0;
    for (; *text && used + 1 < capacity; text++) {
        char c = *text;
        out[used++] = (c == '"' || c == '\\' || c < 0x20 || c > 0x7E) ? ' ' : c;
    }
    out[used] = '\0';
}

// An exact decimal of value / 10^decimals, with no floating point to lose digits of a surveyed position.
static void exact_decimal(char *out, size_t capacity, int64_t value, int decimals)
{
    uint64_t scale = 1;
    for (int i = 0; i < decimals; i++) scale *= 10;
    uint64_t magnitude = value < 0 ? (uint64_t)(-(value + 1)) + 1u : (uint64_t)value;
    snprintf(out, capacity, "%s%llu.%0*llu", value < 0 ? "-" : "",
             (unsigned long long)(magnitude / scale), decimals, (unsigned long long)(magnitude % scale));
}

// Whether the module tracks the second band of the constellations it uses
static const char *second_band_setting(const base_station_t *base)
{
    if (!base->have_signal_settings) return "unknown";

    int judged = 0, on = 0;
    for (int i = 0; i < SIGNAL_SETTINGS_COUNT; i++) {
        if (!SIGNAL_SETTINGS[i].judged || !setting_on(base, i, 0)) continue;
        judged++;
        if (setting_on(base, i, 2)) on++;
    }
    return judged > 0 && on == judged ? "on" : on > 0 ? "partly" : "off";
}

static const char *bands_request_name(base_bands_request_t request)
{
    switch (request) {
    case BASE_BANDS_WANTED:
    case BASE_BANDS_WAITING: return "working";
    case BASE_BANDS_SAVED: return "saved";
    case BASE_BANDS_ON_FOR_NOW: return "on_until_power_off";
    case BASE_BANDS_REFUSED: return "refused";
    default: return "none";
    }
}

int base_status_json(const base_station_t *base, char *out, size_t capacity)
{
    static const struct { uint32_t flag; const char *name; } ERROR_NAMES[] = {
        { BASE_ERROR_NOT_CONFIGURED, "NTRIP_NOT_CONFIGURED" },
        { BASE_ERROR_GPS_NOT_FOUND, "GPS_NOT_CONNECTED" },
        { BASE_ERROR_GPS_NO_DATA, "GPS_NO_DATA" },
        { BASE_ERROR_NETWORK_DOWN, "NETWORK_DOWN" },
        { BASE_ERROR_CASTER, "NTRIP_CONNECTION_ERROR" },
        { BASE_ERROR_BANNED, "NTRIP_BANNED" },
        { BASE_ERROR_RTCM_STALLED, "RTCM_OUTPUT_STALLED" },
        { BASE_ERROR_INVALID_POSITION, "INVALID_FIXED_POSITION" },
        { BASE_ERROR_SINGLE_BAND, "SINGLE_BAND" },
    };

    char errors[200] = "";
    size_t used = 0;
    for (size_t i = 0; i < sizeof(ERROR_NAMES) / sizeof(ERROR_NAMES[0]); i++) {
        if (base->errors & ERROR_NAMES[i].flag) {
            used += (size_t)snprintf(errors + used, sizeof(errors) - used, "%s\"%s\"", used ? "," : "", ERROR_NAMES[i].name);
        }
    }

    char message[sizeof(base->caster.message)];
    json_safe(message, sizeof(message), base->caster.message);

    char fixed_text[sizeof(base->mode.fixed_text)];
    json_safe(fixed_text, sizeof(fixed_text), base->mode.fixed_text);

    // Room for the largest 64-bit value, which the compiler checks for, though a position never comes close
    char lat[48], lon[48], height[48], height_msl[48];
    exact_decimal(lat, sizeof(lat), (int64_t)base->latitude_e7 * 100 + base->latitude_hp, 9);
    exact_decimal(lon, sizeof(lon), (int64_t)base->longitude_e7 * 100 + base->longitude_hp, 9);
    exact_decimal(height, sizeof(height), (int64_t)base->height_mm * 10 + base->height_hp, 4);
    exact_decimal(height_msl, sizeof(height_msl), (int64_t)base->height_msl_mm * 10 + base->height_msl_hp, 4);

    return snprintf(out, capacity,
        "{\"phase\":\"%s\",\"mode\":\"%s\",\"survey_setting_m\":%.3f,\"survey_setting_s\":%u,\"fixed_position\":\"%s\","
        "\"have_position\":%s,\"lat\":%s,\"lon\":%s,\"height_m\":%s,\"height_msl_m\":%s,\"accuracy_m\":%.4f,\"satellites\":%u,\"fix_type\":%u,"
        "\"survey_elapsed_s\":%u,\"survey_accuracy_m\":%.4f,\"survey_valid\":%s,"
        "\"direct_port\":%u,\"direct_rovers\":%d,"
        "\"caster_connected\":%s,\"caster_message\":\"%s\",\"sent_age_ms\":%d,\"frames_sent\":%u,\"bytes_sent\":%u,"
        "\"bands\":{\"second\":\"%s\",\"l1\":[%u,%u,%u],\"l2\":[%u,%u,%u]},"
        "\"rtcm_errors\":%u,\"errors\":[%s]}",
        phase_name(base->phase),
        base->mode.kind == BASE_MODE_FIXED ? "fixed" : "survey",
        base->mode.survey_accuracy_mm / 1000.0, (unsigned)base->mode.survey_seconds, fixed_text,
        base->have_position ? "true" : "false",
        lat, lon, height, height_msl,
        base->horizontal_accuracy_tenth_mm / 10000.0, base->satellites, base->fix_type,
        (unsigned)base->survey_elapsed_s, base->survey_mean_accuracy_tenth_mm / 10000.0, base->survey_valid ? "true" : "false",
        (unsigned)base->direct.port, direct_server_rover_count(&base->direct),
        caster_is_streaming(&base->caster) ? "true" : "false", message,
        base->sent_any ? (int)(base->now_ms - base->last_sent_ms) : -1,
        (unsigned)base->frames_sent, (unsigned)base->bytes_sent,
        second_band_setting(base),
        base->first_band.heard, base->first_band.used, base->first_band.median_cno,
        base->second_band.heard, base->second_band.used, base->second_band.median_cno,
        (unsigned)base->stream.rtcm_errors, errors);
}

int base_sky_json(const base_station_t *base, char *out, size_t capacity)
{
    int used = snprintf(out, capacity, "{\"age_ms\":%d,\"sats\":[",
                        base->have_sky ? (int)(base->now_ms - base->sky_at_ms) : -1);

    for (uint8_t i = 0; i < base->sky_count && used >= 0 && (size_t)used < capacity; i++) {
        const base_satellite_t *s = &base->sky[i];
        used += snprintf(out + used, capacity - (size_t)used, "%s[%u,%u,%u,%d,%d,%d]", i ? "," : "",
                         s->gnss, s->id, s->cno, s->elevation, s->azimuth, s->used ? 1 : 0);
    }

    if (used >= 0 && (size_t)used < capacity) used += snprintf(out + used, capacity - (size_t)used, "]}");
    return used;
}

int base_signals_json(const base_station_t *base, char *out, size_t capacity)
{
    int used = snprintf(out, capacity, "{\"age_ms\":%d,\"settings_age_ms\":%d,\"second_band\":\"%s\",\"request\":\"%s\",\"settings\":[",
                        base->have_signals ? (int)(base->now_ms - base->signals_at_ms) : -1,
                        base->have_signal_settings ? (int)(base->now_ms - base->signal_settings_at_ms) : -1,
                        second_band_setting(base), bands_request_name(base->bands_request));

    for (int i = 0; base->have_signal_settings && i < SIGNAL_SETTINGS_COUNT && used >= 0 && (size_t)used < capacity; i++) {
        used += snprintf(out + used, capacity - (size_t)used, "%s[%u,%d,%d,%d]", i ? "," : "", SIGNAL_SETTINGS[i].gnss,
                         setting_on(base, i, 0), setting_on(base, i, 1), setting_on(base, i, 2));
    }

    if (used >= 0 && (size_t)used < capacity) used += snprintf(out + used, capacity - (size_t)used, "],\"signals\":[");

    for (uint8_t i = 0; i < base->signal_count && used >= 0 && (size_t)used < capacity; i++) {
        const base_signal_t *s = &base->signals[i];
        used += snprintf(out + used, capacity - (size_t)used, "%s[%u,%u,%u,%u,%d]", i ? "," : "",
                         s->gnss, s->id, s->band, s->cno, s->used ? 1 : 0);
    }

    if (used >= 0 && (size_t)used < capacity) used += snprintf(out + used, capacity - (size_t)used, "]}");
    return used;
}
