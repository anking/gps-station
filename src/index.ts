import express from 'express';
import { createServer } from 'http';
import * as path from 'path';
import { Server as SocketServer } from 'socket.io';
import { fork, exec, ChildProcess, spawn, spawnSync } from 'child_process';
import logger from './utils/logger';
import { config, isSet } from './config';
import { httpAuth, socketAuth } from './auth';
import { isSafeCommandParams } from './baseMode';

const GPS_RESTART_DELAY_MS = 5000;

let gpsProcess: ChildProcess | null = null;
let gpsData: GpsProcessSyncData;
let lastGpsUpdate = 0;
let gpsUpdateScheduled = false;
const webServerUrl = `http://localhost:${config.webServerPort}`;
let browserProcess: ChildProcess | null = null;
let shuttingDown = false;

const expressServer = express();
const server = createServer(expressServer);
const webServerSocket = new SocketServer(server);  // Instantiate Socket.IO server

// Wrap everything in async function for proper await handling
const main = async (): Promise<void> => {
  // Output logger level
  logger.info(`Log level: ${logger.level}`);

  // Connect gps process
  createGpsProcess();

  // Setup Express
  setupWebServer();

  // Start browser on RPi
  if (config.kioskBrowser) {
    startBrowser();
  }

  process.on('SIGINT', () => shutdown());
  process.on('SIGTERM', () => shutdown());
};

const shutdown = (): void => {
  logger.info('Shutting down the server...');
  shuttingDown = true;
  gpsProcess?.kill();
  shutdownBrowser();
  server.close();
  process.exit();
};

const setupWebServer = (): void => {
  // The UI can move the base and switch the machine off, so it never goes on the network without a password
  const host = config.uiPassword ? undefined : '127.0.0.1';

  if (config.uiPassword) {
    expressServer.use(httpAuth(config.uiPassword));
    webServerSocket.use(socketAuth(config.uiPassword));
  } else {
    logger.warn('UI_PASSWORD is not set: the web UI is only available on this machine.');
  }

  expressServer.get('/', (_, res) => {
    res.sendFile(path.join(__dirname, 'static', 'index.html'));
  });

  // API route to expose environment variable
  expressServer.get('/config', (_, res) => {
    res.json({ googleMapsApiKey: isSet(config.googleMapsApiKey) ? config.googleMapsApiKey : null });
  });

  // Starting listening for server
  const onListening = () => logger.info(`listening on ${host ?? '*'}:${config.webServerPort}`);
  if (host) server.listen(config.webServerPort, host, onListening);
  else server.listen(config.webServerPort, onListening);

  // Websocket connection made
  webServerSocket.on('connection', (webSocket) => {
    logger.info('UI user connected(new socket created)');

    webSocket.on('disconnect', () => logger.info('UI user disconnected'));

    webSocket.on('RESTART_SURVEY', (params: unknown) => sendReceiverCommand('RESTART_SURVEY', params));
    webSocket.on('RESTART_FIXED', (params: unknown) => sendReceiverCommand('RESTART_FIXED', params));

    webSocket.on('POWER_OFF', () => handleSystemCommand('sudo shutdown now', 'Shutting down'));
    webSocket.on('REBOOT', () => handleSystemCommand('sudo shutdown -r now', 'Rebooting'));
  });
};

const sendReceiverCommand = (name: string, params: unknown): void => {
  if (!isSafeCommandParams(params)) {
    logger.warn(`Ignoring ${name} with invalid parameters`);
    return;
  }

  if (gpsProcess && !gpsProcess.killed) gpsProcess.send(`${name}:${params}`);
};

// Current Raspberry Pi OS calls the package "chromium", older images "chromium-browser"
const findBrowser = (): string | undefined =>
  ['chromium', 'chromium-browser'].find(name => spawnSync('which', [name]).status === 0);

// Start Chromium in kiosk mode when the server starts
const startBrowser = () => {
  const browser = findBrowser();
  if (!browser) {
    logger.info('No Chromium found, not opening the kiosk screen. Set KIOSK_BROWSER=false to skip this check.');
    return;
  }

  logger.chromium("Starting up browser...");

  // A service has no display of its own: point it at the desktop session
  process.env.DISPLAY = process.env.DISPLAY ?? ":0";

  browserProcess = spawn(browser, [
    "--no-sandbox",
    "--disable-gpu",
    "--kiosk",
    "--disable-infobars",
    "--disable-session-crashed-bubble",
    "--noerrdialogs",
    webServerUrl
  ], {
    detached: false,  // Don't detach so that we can manage the process
    stdio: ["ignore", "pipe", "pipe"]  // Capture stdout and stderr
  });

  browserProcess.stdout?.on('data', (data: Buffer) => {
    logger.chromium(data.toString());
  });

  browserProcess.stderr?.on('data', (data: Buffer) => {
    logger.debug(`[CR] ${data.toString()}`);
  });

  browserProcess.on('error', (err: Error) => {
    logger.error(`Failed to start browser: ${err.message}`);
  });

  browserProcess.on('exit', (code: number | null) => {
    logger.info(`Chromium exited with code: ${code}`);
  });
};

// Gracefully shut down and close the browser
const shutdownBrowser = () => {
  if (browserProcess) {
    logger.chromium("Shutting down the browser...");
    browserProcess.kill();  // Send termination signal to the browser process
  }
};

const createGpsProcess = (): void => {
  gpsProcess = fork(path.join(__dirname, 'gps.js'), logger.level === 'debug' ? ['--debug'] : []);

  // Getting coordinate data from GPS
  gpsProcess.on('message', (data: GpsProcessSyncData) => {
    gpsData = data;

    const now = Date.now();
    const timeSinceLastUpdate = now - lastGpsUpdate;

    if (timeSinceLastUpdate >= 1000) {
      // If at least 1 second has passed, send immediately
      sendGpsUpdate();
    } else if (!gpsUpdateScheduled) {
      // Schedule the next update if not already scheduled
      gpsUpdateScheduled = true;
      setTimeout(sendGpsUpdate, 1000 - timeSinceLastUpdate);
    }
  });

  // Restart GPS process if it exits, after a delay so a start-up failure cannot spin
  gpsProcess.on('exit', (code: number | null) => {
    if (shuttingDown) return;

    logger.info(`Gps process exited with code ${code}. Restarting in ${GPS_RESTART_DELAY_MS / 1000}s...`);
    setTimeout(createGpsProcess, GPS_RESTART_DELAY_MS);
  });
};

// Update browser
const sendGpsUpdate = () => {
  webServerSocket.emit('SENSOR_DATA', { gps: gpsData });
  lastGpsUpdate = Date.now();
  gpsUpdateScheduled = false;
};

// Helper function to handle system commands
const handleSystemCommand = (command: string, action: string) => {
  exec(command, (error, stdout, stderr) => {
    if (error) {
      logger.error(`Error during ${action}: ${error.message}`);
      return;
    }
    if (stderr) {
      logger.error(`stderr during ${action}: ${stderr}`);
      return;
    }
    logger.info(`${action} completed successfully: ${stdout}`);
  });
};

main();
