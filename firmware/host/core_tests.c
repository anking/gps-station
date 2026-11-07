// Tests of the portable firmware core, run on a PC with: make -C firmware/host test
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "../src/core/base_station.h"
#include "../src/core/caster.h"
#include "../src/core/fixed_position.h"
#include "../src/core/gnss_stream.h"

static int failures = 0;

#define CHECK(condition) do { \
        if (!(condition)) { printf("FAILED %s:%d: %s\n", __FILE__, __LINE__, #condition); failures++; } \
    } while (0)

// --- Fixed position ---------------------------------------------------------------------------

static void test_fixed_position(void)
{
    fixed_position_t p;
    const char *error = NULL;

    // A trailing zero that used to move the latitude by a factor of ten
    CHECK(fixed_position_parse("40.123456", "-80.1234567", "300", &p, &error));
    CHECK(p.latitude_e7 == 401234560);
    CHECK(p.latitude_hp == 0);
    CHECK(p.longitude_e7 == -801234567);
    CHECK(p.height_cm == 30000);

    CHECK(fixed_position_parse("40.123456789", "-80.123456789", "300.2567", &p, &error));
    CHECK(p.latitude_e7 == 401234567);
    CHECK(p.latitude_hp == 89);
    CHECK(p.longitude_e7 == -801234567);
    CHECK(p.longitude_hp == -89);
    CHECK(p.height_cm == 30025);
    CHECK(p.height_hp == 67);

    // More digits than the receiver holds are rounded
    CHECK(fixed_position_parse("1.0000000019", "1", "1.00005", &p, &error));
    CHECK(p.latitude_e7 == 10000000);
    CHECK(p.latitude_hp == 2);
    CHECK(p.height_hp == 1);

    CHECK(fixed_position_parse("-0.5", "10", "-12.5", &p, &error));
    CHECK(p.latitude_e7 == -5000000);
    CHECK(p.height_cm == -1250);

    CHECK(fixed_position_parse_combined("-33.8688:151.2093:58.5", &p, &error));
    CHECK(p.latitude_e7 == -338688000);
    CHECK(p.height_cm == 5850);

    const char *bad[][3] = {
        { "91", "0", "0" }, { "-91", "0", "0" }, { "0", "181", "0" }, { "10", "10", "10000" }, { "0", "0", "100" },
        { "abc", "10", "10" }, { "10", "", "10" }, { "10,5", "10", "10" }, { "1e1", "10", "10" }, { "1.", "10", "10" },
        { "--1", "10", "10" }, { ".5", "10", "10" }, { "1234567890", "10", "10" },
    };
    for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); i++) {
        CHECK(!fixed_position_parse(bad[i][0], bad[i][1], bad[i][2], &p, &error));
    }
    CHECK(!fixed_position_parse(NULL, "1", "1", &p, &error));

    CHECK(!fixed_position_parse_combined("1:2", &p, &error));
    CHECK(!fixed_position_parse_combined("1:2:3:4", &p, &error));
    CHECK(!fixed_position_parse_combined("", &p, &error));
}

// --- Stream ----------------------------------------------------------------------------------

static int ubx_count;
static uint8_t ubx_cls, ubx_id;
static uint16_t ubx_length;
static uint8_t ubx_first;
static int rtcm_count;
static uint16_t rtcm_length;

static void count_ubx(void *ctx, uint8_t cls, uint8_t id, const uint8_t *payload, uint16_t length)
{
    (void)ctx;
    ubx_count++;
    ubx_cls = cls;
    ubx_id = id;
    ubx_length = length;
    ubx_first = length ? payload[0] : 0;
}

static void count_rtcm(void *ctx, const uint8_t *frame, uint16_t length)
{
    (void)ctx;
    (void)frame;
    rtcm_count++;
    rtcm_length = length;
}

static size_t make_rtcm(uint8_t *out, uint16_t payload_length)
{
    out[0] = 0xD3;
    out[1] = (uint8_t)(payload_length >> 8);
    out[2] = (uint8_t)payload_length;
    memset(out + 3, 0x5A, payload_length);
    uint32_t crc = rtcm_crc24q(out, (size_t)payload_length + 3);
    out[payload_length + 3] = (uint8_t)(crc >> 16);
    out[payload_length + 4] = (uint8_t)(crc >> 8);
    out[payload_length + 5] = (uint8_t)crc;
    return (size_t)payload_length + 6;
}

static void reset_counts(gnss_stream_t *stream)
{
    gnss_stream_init(stream, count_ubx, count_rtcm, NULL);
    ubx_count = rtcm_count = 0;
}

