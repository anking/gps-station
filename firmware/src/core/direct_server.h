// Serves the corrections straight to rovers on the same network, over the NTRIP protocol they already speak, so a rover
// needs neither the internet nor a public caster while it can reach the base. Non-blocking BSD sockets, like caster.c.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define DIRECT_MAX_ROVERS 2

typedef struct {
    int fd;
    bool streaming;
    uint32_t opened_ms;
    size_t request_length;
    char request[256];
} direct_rover_t;

typedef struct {
    uint16_t port;
    int listen_fd;
    uint32_t next_listen_ms;
    direct_rover_t rovers[DIRECT_MAX_ROVERS];
} direct_server_t;

// Exposed for tests. True for a request for a stream, with any name: "GET /base HTTP/1.0".
bool direct_is_stream_request(const char *request);

// Port 0 leaves it off.
void direct_server_init(direct_server_t *server, uint16_t port);

// Accepts rovers and answers them. Call often. It never waits for anything.
void direct_server_poll(direct_server_t *server, uint32_t now_ms);

// Sends a whole frame to every rover. One that cannot take it all right now is dropped, and connects again.
void direct_server_send(direct_server_t *server, const uint8_t *frame, size_t length);

int direct_server_rover_count(const direct_server_t *server);
