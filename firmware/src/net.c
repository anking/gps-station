#include "net.h"

#include <stdio.h>
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/timers.h"

#define STATION_RETRY_MS 5000
#define SETUP_FALLBACK_MS (2 * 60 * 1000)

static const char *TAG = "net";

static esp_netif_t *station_netif;
static volatile bool have_address;
static volatile bool setup_network_active;
static bool station_configured;
static char setup_ssid[32];
static TimerHandle_t retry_timer;
static TimerHandle_t fallback_timer;

static void start_setup_network(void)
{
    if (setup_network_active) return;

    wifi_config_t config = { 0 };
    strcpy((char *)config.ap.ssid, setup_ssid);
    config.ap.ssid_len = (uint8_t)strlen(setup_ssid);
    strcpy((char *)config.ap.password, SETUP_AP_PASSWORD);
    config.ap.authmode = WIFI_AUTH_WPA2_PSK;
    config.ap.max_connection = 2;

    esp_wifi_set_mode(station_configured ? WIFI_MODE_APSTA : WIFI_MODE_AP);
    esp_wifi_set_config(WIFI_IF_AP, &config);
    setup_network_active = true;
    ESP_LOGW(TAG, "Setup network \"%s\" is up at http://192.168.4.1", setup_ssid);
}

static void retry_connect(TimerHandle_t timer)
{
    (void)timer;
    esp_wifi_connect();
}

static void fallback_to_setup(TimerHandle_t timer)
{
    (void)timer;
    // A wrong WiFi password, or a new router, must not lock the device away on a roof
    if (!have_address) start_setup_network();
}

static void on_wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    (void)arg;
    (void)data;
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        have_address = false;
        xTimerStart(retry_timer, 0);
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        have_address = true;
        ESP_LOGI(TAG, "Connected, UI at http://" IPSTR, IP2STR(&((ip_event_got_ip_t *)data)->ip_info.ip));
    }
}

void net_start(const settings_t *settings)
{
    uint8_t mac[6] = { 0 };
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(setup_ssid, sizeof(setup_ssid), "gps-base-%02X%02X", mac[4], mac[5]);

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    station_netif = esp_netif_create_default_wifi_sta();
    esp_netif_create_default_wifi_ap();
    esp_netif_set_hostname(station_netif, "gps-base");

    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    esp_wifi_set_storage(WIFI_STORAGE_RAM);

    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_wifi_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_wifi_event, NULL));

    retry_timer = xTimerCreate("wifi_retry", pdMS_TO_TICKS(STATION_RETRY_MS), pdFALSE, NULL, retry_connect);

    station_configured = settings->wifi_ssid[0] != '\0';

    if (station_configured) {
        wifi_config_t config = { 0 };
        // Both may use the whole field, with no terminator
        memcpy(config.sta.ssid, settings->wifi_ssid, strnlen(settings->wifi_ssid, sizeof(config.sta.ssid)));
        memcpy(config.sta.password, settings->wifi_password, strnlen(settings->wifi_password, sizeof(config.sta.password)));
        config.sta.threshold.authmode = settings->wifi_password[0] ? WIFI_AUTH_WPA2_PSK : WIFI_AUTH_OPEN;

        esp_wifi_set_mode(WIFI_MODE_STA);
        esp_wifi_set_config(WIFI_IF_STA, &config);

        fallback_timer = xTimerCreate("wifi_fallback", pdMS_TO_TICKS(SETUP_FALLBACK_MS), pdFALSE, NULL, fallback_to_setup);
        xTimerStart(fallback_timer, 0);
    }

    if (!settings_complete(settings)) start_setup_network();

    ESP_ERROR_CHECK(esp_wifi_start());
    esp_wifi_set_ps(WIFI_PS_NONE); // Corrections should not wait for a power-save wake-up
}

bool net_has_internet_path(void)
{
    return have_address;
}

void net_address(char *out, size_t capacity)
{
    out[0] = '\0';
    esp_netif_ip_info_t info;
    if (have_address && esp_netif_get_ip_info(station_netif, &info) == ESP_OK) {
        snprintf(out, capacity, IPSTR, IP2STR(&info.ip));
    }
}

int net_rssi(void)
{
    wifi_ap_record_t record;
    return (have_address && esp_wifi_sta_get_ap_info(&record) == ESP_OK) ? record.rssi : 0;
}

const char *net_setup_ssid(void)
{
    return setup_ssid;
}

bool net_setup_network_active(void)
{
    return setup_network_active;
}
