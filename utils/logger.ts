import * as winston from 'winston';
import * as path from 'path';
import * as fs from 'fs';

// Check for --debug flag in command-line arguments
const args = process.argv.slice(2);
const isDebugMode = args.includes('--debug');

// Define logs directory relative to where the app was started
const logDirectory: string = path.join(process.cwd(), 'logs');

// Ensure the logs directory exists
if (!fs.existsSync(logDirectory)) {
    fs.mkdirSync(logDirectory, { recursive: true });
}

// Define log file path
const logFilePath: string = path.join(logDirectory, 'app.log');

// Custom Log Levels
const customLevels = {
    levels: {
        error: 1,
        warn: 2,
        f9p: 3,  // Custom level for f9p drive
        info: 4,
        debug: 5
    },
    colors: {
        f9p: 'cyan',
        error: 'red',
        warn: 'yellow',
        info: 'green',
        debug: 'magenta'
    }
};

// Add the custom colors to the Winston log level colorizer
winston.addColors(customLevels.colors);

// Create logger instance with file size limits
const logger = winston.createLogger({
    level: isDebugMode ? 'debug' : 'info', // Log levels: debug, info, error
    levels: customLevels.levels,
    format: winston.format.combine(        
        winston.format.timestamp({ format: 'HH:mm:ss' }), // Format time as H:M:S
        winston.format.printf(({ timestamp, level, message }: winston.Logform.TransformableInfo) => {
            return `[${timestamp}] [${level.toUpperCase()}]: ${message}`;
        }),
        winston.format.colorize({ all: true }), // Apply colors
    ),
    transports: [
        new winston.transports.Console(),
        new winston.transports.File({
            filename: logFilePath,
            maxsize: 5 * 1024 * 1024, // 5 MB file size limit
            maxFiles: 3 // Keep only the last 3 log files (app.log, app1.log, app2.log)
        })
    ]
});

export default logger;
