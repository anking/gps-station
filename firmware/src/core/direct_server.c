#include "direct_server.h"

#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#ifndef MSG_NOSIGNAL
#define MSG_NOSIGNAL 0
#endif

#define LISTEN_RETRY_MS 5000u
#define REQUEST_TIMEOUT_MS 5000u

static const char STREAM_REPLY[] = "ICY 200 OK\r\n\r\n";
static const char REFUSED_REPLY[] = "HTTP/1.0 400 Bad Request\r\n\r\n";

bool direct_is_stream_request(const char *request)
{
    // "GET / " asks for a list of streams, which there is no need for with only the one
    return strncmp(request, "GET /", 5) == 0 && request[5] != '\0' && request[5] != ' ' && request[5] != '\r';
}

static void close_rover(direct_rover_t *rover)
{
    if (rover->fd >= 0) {
        shutdown(rover->fd, SHUT_RDWR);
        close(rover->fd);
    }
    rover->fd = -1;
    rover->streaming = false;
    rover->request_length = 0;
}

void direct_server_init(direct_server_t *server, uint16_t port)
{
    memset(server, 0, sizeof(*server));
    server->port = port;
    server->listen_fd = -1;
    for (int i = 0; i < DIRECT_MAX_ROVERS; i++) server->rovers[i].fd = -1;
}

static void open_listener(direct_server_t *server, uint32_t now_ms)
{
    server->next_listen_ms = now_ms + LISTEN_RETRY_MS;

    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return;

    int yes = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
    fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) | O_NONBLOCK);

    struct sockaddr_in address;
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_port = htons(server->port);
    address.sin_addr.s_addr = htonl(INADDR_ANY);

    if (bind(fd, (struct sockaddr *)&address, sizeof(address)) != 0 || listen(fd, DIRECT_MAX_ROVERS) != 0) {
        close(fd);
        return;
    }

    server->listen_fd = fd;
}

static direct_rover_t *place_for_a_rover(direct_server_t *server)
{
    direct_rover_t *oldest = &server->rovers[0];
    for (int i = 0; i < DIRECT_MAX_ROVERS; i++) {
        direct_rover_t *rover = &server->rovers[i];
        if (rover->fd < 0) return rover;
        if ((int32_t)(rover->opened_ms - oldest->opened_ms) < 0) oldest = rover;
    }

    // A rover that lost its WiFi never says goodbye, and must not keep out the same rover coming back
    close_rover(oldest);
    return oldest;
}

static void accept_rovers(direct_server_t *server, uint32_t now_ms)
{
    for (;;) {
        int fd = accept(server->listen_fd, NULL, NULL);
        if (fd < 0) {
            if (errno != EAGAIN && errno != EWOULDBLOCK) {
                close(server->listen_fd);
                server->listen_fd = -1;
                server->next_listen_ms = now_ms + LISTEN_RETRY_MS;
            }
            return;
        }

        fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) | O_NONBLOCK);

        // Each frame should leave as soon as it is complete
        int yes = 1;
        setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &yes, sizeof(yes));

        direct_rover_t *rover = place_for_a_rover(server);
        rover->fd = fd;
        rover->streaming = false;
        rover->opened_ms = now_ms;
        rover->request_length = 0;
    }
}

static bool hung_up(ssize_t received)
{
    return received == 0 || (received < 0 && errno != EAGAIN && errno != EWOULDBLOCK);
}

static void read_request(direct_rover_t *rover, uint32_t now_ms)
{
    ssize_t received = recv(rover->fd, rover->request + rover->request_length,
                            sizeof(rover->request) - 1 - rover->request_length, MSG_DONTWAIT);
    if (hung_up(received)) {
        close_rover(rover);
        return;
    }

    if (received > 0) {
        rover->request_length += (size_t)received;
        rover->request[rover->request_length] = '\0';

        if (strstr(rover->request, "\r\n\r\n") != NULL) {
            bool wanted = direct_is_stream_request(rover->request);
            const char *reply = wanted ? STREAM_REPLY : REFUSED_REPLY;
            send(rover->fd, reply, strlen(reply), MSG_DONTWAIT | MSG_NOSIGNAL);
            if (wanted) rover->streaming = true;
            else close_rover(rover);
            return;
        }

        if (rover->request_length >= sizeof(rover->request) - 1) {
            close_rover(rover);
            return;
        }
    }

    if (now_ms - rover->opened_ms >= REQUEST_TIMEOUT_MS) close_rover(rover);
}

void direct_server_poll(direct_server_t *server, uint32_t now_ms)
{
    if (server->port == 0) return;

    if (server->listen_fd < 0 && (int32_t)(now_ms - server->next_listen_ms) >= 0) open_listener(server, now_ms);
    if (server->listen_fd >= 0) accept_rovers(server, now_ms);

    for (int i = 0; i < DIRECT_MAX_ROVERS; i++) {
        direct_rover_t *rover = &server->rovers[i];
        if (rover->fd < 0) continue;

        if (!rover->streaming) {
            read_request(rover, now_ms);
            continue;
        }

        // A rover may send its position, which is of no use here. This finds out whether it hung up.
        char discard[64];
        if (hung_up(recv(rover->fd, discard, sizeof(discard), MSG_DONTWAIT))) close_rover(rover);
    }
}

void direct_server_send(direct_server_t *server, const uint8_t *frame, size_t length)
{
    for (int i = 0; i < DIRECT_MAX_ROVERS; i++) {
        direct_rover_t *rover = &server->rovers[i];
        if (rover->fd < 0 || !rover->streaming) continue;

        // Waiting here would hold up the GPS module and the caster, and corrections that have queued up are going stale.
        // Only part of a frame would corrupt the stream, so that rover goes too.
        if (send(rover->fd, frame, length, MSG_DONTWAIT | MSG_NOSIGNAL) != (ssize_t)length) close_rover(rover);
    }
}

int direct_server_rover_count(const direct_server_t *server)
{
    int count = 0;
    for (int i = 0; i < DIRECT_MAX_ROVERS; i++) {
        if (server->rovers[i].fd >= 0 && server->rovers[i].streaming) count++;
    }
    return count;
}
