// Runs the base station core on a PC against a serial port or pseudo terminal, for testing without an ESP32.
//   base_host --serial /dev/pts/N --host H --port P --mount M --password PW [--direct-port P] [--survey ACCURACY_MM:SECONDS] [--fixed LAT:LON:HEIGHT]
// Prints the status as a JSON line twice a second. Reads commands from stdin:
//   SURVEY <accuracy_mm> <seconds>
//   FIXED <latitude> <longitude> <height>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#include "../src/core/base_station.h"

static int serial_fd = -1;

static void serial_write(void *ctx, const uint8_t *data, size_t length)
{
    (void)ctx;
    if (write(serial_fd, data, length) < 0) fprintf(stderr, "serial write failed: %s\n", strerror(errno));
}

static void serial_set_baud(void *ctx, uint32_t baud)
{
    (void)ctx;
    (void)baud; // A pseudo terminal has no speed
}

static bool network_ready(void *ctx)
{
    (void)ctx;
    return access("/tmp/base-network-down", F_OK) != 0;
}

static void mode_changed(void *ctx, const base_mode_t *mode)
{
    (void)ctx;
    fprintf(stderr, "saved mode %d\n", mode->kind);
}

static uint32_t now_ms(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint32_t)(t.tv_sec * 1000u + t.tv_nsec / 1000000u);
}

int main(int argc, char **argv)
{
    base_caster_settings_t settings = { .port = 2101 };
    base_mode_t mode = { .kind = BASE_MODE_SURVEY, .survey_accuracy_mm = 3000, .survey_seconds = 60 };
    const char *serial = NULL;
    uint16_t direct_port = 0;

    for (int i = 1; i + 1 < argc; i += 2) {
        const char *value = argv[i + 1];
        if (!strcmp(argv[i], "--serial")) serial = value;
        else if (!strcmp(argv[i], "--host")) snprintf(settings.host, sizeof(settings.host), "%s", value);
        else if (!strcmp(argv[i], "--port")) settings.port = (uint16_t)atoi(value);
        else if (!strcmp(argv[i], "--direct-port")) direct_port = (uint16_t)atoi(value);
        else if (!strcmp(argv[i], "--mount")) snprintf(settings.mountpoint, sizeof(settings.mountpoint), "%s", value);
        else if (!strcmp(argv[i], "--password")) snprintf(settings.password, sizeof(settings.password), "%s", value);
        else if (!strcmp(argv[i], "--survey")) sscanf(value, "%u:%u", &mode.survey_accuracy_mm, &mode.survey_seconds);
        else if (!strcmp(argv[i], "--fixed")) {
            const char *error = NULL;
            if (!fixed_position_parse_combined(value, &mode.fixed, &error)) {
                fprintf(stderr, "bad position: %s\n", error);
                return 2;
            }
            mode.kind = BASE_MODE_FIXED;
            snprintf(mode.fixed_text, sizeof(mode.fixed_text), "%s", value);
        }
    }

    signal(SIGPIPE, SIG_IGN);
    setvbuf(stdout, NULL, _IOLBF, 0);

    serial_fd = open(serial, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (serial_fd < 0) {
        fprintf(stderr, "cannot open %s: %s\n", serial, strerror(errno));
        return 1;
    }

    struct termios tio;
    tcgetattr(serial_fd, &tio);
    cfmakeraw(&tio);
    tcsetattr(serial_fd, TCSANOW, &tio);

    static base_station_t base;
    base_hal_t hal = {
        .serial_write = serial_write,
        .serial_set_baud = serial_set_baud,
        .network_ready = network_ready,
        .mode_changed = mode_changed,
    };
    base_init(&base, &hal, &settings, &mode, direct_port);

    fcntl(STDIN_FILENO, F_SETFL, fcntl(STDIN_FILENO, F_GETFL, 0) | O_NONBLOCK);

    uint32_t next_status = 0;
    char line[256];
    size_t line_used = 0;

    for (;;) {
        struct pollfd fds[2] = { { serial_fd, POLLIN, 0 }, { STDIN_FILENO, POLLIN, 0 } };
        poll(fds, 2, 10);

        if (fds[0].revents & POLLIN) {
            uint8_t buffer[1024];
            ssize_t count = read(serial_fd, buffer, sizeof(buffer));
            if (count > 0) base_on_serial(&base, buffer, (size_t)count);
        }

        if (fds[1].revents & POLLIN) {
            char c;
            while (read(STDIN_FILENO, &c, 1) == 1) {
                if (c != '\n' && line_used + 1 < sizeof(line)) {
                    line[line_used++] = c;
                    continue;
                }
                line[line_used] = '\0';
                line_used = 0;

                unsigned accuracy, seconds;
                char lat[32], lon[32], height[32];
                const char *error = NULL;
                if (sscanf(line, "SURVEY %u %u", &accuracy, &seconds) == 2) {
                    base_set_survey(&base, accuracy, seconds);
                } else if (sscanf(line, "FIXED %31s %31s %31s", lat, lon, height) == 3) {
                    if (!base_set_fixed(&base, lat, lon, height, &error)) fprintf(stderr, "refused: %s\n", error);
                }
            }
        }

        uint32_t now = now_ms();
        base_tick(&base, now);

        if ((int32_t)(now - next_status) >= 0) {
            char json[1024];
            base_status_json(&base, json, sizeof(json));
            puts(json);
            next_status = now + 500;
        }
    }
}
