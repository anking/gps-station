// One NTRIP Rev1 source connection to a caster, on non-blocking BSD sockets (lwIP on the ESP32, the OS on a PC).
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum {
    CASTER_REPLY_NONE,
    CASTER_REPLY_OK,
    CASTER_REPLY_SOURCETABLE,
    CASTER_REPLY_BANNED,
    CASTER_REPLY_REJECTED,
} caster_reply_t;

typedef enum {
    CASTER_EVENT_NONE,
    CASTER_EVENT_CONNECTED,
    CASTER_EVENT_FAILED,    // Never got as far as streaming. See caster_t.reply and .message.
    CASTER_EVENT_LOST,      // Was streaming and the connection went away
} caster_event_t;

typedef struct {
    int fd;
    int state;
    uint32_t deadline_ms;
    char request[192];
    size_t request_length;
    char reply_buffer[192];
    size_t reply_length;
    caster_reply_t reply;
    char message[96];       // First line of the caster's reply, or what went wrong
    bool lost;
    bool open_failed;
} caster_t;

// Exposed for tests
int caster_build_source_request(char *out, size_t capacity, const char *mountpoint, const char *password);
caster_reply_t caster_classify_reply(const char *reply);

void caster_init(caster_t *caster);

// Starts connecting. Name resolution blocks; everything after it is polled.
void caster_open(caster_t *caster, const char *host, uint16_t port, const char *mountpoint, const char *password, uint32_t now_ms);

caster_event_t caster_poll(caster_t *caster, uint32_t now_ms);

bool caster_is_open(const caster_t *caster);
bool caster_is_streaming(const caster_t *caster);

// Sends a whole frame or drops the connection: a part of a frame would corrupt the stream for every rover.
bool caster_send(caster_t *caster, const uint8_t *data, size_t length);

void caster_close(caster_t *caster);
