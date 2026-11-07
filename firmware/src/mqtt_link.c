#include "mqtt_link.h"

#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "esp_app_desc.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "freertos/task.h"
#include "mqtt_client.h"
#include "net.h"
#include "ota.h"
#include "sdkconfig.h"

#define TELEMETRY_PERIOD_MS 5000
#define TELEMETRY_RESERVE 160
#define OUTGOING_BUFFER 1600
#define INCOMING_BUFFER 1024
#define TASK_STACK 6144
#define TASK_PRIORITY 4

static const char *TAG = "mqtt";

static base_station_t *base;
static SemaphoreHandle_t lock;
static esp_mqtt_client_handle_t client;
static volatile bool connected;

// Held for the life of the client, which keeps pointers to its settings
static settings_t config;

static char mac[18];
static char client_id[32];
static char topic_status[48];
static char topic_info[48];
static char topic_telemetry[48];
static char topic_cmd[48];
static char topic_responses[48];

static void publish_info(void)
{
    char address[16];
    net_address(address, sizeof(address));

    const esp_app_desc_t *app = esp_app_get_description();
    char json[200];
    snprintf(json, sizeof(json), "{\"model\":\"%s\",\"firmware\":\"%s\",\"project\":\"%s\",\"ui_url\":\"http://%s\"}",
             CONFIG_IDF_TARGET, app->version, app->project_name, address);

    esp_mqtt_client_publish(client, topic_info, json, 0, 1, 1);
}

static void respond(const char *id, bool ok, const char *error)
{
    cJSON *root = cJSON_CreateObject();
    if (root == NULL) return;

    if (id != NULL) cJSON_AddStringToObject(root, "id", id);
    cJSON_AddBoolToObject(root, "ok", ok);
    if (error != NULL) cJSON_AddStringToObject(root, "error", error);

    char *json = cJSON_PrintUnformatted(root);
    if (json != NULL) {
        esp_mqtt_client_publish(client, topic_responses, json, 0, 1, 0);
        cJSON_free(json);
    }
    cJSON_Delete(root);
}

static void handle_command(const char *data, size_t length)
{
    cJSON *root = cJSON_ParseWithLength(data, length);
    if (root == NULL) {
        ESP_LOGW(TAG, "Ignoring a command that is not JSON");
        return;
    }

    const char *id = cJSON_GetStringValue(cJSON_GetObjectItem(root, "id"));
    const char *action = cJSON_GetStringValue(cJSON_GetObjectItem(root, "action"));

    if (action == NULL || strcmp(action, "update_firmware") != 0) {
        respond(id, false, "unknown action");
    } else {
        const cJSON *target = cJSON_GetObjectItem(cJSON_GetObjectItem(root, "params"), "firmware_id");
        int firmware_id = cJSON_IsNumber(target) ? target->valueint : 0;

        if (ota_request_check(firmware_id)) {
            respond(id, true, NULL);
        } else {
            respond(id, false, "a check is already running");
        }
    }

    cJSON_Delete(root);
}

static void on_event(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data)
{
    (void)arg;
    (void)event_base;
    esp_mqtt_event_handle_t event = event_data;

    switch ((esp_mqtt_event_id_t)event_id) {
    case MQTT_EVENT_CONNECTED:
        connected = true;
        ESP_LOGI(TAG, "Connected to the broker");
        esp_mqtt_client_publish(client, topic_status, "{\"online\":true}", 0, 1, 1);
        publish_info();
        esp_mqtt_client_subscribe(client, topic_cmd, 1);
        break;

    case MQTT_EVENT_DISCONNECTED:
        connected = false;
        ESP_LOGW(TAG, "Disconnected from the broker");
        break;

    case MQTT_EVENT_DATA:
        // A real command is tiny. Part of a larger message could only parse by accident.
        if (event->total_data_len != event->data_len) break;
        if (event->topic_len != (int)strlen(topic_cmd) || memcmp(event->topic, topic_cmd, (size_t)event->topic_len) != 0) break;

        // A retained command is an old one the broker replays at every connect. It must not fire again, so it
        // is removed rather than obeyed. Empty and retained is how MQTT deletes one, and it comes back here empty.
        if (event->retain) {
            if (event->data_len > 0) {
                ESP_LOGW(TAG, "Ignoring and clearing a retained command");
                esp_mqtt_client_publish(client, topic_cmd, "", 0, 1, 1);
            }
            break;
        }

        handle_command(event->data, (size_t)event->data_len);
        break;

    default:
        break;
    }
}

