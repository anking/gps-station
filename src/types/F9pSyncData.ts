// One JSON line from the driver on the sync socket. See the zedf9p-server readme for the units.
interface F9pSyncData {
    Latitude?: number | null;
    Longitude?: number | null;
    Altitude?: number | null;
    Accuracy?: number | null;
    Heading?: number | null;
    GroundSpeed?: number | null;
    FixType?: number | null;
    CarrierSolution?: number | null;
    Satellites?: number | null;
    Errors?: string[] | null;
    ModuleCurrentSetAccuracy?: number | null;
    ReceiverMode?: ReceiverModeEnum | null;
    SurveyTime?: number | null;
    IsSurveyValid?: boolean | null;
    LastNtripSent?: string | null;
}
