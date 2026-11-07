#include "settings.h"

#include <string.h>

#include "esp_log.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char *TAG = "settings";
static const char *NAMESPACE = "base";

static void read_text(nvs_handle_t nvs, const char *key, char *out, size_t capacity)
{
    size_t size = capacity;
    if (nvs_get_str(nvs, key, out, &size) != ESP_OK) out[0] = '\0';
}

void settings_load(settings_t *settings)
{
    memset(settings, 0, sizeof(*settings));
    strcpy(settings->caster.host, "rtk2go.com");
    settings->caster.port = 2101;
    settings->mode.kind = BASE_MODE_SURVEY;
    settings->mode.survey_accuracy_mm = 3000;
    settings->mode.survey_seconds = 60;

    nvs_handle_t nvs;
    if (nvs_open(NAMESPACE, NVS_READONLY, &nvs) != ESP_OK) return;

    read_text(nvs, "wifi_ssid", settings->wifi_ssid, sizeof(settings->wifi_ssid));
    read_text(nvs, "wifi_pass", settings->wifi_password, sizeof(settings->wifi_password));
    read_text(nvs, "ui_pass", settings->ui_password, sizeof(settings->ui_password));

    char host[sizeof(settings->caster.host)] = "";
    read_text(nvs, "ntrip_host", host, sizeof(host));
    if (host[0]) strcpy(settings->caster.host, host);
    nvs_get_u16(nvs, "ntrip_port", &settings->caster.port);
    read_text(nvs, "ntrip_mount", settings->caster.mountpoint, sizeof(settings->caster.mountpoint));
    read_text(nvs, "ntrip_pass", settings->caster.password, sizeof(settings->caster.password));

    base_mode_t mode;
    size_t size = sizeof(mode);
    if (nvs_get_blob(nvs, "mode", &mode, &size) == ESP_OK && size == sizeof(mode)) settings->mode = mode;

    nvs_close(nvs);
}

bool settings_save(const settings_t *settings)
{
    nvs_handle_t nvs;
    if (nvs_open(NAMESPACE, NVS_READWRITE, &nvs) != ESP_OK) return false;

    bool ok = nvs_set_str(nvs, "wifi_ssid", settings->wifi_ssid) == ESP_OK
        && nvs_set_str(nvs, "wifi_pass", settings->wifi_password) == ESP_OK
        && nvs_set_str(nvs, "ui_pass", settings->ui_password) == ESP_OK
        && nvs_set_str(nvs, "ntrip_host", settings->caster.host) == ESP_OK
        && nvs_set_u16(nvs, "ntrip_port", settings->caster.port) == ESP_OK
        && nvs_set_str(nvs, "ntrip_mount", settings->caster.mountpoint) == ESP_OK
        && nvs_set_str(nvs, "ntrip_pass", settings->caster.password) == ESP_OK
        && nvs_commit(nvs) == ESP_OK;

    nvs_close(nvs);
    return ok;
}

void settings_save_mode(const base_mode_t *mode)
{
    nvs_handle_t nvs;
    if (nvs_open(NAMESPACE, NVS_READWRITE, &nvs) != ESP_OK) return;

    if (nvs_set_blob(nvs, "mode", mode, sizeof(*mode)) != ESP_OK || nvs_commit(nvs) != ESP_OK) {
        ESP_LOGE(TAG, "Could not save the mode, it will not survive a restart");
    }
    nvs_close(nvs);
}

bool settings_complete(const settings_t *settings)
{
    return settings->wifi_ssid[0] != '\0' && settings->ui_password[0] != '\0';
}

void settings_erase(void)
{
    nvs_handle_t nvs;
    if (nvs_open(NAMESPACE, NVS_READWRITE, &nvs) != ESP_OK) return;
    nvs_erase_all(nvs);
    nvs_commit(nvs);
    nvs_close(nvs);
}