static void telemetry_task(void *arg)
{
    (void)arg;
    static char json[OUTGOING_BUFFER];

    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(TELEMETRY_PERIOD_MS));
        if (!connected) continue;

        xSemaphoreTake(lock, portMAX_DELAY);
        int length = base_status_json(base, json, sizeof(json) - TELEMETRY_RESERVE);
        xSemaphoreGive(lock);

        if (length <= 0 || length >= (int)sizeof(json) - TELEMETRY_RESERVE) {
            ESP_LOGE(TAG, "The status does not fit");
            continue;
        }

        char update[80];
        ota_status(update, sizeof(update));

        // Add what only this layer knows, before the closing brace
        snprintf(json + length - 1, sizeof(json) - (size_t)length + 1, ",\"rssi\":%d,\"uptime_s\":%lld,\"update_status\":\"%s\"}",
                 net_rssi(), esp_timer_get_time() / 1000000, update);

        // QoS 0: a report that was missed is replaced by the next one 5 seconds later
        esp_mqtt_client_publish(client, topic_telemetry, json, 0, 0, 0);
    }
}

void mqtt_link_start(base_station_t *base_station, SemaphoreHandle_t base_lock, const settings_t *settings)
{
    if (settings->mqtt_host[0] == '\0') {
        ESP_LOGI(TAG, "No broker set, not reporting");
        return;
    }

    base = base_station;
    lock = base_lock;
    config = *settings;

    uint8_t raw[6] = { 0 };
    esp_read_mac(raw, ESP_MAC_WIFI_STA);
    snprintf(mac, sizeof(mac), "%02x-%02x-%02x-%02x-%02x-%02x", raw[0], raw[1], raw[2], raw[3], raw[4], raw[5]);

    snprintf(client_id, sizeof(client_id), "base-%s", mac);
    snprintf(topic_status, sizeof(topic_status), "bases/%s/status", mac);
    snprintf(topic_info, sizeof(topic_info), "bases/%s/info", mac);
    snprintf(topic_telemetry, sizeof(topic_telemetry), "bases/%s/telemetry", mac);
    snprintf(topic_cmd, sizeof(topic_cmd), "bases/%s/cmd", mac);
    snprintf(topic_responses, sizeof(topic_responses), "bases/%s/responses", mac);

    esp_mqtt_client_config_t mqtt = {
        .broker.address.hostname = config.mqtt_host,
        .broker.address.port = config.mqtt_port,
        .broker.address.transport = MQTT_TRANSPORT_OVER_TCP,
        .credentials.client_id = client_id,
        .credentials.username = config.mqtt_user[0] ? config.mqtt_user : NULL,
        .credentials.authentication.password = config.mqtt_password[0] ? config.mqtt_password : NULL,
        .session.keepalive = 30,
        .session.last_will.topic = topic_status,
        .session.last_will.msg = "{\"online\":false}",
        .session.last_will.qos = 1,
        .session.last_will.retain = true,
        .buffer.size = INCOMING_BUFFER,
        .buffer.out_size = OUTGOING_BUFFER,
    };

    client = esp_mqtt_client_init(&mqtt);
    if (client == NULL) {
        ESP_LOGE(TAG, "Could not create the MQTT client");
        return;
    }

    esp_mqtt_client_register_event(client, ESP_EVENT_ANY_ID, on_event, NULL);
    esp_mqtt_client_start(client);

    xTaskCreate(telemetry_task, "telemetry", TASK_STACK, NULL, TASK_PRIORITY, NULL);
}
