#include "gnss_stream.h"

#include <string.h>

enum {
    ST_IDLE,
    ST_UBX_SYNC2,
    ST_UBX_HEADER,
    ST_UBX_PAYLOAD,
    ST_UBX_SKIP,
    ST_UBX_CK_A,
    ST_UBX_CK_B,
    ST_RTCM_HEADER,
    ST_RTCM_BODY,
};

void gnss_stream_init(gnss_stream_t *stream,
                      void (*on_ubx)(void *, uint8_t, uint8_t, const uint8_t *, uint16_t),
                      void (*on_rtcm)(void *, const uint8_t *, uint16_t),
                      void *ctx)
{
    memset(stream, 0, sizeof(*stream));
    stream->on_ubx = on_ubx;
    stream->on_rtcm = on_rtcm;
    stream->ctx = ctx;
}

void gnss_stream_reset(gnss_stream_t *stream)
{
    stream->state = ST_IDLE;
    stream->count = 0;
}

static void ubx_checksum_add(gnss_stream_t *s, uint8_t byte)
{
    s->ck_a = (uint8_t)(s->ck_a + byte);
    s->ck_b = (uint8_t)(s->ck_b + s->ck_a);
}

static void feed_byte(gnss_stream_t *s, uint8_t b)
{
    switch (s->state) {
    case ST_IDLE:
        if (b == 0xB5) {
            s->state = ST_UBX_SYNC2;
        } else if (b == 0xD3) {
            s->buffer[0] = b;
            s->count = 1;
            s->state = ST_RTCM_HEADER;
        }
        break;

    case ST_UBX_SYNC2:
        if (b == 0x62) {
            s->count = 0;
            s->ck_a = s->ck_b = 0;
            s->state = ST_UBX_HEADER;
        } else {
            s->state = (b == 0xB5) ? ST_UBX_SYNC2 : ST_IDLE;
        }
        break;

    case ST_UBX_HEADER:
        ubx_checksum_add(s, b);
        s->buffer[s->count++] = b;
        if (s->count == 4) {
            s->cls = s->buffer[0];
            s->id = s->buffer[1];
            s->expected = (uint16_t)(s->buffer[2] | (s->buffer[3] << 8));
            s->count = 0;
            if (s->expected == 0) {
                s->state = ST_UBX_CK_A;
            } else {
                // Messages too long to keep are not ones this firmware reads: step over them
                s->state = (s->expected <= UBX_MAX_PAYLOAD) ? ST_UBX_PAYLOAD : ST_UBX_SKIP;
            }
        }
        break;

    case ST_UBX_PAYLOAD:
        ubx_checksum_add(s, b);
        s->buffer[s->count++] = b;
        if (s->count == s->expected) s->state = ST_UBX_CK_A;
        break;

    case ST_UBX_SKIP:
        ubx_checksum_add(s, b);
        if (--s->expected == 0) {
            s->state = ST_UBX_CK_A;
            s->cls = 0xFF; // Nothing to deliver
        }
        break;

    case ST_UBX_CK_A:
        if (b != s->ck_a) {
            s->ubx_errors++;
            s->state = ST_IDLE;
        } else {
            s->state = ST_UBX_CK_B;
        }
        break;

    case ST_UBX_CK_B:
        if (b != s->ck_b) {
            s->ubx_errors++;
        } else if (s->cls != 0xFF) {
            s->on_ubx(s->ctx, s->cls, s->id, s->buffer, s->count);
        }
        s->state = ST_IDLE;
        break;

    case ST_RTCM_HEADER:
        s->buffer[s->count++] = b;
        if (s->count == 2 && (b & 0xFC) != 0) {
            // The six reserved bits are always zero, so this 0xD3 was not the start of a frame
            s->state = ST_IDLE;
            s->count = 0;
        } else if (s->count == 3) {
            s->expected = (uint16_t)((((s->buffer[1] & 0x03) << 8) | s->buffer[2]) + 6);
            s->state = ST_RTCM_BODY;
        }
        break;

    case ST_RTCM_BODY:
        s->buffer[s->count++] = b;
        if (s->count == s->expected) {
            uint32_t received = ((uint32_t)s->buffer[s->count - 3] << 16) |
                                ((uint32_t)s->buffer[s->count - 2] << 8) |
                                s->buffer[s->count - 1];
            if (rtcm_crc24q(s->buffer, (size_t)(s->count - 3)) == received) {
                s->on_rtcm(s->ctx, s->buffer, s->count);
            } else {
                s->rtcm_errors++;
            }
            s->state = ST_IDLE;
            s->count = 0;
        }
        break;

    default:
        s->state = ST_IDLE;
        break;
    }
}

void gnss_stream_feed(gnss_stream_t *stream, const uint8_t *data, size_t length)
{
    for (size_t i = 0; i < length; i++) {
        feed_byte(stream, data[i]);
    }
}

size_t ubx_frame(uint8_t *out, size_t capacity, uint8_t cls, uint8_t id, const uint8_t *payload, uint16_t length)
{
    size_t total = (size_t)length + UBX_OVERHEAD;
    if (total > capacity) return 0;

    out[0] = 0xB5;
    out[1] = 0x62;
    out[2] = cls;
    out[3] = id;
    out[4] = (uint8_t)(length & 0xFF);
    out[5] = (uint8_t)(length >> 8);
    if (length > 0) memcpy(out + 6, payload, length);

    uint8_t ck_a = 0, ck_b = 0;
    for (size_t i = 2; i < (size_t)length + 6; i++) {
        ck_a = (uint8_t)(ck_a + out[i]);
        ck_b = (uint8_t)(ck_b + ck_a);
    }

    out[length + 6] = ck_a;
    out[length + 7] = ck_b;
    return total;
}

uint32_t rtcm_crc24q(const uint8_t *data, size_t length)
{
    uint32_t crc = 0;
    for (size_t i = 0; i < length; i++) {
        crc ^= (uint32_t)data[i] << 16;
        for (int bit = 0; bit < 8; bit++) {
            crc <<= 1;
            if (crc & 0x1000000) crc ^= 0x1864CFB;
        }
    }
    return crc & 0xFFFFFF;
}
