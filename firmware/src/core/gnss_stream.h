// Splits the byte stream from a u-blox receiver into checked UBX and RTCM3 frames.
#pragma once

#include <stddef.h>
#include <stdint.h>

#define UBX_CLASS_NAV 0x01
#define UBX_CLASS_ACK 0x05
#define UBX_CLASS_CFG 0x06

#define UBX_ACK_NAK 0x00
#define UBX_ACK_ACK 0x01

#define UBX_CFG_PRT 0x00
#define UBX_CFG_MSG 0x01
#define UBX_CFG_RATE 0x08
#define UBX_CFG_TMODE3 0x71

#define UBX_NAV_PVT 0x07
#define UBX_NAV_HPPOSLLH 0x14
#define UBX_NAV_SVIN 0x3B

#define UBX_MAX_PAYLOAD 256
#define UBX_OVERHEAD 8
#define RTCM_MAX_FRAME (3 + 1023 + 3)

typedef struct {
    void (*on_ubx)(void *ctx, uint8_t cls, uint8_t id, const uint8_t *payload, uint16_t length);
    void (*on_rtcm)(void *ctx, const uint8_t *frame, uint16_t length);
    void *ctx;

    int state;
    uint8_t buffer[RTCM_MAX_FRAME];
    uint16_t count;
    uint16_t expected;
    uint8_t cls;
    uint8_t id;
    uint8_t ck_a;
    uint8_t ck_b;

    uint32_t ubx_errors;
    uint32_t rtcm_errors;
} gnss_stream_t;

void gnss_stream_init(gnss_stream_t *stream,
                      void (*on_ubx)(void *, uint8_t, uint8_t, const uint8_t *, uint16_t),
                      void (*on_rtcm)(void *, const uint8_t *, uint16_t),
                      void *ctx);

void gnss_stream_reset(gnss_stream_t *stream);

void gnss_stream_feed(gnss_stream_t *stream, const uint8_t *data, size_t length);

// Writes a complete UBX frame. Returns its length, or 0 if it does not fit.
size_t ubx_frame(uint8_t *out, size_t capacity, uint8_t cls, uint8_t id, const uint8_t *payload, uint16_t length);

uint32_t rtcm_crc24q(const uint8_t *data, size_t length);
