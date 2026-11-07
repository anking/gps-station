#include "web.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_app_desc.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "mbedtls/base64.h"
#include "net.h"

extern const char index_html_start[] asm("_binary_index_html_start");
extern const char index_html_end[] asm("_binary_index_html_end");

#define MAX_FORM_LENGTH 768
#define MIN_UI_PASSWORD_LENGTH 8
#define OTA_CHUNK_SIZE 2048

static const char *TAG = "web";

static base_station_t *base;
static SemaphoreHandle_t lock;
static settings_t settings;
static bool settings_were_complete;

// --- Access ---------------------------------------------------------------------------------

static bool equal_in_constant_time(const char *a, const char *b)
{
    size_t length_a = strlen(a), length_b = strlen(b);
    unsigned char difference = (unsigned char)(length_a != length_b);
    for (size_t i = 0; i < length_a; i++) {
        difference |= (unsigned char)(a[i] ^ b[length_b ? i % length_b : 0]);
    }
    return difference == 0;
}

// Until the UI has a password the device is only reachable on its own setup network.
static bool authorized(httpd_req_t *req)
{
    if (!settings_were_complete) return true;

    char header[192];
    if (httpd_req_get_hdr_value_str(req, "Authorization", header, sizeof(header)) == ESP_OK && strncmp(header, "Basic ", 6) == 0) {
        unsigned char decoded[140];
        size_t length = 0;
        if (mbedtls_base64_decode(decoded, sizeof(decoded) - 1, &length, (const unsigned char *)header + 6, strlen(header + 6)) == 0) {
            decoded[length] = '\0';
            const char *colon = strchr((const char *)decoded, ':');
            if (colon != NULL && equal_in_constant_time(colon + 1, settings.ui_password)) return true;
        }
    }

    httpd_resp_set_status(req, "401 Unauthorized");
    httpd_resp_set_hdr(req, "WWW-Authenticate", "Basic realm=\"GPS Base\", charset=\"UTF-8\"");
    httpd_resp_sendstr(req, "Password required");
    return false;
}

// A page from another site cannot add this header without the browser asking first, which this server never allows.
static bool from_our_page(httpd_req_t *req)
{
    if (httpd_req_get_hdr_value_len(req, "X-Requested-With") > 0) return true;

    httpd_resp_set_status(req, "403 Forbidden");
    httpd_resp_sendstr(req, "Forbidden");
    return false;
}

// --- Forms ----------------------------------------------------------------------------------

static void url_decode(char *text)
{
    char *out = text;
    for (char *in = text; *in; in++) {
        if (*in == '+') {
            *out++ = ' ';
        } else if (*in == '%' && isxdigit((unsigned char)in[1]) && isxdigit((unsigned char)in[2])) {
            char hex[3] = { in[1], in[2], '\0' };
            *out++ = (char)strtol(hex, NULL, 16);
            in += 2;
        } else {
            *out++ = *in;
        }
    }
    *out = '\0';
}

static bool read_form(httpd_req_t *req, char *body, size_t capacity)
{
    if (req->content_len == 0 || req->content_len >= capacity) return false;

    size_t received = 0;
    while (received < req->content_len) {
        int count = httpd_req_recv(req, body + received, req->content_len - received);
        if (count <= 0) return false;
        received += (size_t)count;
    }
    body[received] = '\0';
    return true;
}

static bool form_value(const char *body, const char *key, char *out, size_t capacity)
{
    if (httpd_query_key_value(body, key, out, capacity) != ESP_OK) {
        out[0] = '\0';
        return false;
    }
    url_decode(out);
    return true;
}

static bool set_text(char *out, size_t capacity, const char *value)
{
    size_t length = strlen(value);
    if (length >= capacity) return false;
    memcpy(out, value, length + 1);
    return true;
}

static esp_err_t reply(httpd_req_t *req, const char *status, const char *message)
{
    httpd_resp_set_status(req, status);
    httpd_resp_set_type(req, "application/json");
    char json[200];
    snprintf(json, sizeof(json), "{\"message\":\"%s\"}", message);
    return httpd_resp_sendstr(req, json);
}

// --- Handlers --------------------------------------------------------------------------------

static esp_err_t get_index(httpd_req_t *req)
{
    if (!authorized(req)) return ESP_OK;

    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, index_html_start, index_html_end - index_html_start - 1);
}

