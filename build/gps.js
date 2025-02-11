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
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g = Object.create((typeof Iterator === "function" ? Iterator : Object).prototype);
    return g.next = verb(0), g["throw"] = verb(1), g["return"] = verb(2), typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var fs = __importStar(require("fs"));
var logger_1 = __importDefault(require("./utils/logger"));
var net = __importStar(require("net"));
var serialport_1 = require("serialport");
var child_process_1 = require("child_process");
var rl = __importStar(require("readline"));
//SETTINGS
var ntripServer = 'rtk2go.com';
var ntripPassword = 'arhG4oKZ';
var ntripMountpoint = 'SmirnovRTK';
var ntripPort = 2101;
var gpsAccuracy = 3.000; //in meters
var gpsSurveyTime = 60; //in seconds	
//Create objects
//let gpsParser = null;
var socketPath = '/tmp/';
var currentTimestamp = Date.now();
var syncDataSocketName = socketPath + 'zed-f9p-sync-data-' + currentTimestamp + '.sock';
// This object is being used to send data to the main process
var mainProcessDataObject = {
    survey_valid: false,
    set_accuracy: gpsAccuracy,
};
var f9pDataObject;
//Socket connections
var serialDevice;
var syncDataSocket; //data socket reference needed for sending commands to the driver
var syncDataServer;
//F9p driver
var f9pDriverProcess = null; //process handler for f9p driver
//Wrap everything in async function for proper await handling
var main = function () { return __awaiter(void 0, void 0, void 0, function () {
    return __generator(this, function (_a) {
        // Check if receiving socket for communication with f9p application can be opened(if a file from eprivious connection exists it may be a problem)
        try {
            if (fs.existsSync(syncDataSocketName)) {
                //file exists/ socket cannot be opened
                logger_1.default.info("Node receiving sockets cannot be opened because temporary files that were created for it was never removed from ".concat(socketPath, " directory"));
                unlinkSocketFiles();
            }
            else {
                logger_1.default.info('Receive sockets can be opened successfully');
            }
        }
        catch (err) {
            logger_1.default.error(err);
            logger_1.default.info('unable to remove socket file(s), gps cannot be started');
            process.exit();
        }
        /*
        Find GPS device by hardware ID's
        */
        findGPSDevice();
        // try {
        // 	//get list of all serial devices
        // 	info = await SerialPort.list()
        // 	//look for the one that matches our hardware ID's
        // 	serialDevice = _.find(info, device => device.vendorId === '1546' && device.productId.toLowerCase() === '01a9');
        // 	if (serialDevice) {
        // 		logger.info('Serial device that looks like Zed-F9p found on ' + serialDevice.path);
        // 	}
        // 	else {
        // 		//No device that matches vendor and ID found connected
        // 		logger.info('GPS Error: It does not appear that GPS Module is connected');
        // 		process.exit();
        // 	}
        // } catch (err) {
        // 	logger.error(err)
        // 	logger.info('unable to find serial device that fits specs')
        // 	process.exit();
        // }
        /*
        Open unix socket for interprocess communications(connection with .NET application that configures module)
    
        Socket for SYNC commands:
    
        Commands packets separated by \n
        */
        syncDataServer = net.createServer(function (socket) {
            syncDataSocket = socket;
            console.log("Client connected");
            var buffer = '';
            // Event listener for incoming data
            socket.on('data', function (data) {
                buffer += data.toString(); // Append received data to buffer
                // Process each complete message based on delimiter '\n'
                var messages = buffer.split('\n');
                buffer = messages.pop() || ''; // Keep last incomplete message
                for (var _i = 0, messages_1 = messages; _i < messages_1.length; _i++) {
                    var message = messages_1[_i];
                    try {
                        var syncData = JSON.parse(message);
                        //mainProcessDataObject = syncData;
                        processSyncData(syncData);
                    }
                    catch (error) {
                        console.error('Invalid JSON received:', message);
                    }
                }
            });
            // Handle client disconnect
            socket.on('end', function () {
                console.log("Client disconnected");
            });
            socket.on('error', function (err) {
                console.error("Socket error:", err);
            });
        });
        //Start listening on a changes for this socket
        syncDataServer.listen(syncDataSocketName);
        //connect f9p driver .net core application
        connectF9pDriver();
        //logger.info('gps output hookup...')	
        //wire up data event handler
        //gps.on('data', gpsOutput);
        //commands comming from the http server side
        process.on('message', function (command) {
            if (command.includes('RESTART_SURVEY') || command.includes('RESTART_FIXED')) {
                // Log the command to be sent
                logger_1.default.info('Sending command to sync socket: ' + command);
                // Ensure the socket is not destroyed before writing
                if (syncDataSocket && !syncDataSocket.destroyed) {
                    syncDataSocket.write(command, 'ascii');
                }
            }
        });
        return [2 /*return*/];
    });
}); };
var processSyncData = function (syncData) {
    logger_1.default.debug("Received SyncData:", syncData);
    // Example of how you might process the object
    mainProcessDataObject = {
        lat: syncData.Latitude,
        lon: syncData.Longitude,
        alt: syncData.Altitude,
        accuracy: syncData.Accuracy,
        set_accuracy: syncData.ModuleCurrentSetAccuracy,
        receiver_mode: syncData.ReceiverMode,
        survey_time: syncData.SurveyTime,
        survey_valid: syncData.IsSurveyValid,
        lastNtripSent: null
        //errors: syncData.Errors,
    };
    logger_1.default.debug("Processed Data:", mainProcessDataObject);
};
function findGPSDevice() {
    return __awaiter(this, void 0, void 0, function () {
        var info, err_1;
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0:
                    _a.trys.push([0, 2, , 3]);
                    return [4 /*yield*/, serialport_1.SerialPort.list()];
                case 1:
                    info = _a.sent();
                    // Look for the one that matches our hardware ID's
                    serialDevice = info.find(function (device) { var _a; return device.vendorId === '1546' && ((_a = device.productId) === null || _a === void 0 ? void 0 : _a.toLowerCase()) === '01a9'; });
                    if (serialDevice) {
                        console.log('Serial device that looks like Zed-F9p found on ' + serialDevice.path);
                    }
                    else {
                        // No device that matches vendor and ID found connected
                        console.log('GPS Error: It does not appear that GPS Module is connected');
                        process.exit();
                    }
                    return [3 /*break*/, 3];
                case 2:
                    err_1 = _a.sent();
                    if (err_1 instanceof Error) {
                        console.error(err_1.message);
                    }
                    else {
                        console.error('An unknown error occurred');
                    }
                    console.log('Unable to find serial device that fits specs');
                    process.exit();
                    return [3 /*break*/, 3];
                case 3: return [2 /*return*/];
            }
        });
    });
}
/*
Start F9p module reader (.NET application)
*/
var connectF9pDriver = function () {
    var _a, _b, _c;
    logger_1.default.info('Starting f9p driver application...');
    var command = __dirname + '/f9p/Zedf9p';
    var args = [
        '--com-port',
        (_a = serialDevice === null || serialDevice === void 0 ? void 0 : serialDevice.path) !== null && _a !== void 0 ? _a : '',
        '--ntrip-server', ntripServer,
        '--ntrip-port', ntripPort.toString(),
        '--ntrip-mountpoint', ntripMountpoint,
        '--ntrip-password', ntripPassword,
        '--rtcm-accuracy-req',
        (_c = (_b = mainProcessDataObject.set_accuracy) === null || _b === void 0 ? void 0 : _b.toString()) !== null && _c !== void 0 ? _c : '3',
        '--rtcm-survey-time', gpsSurveyTime.toString(),
        '--mode', 'Station',
        '--sync-socket', syncDataSocketName,
        '--debug'
    ];
    logger_1.default.debug('Running command: ' + command + ' ' + args.join(' '));
    f9pDriverProcess = (0, child_process_1.spawn)(__dirname + '/f9p/Zedf9p', args);
    //create interface for reading one line at a time
    var f9pReadLine = rl.createInterface(f9pDriverProcess.stdout);
    //write line in a console for now
    f9pReadLine.on('line', function (line) {
        logger_1.default.f9p(line);
    });
    f9pDriverProcess.stderr.on('data', function (data) {
        logger_1.default.error('F9p Driver Error: ' + data.toString());
    });
    f9pDriverProcess.on('close', function (code) {
        logger_1.default.info('F9p Driver: child process exited with code ' + code);
    });
    //Restart GPS driver process if it exits
    f9pDriverProcess.on('exit', function (code) {
        logger_1.default.info("Gps driver process exited with code " + code + ". Trying to restart...");
        connectF9pDriver();
    });
    logger_1.default.info('gps output hookup...');
};
/*
Disconnect f9p driver application
*/
var disconnectF9pDriver = function () {
    f9pDriverProcess && logger_1.default.info(f9pDriverProcess.kill()) && (f9pDriverProcess = null);
};
// Update main process
setInterval(function () { return process.send && process.send(mainProcessDataObject); }, 150);
// Unlink files assosiated with sockets
var unlinkSocketFiles = function () {
    if (fs.existsSync(syncDataSocketName)) {
        logger_1.default.info('trying to remove ' + syncDataSocketName);
        fs.unlinkSync(syncDataSocketName);
    }
};
// Improved exit handler with types
var exitHandler = function (options, exitCode) {
    // If cleanup is requested, log the cleanup process (optional log)
    if (options.cleanup) {
        console.info('Cleaning up...');
    }
    // Terminate child process if it exists
    if (f9pDriverProcess) {
        console.info(f9pDriverProcess.kill());
    }
    // Close sync data server if it exists
    if (syncDataServer) {
        syncDataServer.close();
    }
    // Unlink socket files
    unlinkSocketFiles();
    // Log the exit code if available
    if (exitCode !== undefined) {
        console.info("Exit Code (nodejs): ".concat(exitCode));
    }
    // Exit the process if the "exit" flag is set
    if (options.exit) {
        process.exit();
    }
};
// Do something when the app is closing (exit event)
process.on('exit', function () { return exitHandler({ cleanup: true }); });
// Handle ctrl+c event (SIGINT)
process.on('SIGINT', function () { return exitHandler({ exit: true }); });
// Handle "kill pid" (e.g., nodemon restart) signals (SIGUSR1, SIGUSR2)
process.on('SIGUSR1', function () { return exitHandler({ exit: true }); });
process.on('SIGUSR2', function () { return exitHandler({ exit: true }); });
// Handle uncaught exceptions
process.on('uncaughtException', function (err) {
    console.error('Uncaught Exception:', err);
    exitHandler({ exit: true });
});
main();
