#include "caster.h"

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <stdio.h>
#include <string.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>

#ifndef MSG_NOSIGNAL
#define MSG_NOSIGNAL 0
#endif

#define HANDSHAKE_TIMEOUT_MS 15000
#define SEND_STALL_TIMEOUT_MS 2000

enum { ST_CLOSED, ST_CONNECTING, ST_AWAIT_REPLY, ST_STREAMING };

static bool contains_ignoring_case(const char *text, const char *word)
{
    size_t word_length = strlen(word);
    for (; *text; text++) {
        size_t i = 0;
        while (i < word_length && text[i] && tolower((unsigned char)text[i]) == tolower((unsigned char)word[i])) i++;
        if (i == word_length) return true;
    }
    return false;
}

int caster_build_source_request(char *out, size_t capacity, const char *mountpoint, const char *password)
{
    return snprintf(out, capacity, "SOURCE %s /%s\r\nSource-Agent: NTRIP NtripServerPOSIX/Revision: 9109\r\n\r\n", password, mountpoint);
}

caster_reply_t caster_classify_reply(const char *reply)
{
    if (contains_ignoring_case(reply, "SOURCETABLE 200 OK")) return CASTER_REPLY_SOURCETABLE;
    if (contains_ignoring_case(reply, "banned")) return CASTER_REPLY_BANNED;
    if (strncmp(reply, "ICY 200 OK", 10) == 0) return CASTER_REPLY_OK;
    if (strncmp(reply, "HTTP/1.", 7) == 0 && strstr(reply, " 200 ") != NULL) return CASTER_REPLY_OK;
    return CASTER_REPLY_REJECTED;
}

void caster_init(caster_t *caster)
{
    memset(caster, 0, sizeof(*caster));
    caster->fd = -1;
    caster->state = ST_CLOSED;
}

bool caster_is_open(const caster_t *caster)
{
    return caster->state != ST_CLOSED;
}

bool caster_is_streaming(const caster_t *caster)
{
    return caster->state == ST_STREAMING && !caster->lost;
}

void caster_close(caster_t *caster)
{
    if (caster->fd >= 0) {
        shutdown(caster->fd, SHUT_RDWR);
        close(caster->fd);
    }
    caster->fd = -1;
    caster->state = ST_CLOSED;
    caster->lost = false;
}

static void set_message(caster_t *caster, const char *text)
{
    snprintf(caster->message, sizeof(caster->message), "%s", text);
}

static void open_failed(caster_t *caster, const char *message)
{
    set_message(caster, message);
    caster->open_failed = true;
}

void caster_open(caster_t *caster, const char *host, uint16_t port, const char *mountpoint, const char *password, uint32_t now_ms)
{
    caster_close(caster);
    caster->reply = CASTER_REPLY_NONE;
    caster->message[0] = '\0';
    caster->reply_length = 0;
    caster->open_failed = false;
    caster->deadline_ms = now_ms + HANDSHAKE_TIMEOUT_MS;

    int length = caster_build_source_request(caster->request, sizeof(caster->request), mountpoint, password);
    if (length < 0 || (size_t)length >= sizeof(caster->request)) {
        open_failed(caster, "mountpoint or password too long");
        return;
    }
    caster->request_length = (size_t)length;

    char service[8];
    snprintf(service, sizeof(service), "%u", port);

    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    struct addrinfo *address = NULL;
    if (getaddrinfo(host, service, &hints, &address) != 0 || address == NULL) {
        open_failed(caster, "cannot resolve the caster name");
        return;
    }

    int fd = socket(address->ai_family, address->ai_socktype, address->ai_protocol);
    if (fd < 0) {
        freeaddrinfo(address);
        open_failed(caster, "cannot create a socket");
        return;
    }

    fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) | O_NONBLOCK);

    int result = connect(fd, address->ai_addr, address->ai_addrlen);
    int connect_errno = errno;
    freeaddrinfo(address);

    if (result != 0 && connect_errno != EINPROGRESS) {
        close(fd);
        open_failed(caster, "cannot connect to the caster");
        return;
    }

    caster->fd = fd;
    caster->state = ST_CONNECTING;
}

// Waits briefly for the socket. Returns >0 when ready, 0 on timeout, <0 on error.
static int wait_socket(int fd, bool for_write, int timeout_ms)
{
    fd_set set;
    FD_ZERO(&set);
    FD_SET(fd, &set);
    struct timeval timeout = { timeout_ms / 1000, (timeout_ms % 1000) * 1000 };
    return select(fd + 1, for_write ? NULL : &set, for_write ? &set : NULL, NULL, &timeout);
}

static caster_event_t fail(caster_t *caster, const char *message)
{
    if (message) set_message(caster, message);
    caster_close(caster);
    return CASTER_EVENT_FAILED;
}

