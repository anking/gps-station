import * as fs from 'fs';
import logger from './utils/logger';
import * as net from 'net';
import { SerialPort } from 'serialport';
import { ChildProcess, spawn } from 'child_process';
import * as rl from 'readline';
import { config, isNtripConfigured } from './config';
import { BaseMode, driverModeArgs, isValidFixedPosition, loadBaseMode, parseModeCommand, saveBaseMode } from './baseMode';

// Check for --debug flag in command-line arguments
const args = process.argv.slice(2);
const isDebugMode = args.includes('--debug');

const EXIT_INVALID_ARGUMENTS = 2;
const DEVICE_SEARCH_PERIOD_MS = 5000;
const DRIVER_RESTART_MIN_MS = 5000;
const DRIVER_RESTART_MAX_MS = 60000;
const DRIVER_HEALTHY_MS = 60000;

//Create objects
const socketPath = '/tmp/';
const currentTimestamp = Date.now();
const syncDataSocketName = socketPath + 'zed-f9p-sync-data-' + currentTimestamp + '.sock';

// This object is being used to send data to the main process
let mainProcessDataObject: GpsProcessSyncData = {
	survey_valid: false,
	set_accuracy: config.gpsAccuracy,
};

// Problems only this process can see, shown next to the ones the driver reports
const localErrors = new Set<string>();
let driverErrors: string[] = [];

//Socket connections
let syncDataSocket: net.Socket | undefined;		//data socket reference needed for sending commands to the driver
let syncDataServer: net.Server | undefined;

//F9p driver
let f9pDriverProcess: ChildProcess | null = null;		//process handler for f9p driver
let driverStartedAt = 0;
let driverRestartDelay = DRIVER_RESTART_MIN_MS;
let driverExitHandled = false;
let shuttingDown = false;

const fallbackMode: BaseMode = isValidFixedPosition(config.baseFixedPosition)
	? { kind: 'fixed', position: config.baseFixedPosition }
	: { kind: 'survey', accuracy: config.gpsAccuracy, time: config.gpsSurveyTime };

let baseMode = loadBaseMode(config.baseModeFile, fallbackMode);

//Wrap everything in async function for proper await handling
const main = async () => {
	// The commands have to work before the driver starts, or a mode set during start-up is lost
	process.on('message', handleMainProcessCommand);

	if (!isNtripConfigured()) {
		localErrors.add('NTRIP_NOT_CONFIGURED');
		logger.error('NTRIP_SERVER, NTRIP_MOUNTPOINT and NTRIP_PASSWORD must be set in .env. Not connecting to the caster.');
		return;
	}

	unlinkSocketFiles();

	// The driver connects to this socket as soon as it starts, so it has to be listening first
	await startSyncServer();

	await startDriverWhenDeviceIsPresent();
};

const startSyncServer = (): Promise<void> => new Promise((resolve, reject) => {
	/*
	Open unix socket for interprocess communications(connection with .NET application that configures module)

	Socket for SYNC commands:

	Commands packets separated by \n
	*/
	syncDataServer = net.createServer((socket: net.Socket) => {
		logger.info('Client connected');
		syncDataSocket = socket;

		let buffer = '';

		// Event listener for incoming data
		socket.on('data', (data: Buffer) => {
			buffer += data.toString(); // Append received data to buffer

			const messages = buffer.split('\n');
			buffer = messages.pop() || ''; // Retain any incomplete message in the buffer

			for (const message of messages) {
				const trimmedMessage = message.trim(); // Remove leading/trailing spaces
				if (!trimmedMessage) continue; // Skip empty messages

				try {
					processSyncData(JSON.parse(trimmedMessage) as F9pSyncData);
				} catch (error) {
					logger.error(`Invalid JSON received: ${trimmedMessage}`);
				}
			}
		});

		socket.on('end', () => logger.info('Client disconnected'));

		socket.on('error', (err: Error) => {
			logger.error(`Socket error: ${err.message}`);
		});
	});

	syncDataServer.once('error', reject);
	syncDataServer.listen(syncDataSocketName, resolve);
});

