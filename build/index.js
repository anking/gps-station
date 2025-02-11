"use strict";
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
var express_1 = __importDefault(require("express"));
var http_1 = require("http");
var socket_io_1 = require("socket.io");
var child_process_1 = require("child_process");
var logger_1 = __importDefault(require("./utils/logger"));
// Create objects
var gpsProcess = null;
var gpsData = null; // You can replace `any` with a more specific type based on your GPS data structure
// Wrap everything in async function for proper await handling
var main = function () { return __awaiter(void 0, void 0, void 0, function () {
    return __generator(this, function (_a) {
        // Connect gps process
        createGpsProcess();
        // Setup Express
        setupWebServer();
        // Update browser
        setInterval(function () { return io.emit('sensor data', { gps: gpsData }); }, 150);
        // If process forcibly terminated - clear out
        process.on('SIGTERM', function () {
            server.close();
        });
        return [2 /*return*/];
    });
}); };
var expressServer = (0, express_1.default)();
var server = (0, http_1.createServer)(expressServer);
var io = new socket_io_1.Server(server); // Instantiate Socket.IO server
var setupWebServer = function () {
    expressServer.get('/', function (_, res) {
        res.sendFile(__dirname + '/index.html');
    });
    expressServer.get('/chat', function (_, res) {
        res.sendFile(__dirname + '/chat.html');
    });
    // Starting listening for server
    server.listen(3000, function () {
        logger_1.default.info('listening on *:3000');
    });
    // Websocket connection made
    io.on('connection', function (webSocket) {
        logger_1.default.info('UI user connected(new socket created)');
        webSocket.on('disconnect', function () { return logger_1.default.info('UI user disconnected'); });
        webSocket.on('chat message', function (msg) {
            logger_1.default.info('message: ' + msg);
            // mirror message back to user
            io.emit('chat message', msg);
            if (gpsProcess && msg === 'gps off')
                gpsProcess.send(msg);
            if (gpsProcess && msg === 'gps on')
                gpsProcess.send(msg);
        });
        webSocket.on('RESTART_SURVEY', function (params) { return gpsProcess && !gpsProcess.killed && gpsProcess.send('RESTART_SURVEY:' + params); });
        webSocket.on('RESTART_FIXED', function (params) { return gpsProcess && !gpsProcess.killed && gpsProcess.send('RESTART_FIXED:' + params); });
        webSocket.on('POWER_OFF', function () { return (0, child_process_1.exec)('shutdown now', function (error, stdout, stderr) { return logger_1.default.info('shutting down....'); }); });
        webSocket.on('REBOOT', function () { return (0, child_process_1.exec)('shutdown -r now', function (error, stdout, stderr) { return logger_1.default.info('rebooting....'); }); });
        // RTCM TEST
        webSocket.on('rtcm', function (rtcmData) {
            logger_1.default.info('RTCM: ' + rtcmData);
        });
    });
};
var createGpsProcess = function () {
    gpsProcess = (0, child_process_1.fork)('build/gps.js');
    // Getting coordinate data from GPS
    gpsProcess.on('message', function (data) {
        // update data in local cache
        gpsData = data;
        if (data.error) {
            logger_1.default.info('error generated by gps process: ' + data.error);
        }
    });
    // Restart GPS process if it exits
    gpsProcess.on('exit', function (code) {
        logger_1.default.info('Gps process exited with code ' + code + '. Trying to restart...');
        createGpsProcess();
    });
};
main();
