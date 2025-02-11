import * as fs from 'fs';
import logger from './utils/logger';
import * as net from 'net';
import { SerialPort } from 'serialport';
import { spawn } from 'child_process';
import * as rl from 'readline';


//SETTINGS
const ntripServer = 'rtk2go.com';
const ntripPassword = 'arhG4oKZ';
const ntripMountpoint = 'SmirnovRTK';
const ntripPort = 2101;
let gpsAccuracy: number = 3.000;		//in meters
let gpsSurveyTime: number = 60;		//in seconds	

//Create objects
//let gpsParser = null;
const socketPath = '/tmp/';
const currentTimestamp = Date.now();
const syncDataSocketName = socketPath + 'zed-f9p-sync-data-' + currentTimestamp + '.sock';

// This object is being used to send data to the main process
var mainProcessDataObject : MainProcessSyncData = {		//this object is being used to send data to the main process
	survey_valid: false,
	set_accuracy: gpsAccuracy,
};
var f9pDataObject : F9pSyncData;

//Socket connections
let serialDevice: SerialDevice | undefined;
let syncDataSocket: net.Socket;		//data socket reference needed for sending commands to the driver
let syncDataServer: net.Server;

//F9p driver
let f9pDriverProcess: any = null;		//process handler for f9p driver




//Wrap everything in async function for proper await handling
const main = async () => {

	// Check if receiving socket for communication with f9p application can be opened(if a file from eprivious connection exists it may be a problem)
	try {
		if (fs.existsSync(syncDataSocketName)) {
			//file exists/ socket cannot be opened
			logger.info(`Node receiving sockets cannot be opened because temporary files that were created for it was never removed from ${socketPath} directory`)

			unlinkSocketFiles();
		} else {
			logger.info('Receive sockets can be opened successfully')
		}
	} catch (err) {
		logger.error(err)
		logger.info('unable to remove socket file(s), gps cannot be started')
		process.exit();
	}


	
	// Find GPS device by hardware ID's
	await findGPSDevice();	

	// Connect f9p driver .net core application
	connectF9pDriver();

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
	
			let messages = buffer.split('\n');
			buffer = messages.pop() || ''; // Retain any incomplete message in the buffer
	
			for (const message of messages) {
				const trimmedMessage = message.trim(); // Remove leading/trailing spaces
				if (!trimmedMessage) continue; // Skip empty messages
	
				try {
					const syncData: F9pSyncData = JSON.parse(trimmedMessage) as F9pSyncData;
					processSyncData(syncData);
				} catch (error) {
					logger.error(`Invalid JSON received: ${trimmedMessage}`);
				}
			}
		});
	
		// Handle client disconnect
		socket.on('end', () => {
			if (buffer.trim()) {
				// Attempt to process remaining data if valid JSON
				try {
					const syncData: F9pSyncData = JSON.parse(buffer.trim()) as F9pSyncData;
					processSyncData(syncData);
				} catch (error) {
					logger.error(`Invalid JSON received at end: ${buffer.trim()}`);
				}
			}
			logger.info('Client disconnected');
		});
	
		socket.on('error', (err: Error) => {
			logger.error(`Socket error: ${err.message}`);
		});
	});

	//Start listening on a changes for this socket
	syncDataServer.listen(syncDataSocketName);

	//logger.info('gps output hookup...')	
	//wire up data event handler
	//gps.on('data', gpsOutput);

	//commands comming from the http server side
	process.on('message', (command: string) => {
		if (command.includes('RESTART_SURVEY') || command.includes('RESTART_FIXED')) {
			// Log the command to be sent
			logger.info('Sending command to sync socket: ' + command);
	
			// Ensure the socket is not destroyed before writing
			if (syncDataSocket && !syncDataSocket.destroyed) {
				syncDataSocket.write(command, 'ascii');
			}
		}
	});
};

const processSyncData = (syncData: F9pSyncData) => {
    logger.debug(`Received SyncData: ${JSON.stringify(syncData)}`);

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

    logger.debug(`Processed Data: ${JSON.stringify(mainProcessDataObject)}`);
}