//commands comming from the http server side
const handleMainProcessCommand = (command: string) => {
	if (typeof command !== 'string' || !(command.startsWith('RESTART_SURVEY') || command.startsWith('RESTART_FIXED'))) return;

	logger.info('Received command: ' + command);

	// Anything invalid still goes to the driver, which reports it and leaves the base as it is
	const mode = parseModeCommand(command);
	if (mode) {
		baseMode = mode;
		try {
			saveBaseMode(config.baseModeFile, mode);
		} catch (error) {
			logger.error(`Could not save the base mode, it will not survive a restart: ${error}`);
		}
	}

	if (syncDataSocket && !syncDataSocket.destroyed) {
		syncDataSocket.write(command + '\n', 'ascii');
	}
};

const processSyncData = (syncData: F9pSyncData) => {
	logger.debug(`Received SyncData: ${JSON.stringify(syncData)}`);

	if (syncData.Errors) driverErrors = syncData.Errors;

	// Update only if the value is defined
	mainProcessDataObject = {
		lat: syncData.Latitude ?? mainProcessDataObject.lat,
		lon: syncData.Longitude ?? mainProcessDataObject.lon,
		alt: syncData.Altitude ?? mainProcessDataObject.alt,
		accuracy: syncData.Accuracy ?? mainProcessDataObject.accuracy,
		set_accuracy: syncData.ModuleCurrentSetAccuracy ?? mainProcessDataObject.set_accuracy,
		receiver_mode: syncData.ReceiverMode ?? mainProcessDataObject.receiver_mode,
		survey_time: syncData.SurveyTime ?? mainProcessDataObject.survey_time,
		survey_valid: syncData.IsSurveyValid ?? mainProcessDataObject.survey_valid,
		last_ntrip_sent: syncData.LastNtripSent ?? mainProcessDataObject.last_ntrip_sent,
	};
}

async function findGPSDevicePath(): Promise<string | undefined> {
	if (config.gpsSerialPort) return config.gpsSerialPort;

	// Get list of all serial devices
	const info: SerialDevice[] = await SerialPort.list();

	// Look for the one that matches our hardware ID's
	return info.find(device => device.vendorId === '1546' && device.productId?.toLowerCase() === '01a9')?.path;
}

/**
 * Waits for the module instead of exiting: the base may be powered before it, and it may be replugged later.
 */
async function startDriverWhenDeviceIsPresent() {
	if (shuttingDown) return;

	let devicePath: string | undefined;
	try {
		devicePath = await findGPSDevicePath();
	} catch (err: unknown) {
		logger.error('Unable to list serial devices: ' + (err instanceof Error ? err.message : String(err)));
	}

	if (!devicePath) {
		if (!localErrors.has('GPS_NOT_CONNECTED')) logger.info('GPS Error: It does not appear that GPS Module is connected');
		localErrors.add('GPS_NOT_CONNECTED');
		setTimeout(startDriverWhenDeviceIsPresent, DEVICE_SEARCH_PERIOD_MS);
		return;
	}

	localErrors.delete('GPS_NOT_CONNECTED');
	logger.info('Serial device that looks like Zed-F9p found on ' + devicePath);
	connectF9pDriver(devicePath);
}

/*
Start F9p module reader (.NET application)
*/
const connectF9pDriver = (devicePath: string) => {
	logger.info('Starting f9p driver application...')

	const driverArgs: string[] = [
		'--com-port', devicePath,
		'--ntrip-server', config.ntripServer,
		'--ntrip-port', config.ntripPort.toString(),
		'--ntrip-mountpoint', config.ntripMountpoint,
		'--ntrip-password', config.ntripPassword,
		...driverModeArgs(baseMode),
		'--mode', 'Station',
		'--sync-socket', syncDataSocketName
	];

	if (isDebugMode) {
		driverArgs.push('--debug');
	}

	driverExitHandled = false;
	driverStartedAt = Date.now();
	f9pDriverProcess = spawn(config.driverPath, driverArgs);

	//create interface for reading one line at a time
	rl.createInterface(f9pDriverProcess.stdout!).on('line', line => logger.f9p(line));

	f9pDriverProcess.stderr!.on('data', (data: Buffer) => {
		logger.error('F9p Driver Error: ' + data.toString());
	});

	f9pDriverProcess.on('error', (err: Error) => {
		logger.error(`Cannot run the F9p driver at ${config.driverPath}: ${err.message}`);
		handleDriverGone(null);
	});

	f9pDriverProcess.on('exit', (code: number | null) => handleDriverGone(code));
}