static esp_err_t get_status(httpd_req_t *req)
{
    if (!authorized(req)) return ESP_OK;

    static char json[1400];
    xSemaphoreTake(lock, portMAX_DELAY);
    int length = base_status_json(base, json, sizeof(json) - 200);
    xSemaphoreGive(lock);

    if (length <= 0 || length >= (int)sizeof(json) - 200) return httpd_resp_send_500(req);

    // Add what only this layer knows, before the closing brace
    char address[16];
    net_address(address, sizeof(address));
    snprintf(json + length - 1, sizeof(json) - (size_t)length + 1,
             ",\"setup_needed\":%s,\"setup_ssid\":\"%s\",\"address\":\"%s\",\"rssi\":%d,\"uptime_s\":%lld,\"version\":\"%s\"}",
             settings_were_complete ? "false" : "true", net_setup_ssid(), address, net_rssi(),
             esp_timer_get_time() / 1000000, esp_app_get_description()->version);

    httpd_resp_set_type(req, "application/json");
    return httpd_resp_sendstr(req, json);
}

static esp_err_t get_settings(httpd_req_t *req)
{
    if (!authorized(req)) return ESP_OK;

    // Passwords are write-only
    char json[300];
    snprintf(json, sizeof(json),
             "{\"wifi_ssid\":\"%s\",\"ntrip_host\":\"%s\",\"ntrip_port\":%u,\"ntrip_mount\":\"%s\",\"has_password\":%s}",
             settings.wifi_ssid, settings.caster.host, settings.caster.port, settings.caster.mountpoint,
             settings.ui_password[0] ? "true" : "false");
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_sendstr(req, json);
}

static esp_err_t post_mode(httpd_req_t *req)
{
    if (!authorized(req) || !from_our_page(req)) return ESP_OK;

    char body[MAX_FORM_LENGTH];
    if (!read_form(req, body, sizeof(body))) return reply(req, "400 Bad Request", "Bad request");

    char mode[12], a[32], b[32], c[32];
    form_value(body, "mode", mode, sizeof(mode));

    if (strcmp(mode, "survey") == 0) {
        form_value(body, "accuracy", a, sizeof(a));
        form_value(body, "time", b, sizeof(b));
        double accuracy_m = atof(a);
        int seconds = atoi(b);
        if (accuracy_m <= 0 || accuracy_m > 100 || seconds <= 0 || seconds > 86400) {
            return reply(req, "400 Bad Request", "Accuracy must be above 0 m and the time 1 to 86400 s");
        }

        xSemaphoreTake(lock, portMAX_DELAY);
        base_set_survey(base, (uint32_t)(accuracy_m * 1000.0), (uint32_t)seconds);
        xSemaphoreGive(lock);
        return reply(req, "200 OK", "Survey started");
    }

    if (strcmp(mode, "fixed") == 0) {
        form_value(body, "lat", a, sizeof(a));
        form_value(body, "lon", b, sizeof(b));
        form_value(body, "height", c, sizeof(c));

        const char *error = NULL;
        xSemaphoreTake(lock, portMAX_DELAY);
        bool accepted = base_set_fixed(base, a, b, c, &error);
        xSemaphoreGive(lock);
        return accepted ? reply(req, "200 OK", "Fixed position set") : reply(req, "400 Bad Request", error);
    }

    return reply(req, "400 Bad Request", "Unknown mode");
}

static void restart_soon(void *arg)
{
    (void)arg;
    vTaskDelay(pdMS_TO_TICKS(500));
    esp_restart();
}

static void schedule_restart(void)
{
    xTaskCreate(restart_soon, "restart", 2048, NULL, 5, NULL);
}