async function findGPSDevice() {
    try {
        // Get list of all serial devices
        const info: SerialDevice[] = await SerialPort.list();

        // Look for the one that matches our hardware ID's
        serialDevice = info.find((device) => 
			device.vendorId === '1546' && device.productId?.toLowerCase() === '01a9'
		);

        if (serialDevice) {
            logger.info('Serial device that looks like Zed-F9p found on ' + serialDevice.path);
        } else {
            // No device that matches vendor and ID found connected
            logger.info('GPS Error: It does not appear that GPS Module is connected');
            process.exit();
        }
    } catch (err: unknown) {
        if (err instanceof Error) {
            logger.error(err.message);
        } else {
            logger.error('An unknown error occurred');
        }
        logger.info('Unable to find serial device that fits specs');
        process.exit();
    }
}

/*
Start F9p module reader (.NET application)
*/
const connectF9pDriver = () => {
	logger.info('Starting f9p driver application...')

	const command = __dirname + '/f9p/Zedf9p';
	const args: string[] = [
		'--com-port', serialDevice?.path ?? '',
		'--ntrip-server', ntripServer,
		'--ntrip-port', ntripPort.toString(),
		'--ntrip-mountpoint', ntripMountpoint,
		'--ntrip-password', ntripPassword,
		'--rtcm-accuracy-req', mainProcessDataObject.set_accuracy?.toString() ?? '3',
		'--rtcm-survey-time', gpsSurveyTime.toString(),
		'--mode', 'Station',
		'--sync-socket', syncDataSocketName,
		'--debug'
	];

	logger.debug('Running command: ' + command + ' ' + args.join(' '));

	f9pDriverProcess = spawn(__dirname + '/f9p/Zedf9p', args);

	//create interface for reading one line at a time
	let f9pReadLine = rl.createInterface(f9pDriverProcess.stdout);

	//write line in a console for now
	f9pReadLine.on('line', line => {
		logger.f9p(line);
	});

	f9pDriverProcess.stderr.on('data', (data: Buffer) => {
		logger.error('F9p Driver Error: ' + data.toString());
	});

	f9pDriverProcess.on('close', (code: number | null) => {
		logger.info('F9p Driver: child process exited with code ' + code);
	});

	//Restart GPS driver process if it exits
	f9pDriverProcess.on('exit', (code: number | null) => {
		logger.info("Gps driver process exited with code " + code + ". Trying to restart...")

		connectF9pDriver();
	})

	logger.info('gps output hookup...')
}

/*
Disconnect f9p driver application
*/
const disconnectF9pDriver = () => {
	f9pDriverProcess && logger.info(f9pDriverProcess.kill()) && (f9pDriverProcess = null)
}

// Update main process
setInterval(() => process.send && process.send(mainProcessDataObject), 150)

// Unlink files assosiated with sockets
const unlinkSocketFiles = () => {
	if (fs.existsSync(syncDataSocketName)) {
		logger.info('trying to remove ' + syncDataSocketName)
		fs.unlinkSync(syncDataSocketName)
	}
}

// Improved exit handler with types
const exitHandler = (options: { cleanup?: boolean; exit?: boolean }, exitCode?: number): void => {
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
        console.info(`Exit Code (nodejs): ${exitCode}`);
    }

    // Exit the process if the "exit" flag is set
    if (options.exit) {
        process.exit();
    }
};

// Do something when the app is closing (exit event)
process.on('exit', () => exitHandler({ cleanup: true }));

// Handle ctrl+c event (SIGINT)
process.on('SIGINT', () => exitHandler({ exit: true }));

// Handle "kill pid" (e.g., nodemon restart) signals (SIGUSR1, SIGUSR2)
process.on('SIGUSR1', () => exitHandler({ exit: true }));
process.on('SIGUSR2', () => exitHandler({ exit: true }));

// Handle uncaught exceptions
process.on('uncaughtException', (err: Error) => {
    logger.error('Uncaught Exception:', err);
    exitHandler({ exit: true });
});

main();