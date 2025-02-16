import dotenv from 'dotenv';

// Load environment variables from .env file
dotenv.config();

function getEnvVariable<T>(key: string, defaultValue: T): T {
    const value = process.env[key];
    if (typeof defaultValue === 'number') {
      return (value ? Number(value) : defaultValue) as T;
    }
    return (value || defaultValue) as T;
  }

// Define environment variables with default values
export const config = {
    ntripServer: getEnvVariable('NTRIP_SERVER', 'xxxx-not-set'),
    ntripPort: getEnvVariable('NTRIP_PORT', 2101),
    ntripPassword: getEnvVariable('NTRIP_PASSWORD', 'xxxx-not-set'),
    ntripMountpoint: getEnvVariable('NTRIP_MOUNTPOINT', 'xxxx-not-set'),
    gpsAccuracy: getEnvVariable('GPS_ACCURACY', 3.000), // in meters
    gpsSurveyTime: getEnvVariable('GPS_SURVEY_TIME', 60), // in seconds
    webServerPort: getEnvVariable('WEB_SERVER_PORT', 3000), // in seconds
};