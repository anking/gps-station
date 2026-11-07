#include "ota.h"

#include <inttypes.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "esp_app_desc.h"
#include "esp_http_client.h"
#include "esp_https_ota.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_ota_ops.h"
#include "esp_random.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "net.h"
#include "sdkconfig.h"
#include "update_policy.h"

// Plain HTTP on purpose, for the reason SolarControlV2's ota_update.c gives: on an ESP32 mbedTLS runs out of heap on
// the TLS records of a 1+ MB download. The image is checked before it boots, which catches a bad download. It does not
// prove who built it. nginx exposes only this one path on port 80.
#ifndef FIRMWARE_URL
#define FIRMWARE_URL "http://rider.solvitcorp.com/api/firmware/base/firmware.bin"
#endif

#define CHECK_INTERVAL_MS (10 * 60 * 1000)
#define BOOT_RETRY_MS 5000
#define HTTP_TIMEOUT_MS 30000
#define RESTART_DELAY_MS 3000
#define TASK_STACK 8192
#define TASK_PRIORITY 5

// The server's answer when the active release was built for another chip, which the device could not run
#define HTTP_WRONG_CHIP 412

static const char *TAG = "ota";

static TaskHandle_t task;
static bool auto_updates;
static volatile bool checking;
static volatile int requested_id;

static portMUX_TYPE status_lock = portMUX_INITIALIZER_UNLOCKED;
static char status_text[80] = "Not checked yet";

static void set_status(const char *format, ...)
{
    char text[sizeof(status_text)];
    va_list args;
    va_start(args, format);
    vsnprintf(text, sizeof(text), format, args);
    va_end(args);

    // Telemetry and the web UI put this inside a JSON string, and a version comes from the image
    for (char *c = text; *c; c++) {
        if (*c == '"' || *c == '\\' || (unsigned char)*c < 0x20) *c = '_';
    }

    ESP_LOGI(TAG, "%s", text);

    portENTER_CRITICAL(&status_lock);
    memcpy(status_text, text, sizeof(status_text));
    portEXIT_CRITICAL(&status_lock);
}

void ota_status(char *out, size_t capacity)
{
    char text[sizeof(status_text)];

    portENTER_CRITICAL(&status_lock);
    memcpy(text, status_text, sizeof(text));
    portEXIT_CRITICAL(&status_lock);

    snprintf(out, capacity, "%s", text);
}

static void build_url(char *out, size_t capacity, const char *version, int firmware_id)
{
    uint8_t mac[6] = { 0 };
    esp_read_mac(mac, ESP_MAC_WIFI_STA);

    int used = snprintf(out, capacity, "%s?id=%02x-%02x-%02x-%02x-%02x-%02x&ver=%s&chip=%s&ts=%08" PRIx32,
                        FIRMWARE_URL, mac[0], mac[1], mac[2], mac[3], mac[4], mac[5],
                        version, CONFIG_IDF_TARGET, esp_random());

    if (firmware_id > 0 && used > 0 && (size_t)used < capacity) {
        snprintf(out + used, capacity - (size_t)used, "&fwid=%d", firmware_id);
    }
}

static esp_err_t head_status(const char *url, int *status)
{
    esp_http_client_config_t config = {
        .url = url,
        .timeout_ms = HTTP_TIMEOUT_MS,
        .method = HTTP_METHOD_HEAD,
    };

    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (client == NULL) return ESP_FAIL;

    esp_err_t result = esp_http_client_perform(client);
    if (result == ESP_OK) *status = esp_http_client_get_status_code(client);

    esp_http_client_cleanup(client);
    return result;
}

// The version this device already tried and rolled back from, or an empty string
static void failed_version(char *out, size_t capacity)
{
    out[0] = '\0';

    const esp_partition_t *invalid = esp_ota_get_last_invalid_partition();
    esp_app_desc_t description;
    if (invalid != NULL && esp_ota_get_partition_description(invalid, &description) == ESP_OK) {
        snprintf(out, capacity, "%s", description.version);
    }
}

// A new firmware has to prove itself before it can be replaced: esp_ota_begin refuses until it is marked good
static bool firmware_confirmed(void)
{
    esp_ota_img_states_t state;
    esp_err_t result = esp_ota_get_state_partition(esp_ota_get_running_partition(), &state);
    return result != ESP_OK || state != ESP_OTA_IMG_PENDING_VERIFY;
}