static esp_err_t post_settings(httpd_req_t *req)
{
    if (!authorized(req) || !from_our_page(req)) return ESP_OK;

    char body[MAX_FORM_LENGTH];
    if (!read_form(req, body, sizeof(body))) return reply(req, "400 Bad Request", "Bad request");

    settings_t updated = settings;
    char text[80];
    bool fits = true;

    if (form_value(body, "wifi_ssid", text, sizeof(text))) fits &= set_text(updated.wifi_ssid, sizeof(updated.wifi_ssid), text);
    if (form_value(body, "ntrip_host", text, sizeof(text)) && text[0]) fits &= set_text(updated.caster.host, sizeof(updated.caster.host), text);
    if (form_value(body, "ntrip_mount", text, sizeof(text))) fits &= set_text(updated.caster.mountpoint, sizeof(updated.caster.mountpoint), text);
    if (form_value(body, "ntrip_port", text, sizeof(text)) && text[0]) updated.caster.port = (uint16_t)atoi(text);

    // A blank password field means "keep the current one"
    if (form_value(body, "wifi_password", text, sizeof(text)) && text[0]) fits &= set_text(updated.wifi_password, sizeof(updated.wifi_password), text);
    if (form_value(body, "ntrip_password", text, sizeof(text)) && text[0]) fits &= set_text(updated.caster.password, sizeof(updated.caster.password), text);
    if (form_value(body, "ui_password", text, sizeof(text)) && text[0]) {
        if (strlen(text) < MIN_UI_PASSWORD_LENGTH) return reply(req, "400 Bad Request", "The UI password needs at least 8 characters");
        fits &= set_text(updated.ui_password, sizeof(updated.ui_password), text);
    }

    // A value cut short would fail later in a confusing way, such as a WiFi password that never works
    if (!fits) return reply(req, "400 Bad Request", "One of the values is too long");

    if (updated.wifi_ssid[0] == '\0') return reply(req, "400 Bad Request", "The WiFi network name is required");
    if (updated.ui_password[0] == '\0') return reply(req, "400 Bad Request", "A UI password is required before this goes on your network");
    if (updated.caster.port == 0) return reply(req, "400 Bad Request", "The caster port is not valid");

    if (!settings_save(&updated)) return reply(req, "500 Internal Server Error", "Could not save the settings");

    esp_err_t result = reply(req, "200 OK", "Saved. Restarting.");
    schedule_restart();
    return result;
}

static esp_err_t post_restart(httpd_req_t *req)
{
    if (!authorized(req) || !from_our_page(req)) return ESP_OK;

    esp_err_t result = reply(req, "200 OK", "Restarting.");
    schedule_restart();
    return result;
}

static esp_err_t post_firmware(httpd_req_t *req)
{
    if (!authorized(req) || !from_our_page(req)) return ESP_OK;

    const esp_partition_t *partition = esp_ota_get_next_update_partition(NULL);
    esp_ota_handle_t handle;
    if (partition == NULL || esp_ota_begin(partition, OTA_SIZE_UNKNOWN, &handle) != ESP_OK) {
        return reply(req, "500 Internal Server Error", "Could not start the update");
    }

    char *chunk = malloc(OTA_CHUNK_SIZE);
    if (chunk == NULL) {
        esp_ota_abort(handle);
        return reply(req, "500 Internal Server Error", "Out of memory");
    }

    size_t remaining = req->content_len;
    bool ok = remaining > 0;
    while (ok && remaining > 0) {
        int count = httpd_req_recv(req, chunk, remaining < OTA_CHUNK_SIZE ? remaining : OTA_CHUNK_SIZE);
        if (count == HTTPD_SOCK_ERR_TIMEOUT) continue;
        ok = count > 0 && esp_ota_write(handle, chunk, (size_t)count) == ESP_OK;
        if (ok) remaining -= (size_t)count;
    }
    free(chunk);

    if (!ok) {
        esp_ota_abort(handle);
        return reply(req, "400 Bad Request", "The upload failed");
    }

    // esp_ota_end checks the image, so a wrong file is refused here
    if (esp_ota_end(handle) != ESP_OK || esp_ota_set_boot_partition(partition) != ESP_OK) {
        return reply(req, "400 Bad Request", "That is not a valid firmware image");
    }

    ESP_LOGI(TAG, "Firmware updated, restarting");
    esp_err_t result = reply(req, "200 OK", "Updated. Restarting.");
    schedule_restart();
    return result;
}

void web_start(base_station_t *base_station, SemaphoreHandle_t base_lock, const settings_t *current)
{
    base = base_station;
    lock = base_lock;
    settings = *current;
    settings_were_complete = settings_complete(current);

    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.stack_size = 8192;
    config.max_uri_handlers = 8;
    config.lru_purge_enable = true;

    httpd_handle_t server = NULL;
    ESP_ERROR_CHECK(httpd_start(&server, &config));

    const httpd_uri_t routes[] = {
        { .uri = "/", .method = HTTP_GET, .handler = get_index },
        { .uri = "/api/status", .method = HTTP_GET, .handler = get_status },
        { .uri = "/api/settings", .method = HTTP_GET, .handler = get_settings },
        { .uri = "/api/mode", .method = HTTP_POST, .handler = post_mode },
        { .uri = "/api/settings", .method = HTTP_POST, .handler = post_settings },
        { .uri = "/api/restart", .method = HTTP_POST, .handler = post_restart },
        { .uri = "/api/firmware", .method = HTTP_POST, .handler = post_firmware },
    };
    for (size_t i = 0; i < sizeof(routes) / sizeof(routes[0]); i++) {
        ESP_ERROR_CHECK(httpd_register_uri_handler(server, &routes[i]));
    }
}
