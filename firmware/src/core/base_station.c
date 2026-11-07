#include "base_station.h"

#include <stdio.h>
#include <string.h>

enum {
    PHASE_NOT_CONFIGURED,
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
    uint8_t frame[64];
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
        if (base->ack_state == ACK_WAITING && payload[0] == base->ack_class && payload[1] == base->ack_id) {
            base->ack_state = (id == UBX_ACK_ACK) ? ACK_DONE : ACK_REFUSED;
        }
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
        base->horizontal_accuracy_tenth_mm = u32_le(payload + 28);
        base->have_position = true;
    } else if (id == UBX_NAV_SVIN && length == 40) {
        base->survey_elapsed_s = u32_le(payload + 8);
        base->survey_mean_accuracy_tenth_mm = u32_le(payload + 28);
        base->survey_valid = payload[36] != 0;
    }
}

static void on_rtcm(void *ctx, const uint8_t *frame, uint16_t length)
{
    base_station_t *base = ctx;
    base->rtcm_seen = true;
    base->last_rtcm_ms = base->now_ms;

    // Whole frames go out as soon as they are complete, so corrections are as fresh as they can be
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
    if (!caster_is_open(&base->caster) && network && rtcm_flowing && (int32_t)(now - base->next_connect_ms) >= 0) {
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

    if (base->phase == PHASE_NOT_CONFIGURED) return;

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

void base_init(base_station_t *base, const base_hal_t *hal, const base_caster_settings_t *settings, const base_mode_t *mode)
{
    memset(base, 0, sizeof(*base));
    base->hal = *hal;
    base->settings = *settings;
    base->mode = *mode;
    base->backoff_ms = BACKOFF_FIRST_MS;

    gnss_stream_init(&base->stream, on_ubx, on_rtcm, base);
    caster_init(&base->caster);

    // Connecting with empty settings would only count as a bad connection against this IP on a public caster
    if (settings->host[0] == '\0' || settings->mountpoint[0] == '\0' || settings->password[0] == '\0') {
        base->errors |= BASE_ERROR_NOT_CONFIGURED;
        base->phase = PHASE_NOT_CONFIGURED;
        return;
    }

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

// ------------------------------------------------------------------------------------------------
// Status
// ------------------------------------------------------------------------------------------------

static const char *phase_name(int phase)
{
    switch (phase) {
    case PHASE_NOT_CONFIGURED: return "not_configured";
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

    return snprintf(out, capacity,
        "{\"phase\":\"%s\",\"mode\":\"%s\",\"survey_setting_m\":%.3f,\"survey_setting_s\":%u,\"fixed_position\":\"%s\","
        "\"have_position\":%s,\"lat\":%.7f,\"lon\":%.7f,\"height_m\":%.3f,\"accuracy_m\":%.4f,\"satellites\":%u,\"fix_type\":%u,"
        "\"survey_elapsed_s\":%u,\"survey_accuracy_m\":%.4f,\"survey_valid\":%s,"
        "\"caster_connected\":%s,\"caster_message\":\"%s\",\"sent_age_ms\":%d,\"frames_sent\":%u,\"bytes_sent\":%u,"
        "\"rtcm_errors\":%u,\"errors\":[%s]}",
        phase_name(base->phase),
        base->mode.kind == BASE_MODE_FIXED ? "fixed" : "survey",
        base->mode.survey_accuracy_mm / 1000.0, (unsigned)base->mode.survey_seconds, fixed_text,
        base->have_position ? "true" : "false",
        base->latitude_e7 / 1e7, base->longitude_e7 / 1e7, base->height_mm / 1000.0,
        base->horizontal_accuracy_tenth_mm / 10000.0, base->satellites, base->fix_type,
        (unsigned)base->survey_elapsed_s, base->survey_mean_accuracy_tenth_mm / 10000.0, base->survey_valid ? "true" : "false",
        caster_is_streaming(&base->caster) ? "true" : "false", message,
        base->sent_any ? (int)(base->now_ms - base->last_sent_ms) : -1,
        (unsigned)base->frames_sent, (unsigned)base->bytes_sent,
        (unsigned)base->stream.rtcm_errors, errors);
}
