import dotenv from 'dotenv';
import * as path from 'path';

// Load environment variables from .env file
dotenv.config({ quiet: true });

const NOT_SET = 'xxxx-not-set';

function getEnvVariable<T>(key: string, defaultValue: T): T {
    const value = process.env[key];
    if (typeof defaultValue === 'number') {
      return (value ? Number(value) : defaultValue) as T;
    }
    return (value || defaultValue) as T;
  }

// Define environment variables with default values
export const config = {
    ntripServer: getEnvVariable('NTRIP_SERVER', NOT_SET),
    ntripPort: getEnvVariable('NTRIP_PORT', 2101),
    ntripPassword: getEnvVariable('NTRIP_PASSWORD', NOT_SET),
    ntripMountpoint: getEnvVariable('NTRIP_MOUNTPOINT', NOT_SET),
    gpsAccuracy: getEnvVariable('GPS_ACCURACY', 3.000), // in meters
    gpsSurveyTime: getEnvVariable('GPS_SURVEY_TIME', 60), // in seconds
    baseFixedPosition: getEnvVariable('BASE_FIXED_POSITION', ''), // latitude:longitude:height, overrides the survey at start-up
    gpsSerialPort: getEnvVariable('GPS_SERIAL_PORT', ''), // skips the USB search, for setups with more than one F9P
    webServerPort: getEnvVariable('WEB_SERVER_PORT', 3000),
    uiPassword: getEnvVariable('UI_PASSWORD', ''), // without it the UI is only served to this machine
    kioskBrowser: getEnvVariable<string>('KIOSK_BROWSER', 'true') !== 'false',
    googleMapsApiKey: getEnvVariable('GOOGLE_MAPS_API_KEY', NOT_SET),
    driverPath: getEnvVariable('F9P_DRIVER_PATH', path.join(__dirname, '..', 'f9p', 'Zedf9p')),
    baseModeFile: getEnvVariable('BASE_MODE_FILE', path.join(process.cwd(), 'data', 'base-mode.json')),
};

/**
 * Connecting with placeholder credentials would only count as a bad connection against this IP on a public caster.
 */
export const isNtripConfigured = (): boolean =>
    ![config.ntripServer, config.ntripPassword, config.ntripMountpoint].some(value => !value || value === NOT_SET);

export const isSet = (value: string): boolean => Boolean(value) && !value.includes('NOT_SET') && value !== NOT_SET;
