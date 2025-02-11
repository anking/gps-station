"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
var winston = __importStar(require("winston"));
var path = __importStar(require("path"));
var fs = __importStar(require("fs"));
// Define logs directory relative to where the app was started
var logDirectory = path.join(process.cwd(), 'logs');
// Ensure the logs directory exists
if (!fs.existsSync(logDirectory)) {
    fs.mkdirSync(logDirectory, { recursive: true });
}
// Define log file path
var logFilePath = path.join(logDirectory, 'app.log');
// Custom Log Levels
var customLevels = {
    levels: {
        error: 1,
        warn: 2,
        f9p: 3, // Custom level for f9p drive
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
var logger = winston.createLogger({
    level: 'debug', // Log levels: debug, info, error
    levels: customLevels.levels,
    format: winston.format.combine(winston.format.timestamp({ format: 'HH:mm:ss' }), // Format time as H:M:S
    winston.format.printf(function (_a) {
        var timestamp = _a.timestamp, level = _a.level, message = _a.message;
        return "[".concat(timestamp, "] [").concat(level.toUpperCase(), "]: ").concat(message);
    }), winston.format.colorize({ all: true })),
    transports: [
        new winston.transports.Console(),
        new winston.transports.File({
            filename: logFilePath,
            maxsize: 5 * 1024 * 1024, // 5 MB file size limit
            maxFiles: 3 // Keep only the last 3 log files (app.log, app1.log, app2.log)
        })
    ]
});
exports.default = logger;
