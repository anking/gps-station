interface F9pSyncData {
    Latitude?: number | null;
    Longitude?: number | null;
    Altitude?: number | null;
    Accuracy?: number | null;
    Heading?: number | null;
    Errors?: any; // Adjust if Errors has a specific structure
    ModuleCurrentSetAccuracy?: number | null;
    ReceiverMode?: ReceiverModeEnum | null;
    SurveyTime?: number | null;
    IsSurveyValid?: boolean | null;
}
