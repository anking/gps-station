interface MainProcessSyncData {
    lat?: number | null;
    lon?: number | null;
    alt?: number | null;
    survey_time?: number | null;
    accuracy?: number | null;
    survey_valid?: boolean | null;
    receiver_mode?: ReceiverModeEnum | null;
    set_accuracy?: number | null;
    lastNtripSent?: Date | null;
}