/**
 * Restarts the driver after a growing delay. Restarting at once would also restart its caster backoff, and repeated
 * connections from one IP get it banned.
 */
const handleDriverGone = (code: number | null) => {
	if (driverExitHandled || shuttingDown) return;
	driverExitHandled = true;

	f9pDriverProcess = null;
	syncDataSocket = undefined;
	driverErrors = [];

	// The arguments will not get better by themselves
	if (code === EXIT_INVALID_ARGUMENTS) {
		localErrors.add('DRIVER_CONFIG_ERROR');
		logger.error('The F9p driver refused its arguments. Check .env, then restart the service.');
		return;
	}

	if (Date.now() - driverStartedAt >= DRIVER_HEALTHY_MS) driverRestartDelay = DRIVER_RESTART_MIN_MS;

	logger.info(`F9p driver exited with code ${code}. Restarting in ${driverRestartDelay / 1000}s...`);
	localErrors.add('DRIVER_RESTARTING');

	setTimeout(() => {
		localErrors.delete('DRIVER_RESTARTING');
		startDriverWhenDeviceIsPresent();
	}, driverRestartDelay);

	driverRestartDelay = Math.min(driverRestartDelay * 2, DRIVER_RESTART_MAX_MS);
}

/*
Disconnect f9p driver application
*/
const disconnectF9pDriver = () => {
	if (f9pDriverProcess) {
		logger.info(`F9p child process terminated: ${f9pDriverProcess.kill()}`);
		f9pDriverProcess = null;
	}
}

// Update main process
setInterval(() => process.send && process.send({
	...mainProcessDataObject,
	errors: [...localErrors, ...driverErrors],
}), 150)

// Unlink files assosiated with sockets
const unlinkSocketFiles = () => {
	if (fs.existsSync(syncDataSocketName)) {
		logger.info('trying to remove ' + syncDataSocketName)
		fs.unlinkSync(syncDataSocketName)
	}
}

// Improved exit handler with types
const exitHandler = (options: { cleanup?: boolean; exit?: boolean }, exitCode?: number): void => {
	shuttingDown = true;

	// If cleanup is requested, log the cleanup process (optional log)
	if (options.cleanup) {
		logger.info('Cleaning up...');
	}

	// Terminate child process if it exists
	disconnectF9pDriver();

	// Close sync data server if it exists
	syncDataServer?.close();

	// Unlink socket files
	unlinkSocketFiles();

	// Log the exit code if available
	if (exitCode !== undefined) {
		logger.info(`Exit Code (nodejs): ${exitCode}`);
	}

	// Exit the process if the "exit" flag is set
	if (options.exit) {
		process.exit();
	}
};

// Do something when the app is closing (exit event)
process.on('exit', () => exitHandler({ cleanup: true }));

// Handle ctrl+c event (SIGINT) and service stop (SIGTERM)
process.on('SIGINT', () => exitHandler({ exit: true }));
process.on('SIGTERM', () => exitHandler({ exit: true }));

// Handle "kill pid" (e.g., nodemon restart) signals (SIGUSR1, SIGUSR2)
process.on('SIGUSR1', () => exitHandler({ exit: true }));
process.on('SIGUSR2', () => exitHandler({ exit: true }));

// Handle uncaught exceptions
process.on('uncaughtException', (err: Error) => {
	logger.error(`Uncaught Exception: ${err.stack ?? err.message}`);
	exitHandler({ exit: true });
});

main().catch(err => {
	logger.error(`GPS process failed to start: ${err}`);
	process.exit(1);
});