static void test_stream(void)
{
    gnss_stream_t stream;
    uint8_t frame[RTCM_MAX_FRAME + 32];

    // The CRC of the published example vector for CRC-24Q
    const uint8_t vector[] = "123456789";
    CHECK(rtcm_crc24q(vector, 9) == 0xCDE703);

    // A frame built here parses back
    reset_counts(&stream);
    uint8_t payload[] = { 7, 8, 9 };
    size_t length = ubx_frame(frame, sizeof(frame), 0x06, 0x08, payload, 3);
    CHECK(length == 11);
    gnss_stream_feed(&stream, frame, length);
    CHECK(ubx_count == 1 && ubx_cls == 0x06 && ubx_id == 0x08 && ubx_length == 3 && ubx_first == 7);

    // The published checksum of a UBX-CFG-RATE poll
    length = ubx_frame(frame, sizeof(frame), 0x06, 0x08, NULL, 0);
    CHECK(frame[6] == 0x0E && frame[7] == 0x30);

    // A frame that does not fit is refused
    CHECK(ubx_frame(frame, 5, 0x06, 0x08, NULL, 0) == 0);

    // One byte at a time, with noise before and between
    reset_counts(&stream);
    uint8_t noise[] = { 0x00, 0xB5, 0x00, 0x62, 0xFF, 0xD3, 0xFF };
    gnss_stream_feed(&stream, noise, sizeof(noise));
    length = make_rtcm(frame, 100);
    for (size_t i = 0; i < length; i++) gnss_stream_feed(&stream, frame + i, 1);
    CHECK(rtcm_count == 1 && rtcm_length == 106);

    // The longest frame
    reset_counts(&stream);
    length = make_rtcm(frame, 1023);
    gnss_stream_feed(&stream, frame, length);
    CHECK(rtcm_count == 1 && rtcm_length == 1029);

    // Damage is never passed on, and the next frame still gets through
    reset_counts(&stream);
    length = make_rtcm(frame, 50);
    frame[10] ^= 0x01;
    gnss_stream_feed(&stream, frame, length);
    CHECK(rtcm_count == 0 && stream.rtcm_errors == 1);
    length = make_rtcm(frame, 50);
    gnss_stream_feed(&stream, frame, length);
    CHECK(rtcm_count == 1);

    reset_counts(&stream);
    length = ubx_frame(frame, sizeof(frame), 0x06, 0x08, payload, 3);
    frame[length - 1] ^= 0x01;
    gnss_stream_feed(&stream, frame, length);
    CHECK(ubx_count == 0 && stream.ubx_errors == 1);

    // A message too long to keep is stepped over and the stream stays in step
    reset_counts(&stream);
    uint8_t header[] = { 0xB5, 0x62, 0x0A, 0x04, 0x2C, 0x01 }; // 300 bytes
    gnss_stream_feed(&stream, header, sizeof(header));
    static uint8_t filler[302];
    gnss_stream_feed(&stream, filler, sizeof(filler));
    length = ubx_frame(frame, sizeof(frame), 0x01, 0x07, payload, 3);
    gnss_stream_feed(&stream, frame, length);
    CHECK(ubx_count == 1 && ubx_cls == 0x01);
}

// --- Caster protocol ---------------------------------------------------------------------------

static void test_caster_protocol(void)
{
    char request[128];
    caster_build_source_request(request, sizeof(request), "MOUNT", "secret");
    CHECK(strncmp(request, "SOURCE secret /MOUNT\r\n", 22) == 0);
    CHECK(strlen(request) >= 4 && strcmp(request + strlen(request) - 4, "\r\n\r\n") == 0);

    CHECK(caster_classify_reply("ICY 200 OK\r\n") == CASTER_REPLY_OK);
    CHECK(caster_classify_reply("HTTP/1.1 200 OK\r\n\r\n") == CASTER_REPLY_OK);
    CHECK(caster_classify_reply("SOURCETABLE 200 OK\r\n") == CASTER_REPLY_SOURCETABLE);
    CHECK(caster_classify_reply("HTTP/1.1 403 Forbidden\r\n\r\nYour IP is BANNED") == CASTER_REPLY_BANNED);
    CHECK(caster_classify_reply("ERROR - Bad Password\r\n") == CASTER_REPLY_REJECTED);
    CHECK(caster_classify_reply("HTTP/1.1 401 Unauthorized\r\n") == CASTER_REPLY_REJECTED);
    CHECK(caster_classify_reply("") == CASTER_REPLY_REJECTED);
}

// --- Status ------------------------------------------------------------------------------------

static void no_write(void *ctx, const uint8_t *data, size_t length) { (void)ctx; (void)data; (void)length; }
static void no_baud(void *ctx, uint32_t baud) { (void)ctx; (void)baud; }
static bool no_network(void *ctx) { (void)ctx; return false; }

static void test_not_configured(void)
{
    static base_station_t base;
    base_hal_t hal = { .serial_write = no_write, .serial_set_baud = no_baud, .network_ready = no_network };
    base_caster_settings_t settings = { .port = 2101 };
    base_mode_t mode = { .kind = BASE_MODE_SURVEY, .survey_accuracy_mm = 3000, .survey_seconds = 60 };

    base_init(&base, &hal, &settings, &mode);
    base_tick(&base, 1000);

    char json[1024];
    int length = base_status_json(&base, json, sizeof(json));
    CHECK(length > 0 && (size_t)length < sizeof(json));
    CHECK(strstr(json, "\"phase\":\"not_configured\"") != NULL);
    CHECK(strstr(json, "NTRIP_NOT_CONFIGURED") != NULL);

    // Text from a caster cannot break the JSON
    strcpy(base.caster.message, "bad \"quote\" \\ here");
    base_status_json(&base, json, sizeof(json));
    CHECK(strstr(json, "\"caster_message\":\"bad  quote    here\"") != NULL);
}

int main(void)
{
    test_fixed_position();
    test_stream();
    test_caster_protocol();
    test_not_configured();

    printf(failures ? "%d FAILED\n" : "all core tests passed\n", failures);
    return failures ? 1 : 0;
}
