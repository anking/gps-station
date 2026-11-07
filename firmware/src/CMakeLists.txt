idf_component_register(
    SRCS
        "main.c"
        "settings.c"
        "net.c"
        "web.c"
        "ota.c"
        "mqtt_link.c"
        "core/base_station.c"
        "core/caster.c"
        "core/direct_server.c"
        "core/fixed_position.c"
        "core/gnss_stream.c"
        "core/update_policy.c"
    INCLUDE_DIRS "." "core"
    REQUIRES driver esp_timer esp_wifi esp_http_server esp_netif nvs_flash esp_event app_update mbedtls esp_app_format esp_http_client esp_https_ota mqtt json
    EMBED_TXTFILES "web/index.html"
)
