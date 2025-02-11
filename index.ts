import express from 'express';
import { createServer } from 'http';
import {Server as SocketServer} from 'socket.io';
import { fork, exec, ChildProcess } from 'child_process';
import logger from './utils/logger';

// Create objects
let gpsProcess: ChildProcess | null = null;
let gpsData: any = null; // You can replace `any` with a more specific type based on your GPS data structure

// Wrap everything in async function for proper await handling
const main = async (): Promise<void> => {

  // Connect gps process
  createGpsProcess();

  // Setup Express
  setupWebServer();

  // Update browser
  setInterval(() => io.emit('sensor data', { gps: gpsData }), 150);

  // If process forcibly terminated - clear out
  process.on('SIGTERM', () => {
	server.close();
  });

};

const expressServer = express();
const server = createServer(expressServer);
const io = new SocketServer(server);  // Instantiate Socket.IO server

const setupWebServer = (): void => {
  expressServer.get('/', (_, res) => {
    res.sendFile(__dirname + '/index.html');
  });

  expressServer.get('/chat', (_, res) => {
    res.sendFile(__dirname + '/chat.html');
  });

  // Starting listening for server
  server.listen(3000, () => {
    logger.info('listening on *:3000');
  });

  // Websocket connection made
  io.on('connection', (webSocket) => {
    logger.info('UI user connected(new socket created)');

    webSocket.on('disconnect', () => logger.info('UI user disconnected'));

    webSocket.on('chat message', (msg: string) => {
      logger.info('message: ' + msg);

      // mirror message back to user
      io.emit('chat message', msg);

      if (gpsProcess && msg === 'gps off') gpsProcess.send(msg);
      if (gpsProcess && msg === 'gps on') gpsProcess.send(msg);
    });

    webSocket.on('RESTART_SURVEY', (params: string) => gpsProcess && !gpsProcess.killed && gpsProcess.send('RESTART_SURVEY:' + params));
    webSocket.on('RESTART_FIXED', (params: string) => gpsProcess && !gpsProcess.killed && gpsProcess.send('RESTART_FIXED:' + params));

    webSocket.on('POWER_OFF', () => exec('shutdown now', (error, stdout, stderr) => logger.info('shutting down....')));
    webSocket.on('REBOOT', () => exec('shutdown -r now', (error, stdout, stderr) => logger.info('rebooting....')));

    // RTCM TEST
    webSocket.on('rtcm', (rtcmData: string) => {
      logger.info('RTCM: ' + rtcmData);
    });
  });
};

const createGpsProcess = (): void => {
  gpsProcess = fork('build/gps.js');

  // Getting coordinate data from GPS
  gpsProcess.on('message', (data: any) => { // Adjust the type of data based on your GPS message structure
    // update data in local cache
    gpsData = data;

    if (data.error) {
      logger.info('error generated by gps process: ' + data.error);
    }
  });

  // Restart GPS process if it exits
  gpsProcess.on('exit', (code: number) => {
    logger.info('Gps process exited with code ' + code + '. Trying to restart...');
    createGpsProcess();
  });
};

main();