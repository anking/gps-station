// GPS base station on an ESP32: a ZED-F9P on a UART, corrections to an NTRIP caster over WiFi, a small web UI.
// The base station's logic is all in core/, this file connects it to the hardware.
#include <string.h>

#include "base_station.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "net.h"
#include "nvs_flash.h"
#include "settings.h"
#include "web.h"

#define UART_RX_BUFFER 8192
#define UART_TX_BUFFER 2048
#define RESET_HOLD_MS 5000
#define MARK_FIRMWARE_GOOD_AFTER_MS 60000

static const char *TAG = "main";

static base_station_t base;
static settings_t settings;
static SemaphoreHandle_t base_lock;

static void serial_write(void *ctx, const uint8_t *data, size_t length)
{
    (void)ctx;
    uart_write_bytes(GPS_UART_NUM, data, length);
}

static void serial_set_baud(void *ctx, uint32_t baud)
{
    (void)ctx;
    uart_set_baudrate(GPS_UART_NUM, baud);
    uart_flush_input(GPS_UART_NUM);
}

static bool network_ready(void *ctx)
{
    (void)ctx;
    return net_has_internet_path();
}

static void mode_changed(void *ctx, const base_mode_t *mode)
{
    (void)ctx;
    settings_save_mode(mode);
}

static uint32_t now_ms(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000);
}

static void start_uart(void)
{
    const uart_config_t config = {
        .baud_rate = 230400,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(GPS_UART_NUM, UART_RX_BUFFER, UART_TX_BUFFER, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(GPS_UART_NUM, &config));
    ESP_ERROR_CHECK(uart_set_pin(GPS_UART_NUM, GPS_TX_PIN, GPS_RX_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
}

static void check_reset_button(uint32_t now)
{
    static uint32_t pressed_since;
    static bool pressed;

    if (gpio_get_level(RESET_BUTTON_PIN) != 0) {
        pressed = false;
        return;
    }

    if (!pressed) {
        pressed = true;
        pressed_since = now;
    } else if (now - pressed_since >= RESET_HOLD_MS) {
        ESP_LOGW(TAG, "Reset button held, erasing the settings");
        settings_erase();
        esp_restart();
    }
}

static void base_task(void *arg)
{
    (void)arg;
    static uint8_t buffer[1024];
    bool firmware_marked_good = false;

    esp_task_wdt_add(NULL);

    for (;;) {
        // Waking on data keeps corrections moving as they arrive
        int count = uart_read_bytes(GPS_UART_NUM, buffer, sizeof(buffer), pdMS_TO_TICKS(10));
        uint32_t now = now_ms();

        xSemaphoreTake(base_lock, portMAX_DELAY);
        base.now_ms = now;
        if (count > 0) base_on_serial(&base, buffer, (size_t)count);
        base_tick(&base, now);
        xSemaphoreGive(base_lock);

        check_reset_button(now);

        // A new firmware that keeps crashing before this point rolls back to the previous one by itself
        if (!firmware_marked_good && now >= MARK_FIRMWARE_GOOD_AFTER_MS) {
            esp_ota_mark_app_valid_cancel_rollback();
            firmware_marked_good = true;
        }

        esp_task_wdt_reset();
    }
}

void app_main(void)
{
    esp_err_t result = nvs_flash_init();
    if (result == ESP_ERR_NVS_NO_FREE_PAGES || result == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        result = nvs_flash_init();
    }
    ESP_ERROR_CHECK(result);

    gpio_set_direction(RESET_BUTTON_PIN, GPIO_MODE_INPUT);
    gpio_set_pull_mode(RESET_BUTTON_PIN, GPIO_PULLUP_ONLY);

    settings_load(&settings);
    net_start(&settings);
    start_uart();

    base_hal_t hal = {
        .serial_write = serial_write,
        .serial_set_baud = serial_set_baud,
        .network_ready = network_ready,
        .mode_changed = mode_changed,
    };

    base_lock = xSemaphoreCreateMutex();
    base_init(&base, &hal, &settings.caster, &settings.mode);

    web_start(&base, base_lock, &settings);

    xTaskCreate(base_task, "base", 8192, NULL, 6, NULL);
}