static void keep_first_line(caster_t *caster)
{
    size_t length = strcspn(caster->reply_buffer, "\r\n");
    if (length >= sizeof(caster->message)) length = sizeof(caster->message) - 1;
    memcpy(caster->message, caster->reply_buffer, length);
    caster->message[length] = '\0';
}

caster_event_t caster_poll(caster_t *caster, uint32_t now_ms)
{
    switch (caster->state) {
    case ST_CLOSED:
        // A failure inside caster_open is reported once, here
        if (caster->open_failed) {
            caster->open_failed = false;
            caster->reply = CASTER_REPLY_REJECTED;
            return CASTER_EVENT_FAILED;
        }
        return CASTER_EVENT_NONE;

    case ST_CONNECTING: {
        int ready = wait_socket(caster->fd, true, 0);
        if (ready > 0) {
            int socket_error = 0;
            socklen_t size = sizeof(socket_error);
            getsockopt(caster->fd, SOL_SOCKET, SO_ERROR, &socket_error, &size);
            if (socket_error != 0) {
                caster->reply = CASTER_REPLY_REJECTED;
                return fail(caster, "cannot connect to the caster");
            }

            if (send(caster->fd, caster->request, caster->request_length, MSG_NOSIGNAL) != (ssize_t)caster->request_length) {
                caster->reply = CASTER_REPLY_REJECTED;
                return fail(caster, "cannot send the login to the caster");
            }

            // The login holds the password: it has no further use
            memset(caster->request, 0, sizeof(caster->request));
            caster->state = ST_AWAIT_REPLY;
        } else if ((int32_t)(now_ms - caster->deadline_ms) >= 0) {
            caster->reply = CASTER_REPLY_REJECTED;
            return fail(caster, "timed out connecting to the caster");
        }
        return CASTER_EVENT_NONE;
    }

    case ST_AWAIT_REPLY: {
        ssize_t received = recv(caster->fd, caster->reply_buffer + caster->reply_length,
                                sizeof(caster->reply_buffer) - 1 - caster->reply_length, MSG_DONTWAIT);
        if (received > 0) {
            caster->reply_length += (size_t)received;
            caster->reply_buffer[caster->reply_length] = '\0';

            if (strstr(caster->reply_buffer, "\r\n") != NULL || caster->reply_length >= sizeof(caster->reply_buffer) - 1) {
                keep_first_line(caster);
                caster->reply = caster_classify_reply(caster->reply_buffer);
                if (caster->reply == CASTER_REPLY_OK) {
                    caster->state = ST_STREAMING;
                    return CASTER_EVENT_CONNECTED;
                }
                return fail(caster, NULL);
            }
        } else if (received == 0 || (errno != EAGAIN && errno != EWOULDBLOCK)) {
            if (caster->reply_length > 0) {
                caster->reply_buffer[caster->reply_length] = '\0';
                keep_first_line(caster);
                caster->reply = caster_classify_reply(caster->reply_buffer);
                if (caster->reply == CASTER_REPLY_OK) caster->reply = CASTER_REPLY_REJECTED;
                return fail(caster, NULL);
            }
            caster->reply = CASTER_REPLY_REJECTED;
            return fail(caster, "the caster closed the connection without replying");
        }

        if ((int32_t)(now_ms - caster->deadline_ms) >= 0) {
            caster->reply = CASTER_REPLY_REJECTED;
            return fail(caster, "timed out waiting for the caster to reply");
        }
        return CASTER_EVENT_NONE;
    }

    case ST_STREAMING: {
        if (caster->lost) {
            caster_close(caster);
            return CASTER_EVENT_LOST;
        }

        // A source is not sent anything worth reading, this only finds out whether the caster hung up
        char discard[64];
        ssize_t received = recv(caster->fd, discard, sizeof(discard), MSG_DONTWAIT);
        if (received == 0 || (received < 0 && errno != EAGAIN && errno != EWOULDBLOCK)) {
            set_message(caster, "the caster closed the connection");
            caster_close(caster);
            return CASTER_EVENT_LOST;
        }
        return CASTER_EVENT_NONE;
    }

    default:
        return CASTER_EVENT_NONE;
    }
}

bool caster_send(caster_t *caster, const uint8_t *data, size_t length)
{
    if (!caster_is_streaming(caster)) return false;

    size_t sent = 0;
    int waited_ms = 0;
    while (sent < length) {
        ssize_t result = send(caster->fd, data + sent, length - sent, MSG_DONTWAIT | MSG_NOSIGNAL);
        if (result > 0) {
            sent += (size_t)result;
        } else if (result < 0 && (errno == EAGAIN || errno == EWOULDBLOCK) && waited_ms < SEND_STALL_TIMEOUT_MS) {
            wait_socket(caster->fd, true, 100);
            waited_ms += 100;
        } else {
            set_message(caster, "sending to the caster failed");
            caster->lost = true;
            return false;
        }
    }
    return true;
}