static void check_and_install(int firmware_id)
{
    if (!net_has_internet_path()) {
        set_status("Waiting for the network");
        return;
    }

    const esp_app_desc_t *running = esp_app_get_description();

    char url[220];
    build_url(url, sizeof(url), running->version, firmware_id);

    // Asking first costs a few bytes every 10 minutes, where a download would cost a megabyte
    int status = -1;
    if (head_status(url, &status) != ESP_OK) {
        set_status("Could not reach the update server");
        return;
    }

    switch (status) {
    case 200:
        break;
    case 304:
        set_status("Up to date");
        return;
    case 404:
        set_status("Nothing to install");
        return;
    case 409:
        set_status("Newer than the active release");
        return;
    case HTTP_WRONG_CHIP:
        set_status("The active release is built for a different chip");
        return;
    default:
        set_status("The update server answered %d", status);
        return;
    }

    esp_http_client_config_t http = {
        .url = url,
        .timeout_ms = HTTP_TIMEOUT_MS,
        .keep_alive_enable = true,
    };
    esp_https_ota_config_t config = { .http_config = &http };

    esp_https_ota_handle_t handle = NULL;
    esp_err_t result = esp_https_ota_begin(&config, &handle);
    if (result != ESP_OK) {
        set_status("The download did not start: %s", esp_err_to_name(result));
        return;
    }

    // This reads only the start of the image, so nothing has been written yet
    esp_app_desc_t incoming;
    result = esp_https_ota_get_img_desc(handle, &incoming);
    if (result != ESP_OK) {
        esp_https_ota_abort(handle);
        set_status("The server sent something that is not firmware");
        return;
    }

    char failed[sizeof(incoming.version)];
    failed_version(failed, sizeof(failed));

    switch (update_decide(running->project_name, running->version, incoming.project_name, incoming.version, failed, firmware_id > 0)) {
    case UPDATE_INSTALL:
        break;
    case UPDATE_SKIP_SAME_VERSION:
        esp_https_ota_abort(handle);
        set_status("Up to date");
        return;
    case UPDATE_REFUSE_WRONG_PROJECT:
        esp_https_ota_abort(handle);
        set_status("Refused: that firmware is for %s", incoming.project_name);
        return;
    case UPDATE_REFUSE_FAILED_BEFORE:
        esp_https_ota_abort(handle);
        set_status("Not installing %s: it failed to start here", incoming.version);
        return;
    }

    set_status("Installing %s", incoming.version);

    do {
        result = esp_https_ota_perform(handle);
    } while (result == ESP_ERR_HTTPS_OTA_IN_PROGRESS);

    if (result != ESP_OK || !esp_https_ota_is_complete_data_received(handle)) {
        esp_https_ota_abort(handle);
        set_status("The download of %s failed", incoming.version);
        return;
    }

    // Checks the whole image and only then makes it the one to boot. It releases the handle either way.
    result = esp_https_ota_finish(handle);
    if (result != ESP_OK) {
        set_status("%s did not pass its check: %s", incoming.version, esp_err_to_name(result));
        return;
    }

    set_status("Restarting into %s", incoming.version);
    vTaskDelay(pdMS_TO_TICKS(RESTART_DELAY_MS));
    esp_restart();
}

static void ota_task(void *arg)
{
    (void)arg;

    if (!auto_updates) set_status("Automatic updates are off");

    while (!firmware_confirmed() || !net_has_internet_path()) {
        vTaskDelay(pdMS_TO_TICKS(BOOT_RETRY_MS));
    }

    bool due = auto_updates;
    for (;;) {
        if (due) {
            checking = true;
            int firmware_id = requested_id;
            requested_id = 0;
            check_and_install(firmware_id);
            checking = false;
        }

        // Asking for a check wakes this early
        bool asked = ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(CHECK_INTERVAL_MS)) > 0;
        due = asked || auto_updates;
    }
}

bool ota_request_check(int firmware_id)
{
    if (task == NULL || checking) return false;

    requested_id = firmware_id > 0 ? firmware_id : 0;
    xTaskNotifyGive(task);
    return true;
}

void ota_start(bool auto_update)
{
    auto_updates = auto_update;
    xTaskCreate(ota_task, "ota", TASK_STACK, NULL, TASK_PRIORITY, &task);
}
