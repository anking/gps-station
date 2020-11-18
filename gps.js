//Imports
const SerialPort = require('serialport');
const GPS = require('gps')
const net = require('net');
const fs = require('fs')
const { exec, spawn } = require('child_process');
const _ = require('lodash');
const rl = require('readline');

//SETTINGS
const ntripServer = 'rtk2go.com';
const ntripPassword = '6n9c2TxqKwuc';
const ntripMountpoint = 'Wexford';
const ntripPort = 2101;
let gpsAccuracy = 3.000;		//in meters
let gpsSurveyTime = 60;		//in seconds	

//Create objects
let gps = null;
const nmeaDataSocketName = 'zed-f9p-nmea-data.sock';
const rtcmDataSocketName = 'zed-f9p-rtcm-data.sock';
const syncDataSocketName = 'zed-f9p-sync-data.sock';
var processDataObject = {		//this object is being used to send data to the main process
	lat: null,
	lon: null,
	survey_time: null,
	accuracy: null,
	survey_valid: false,
	accuracy_setting: gpsAccuracy
};

//local vars
let serialDevice = null;
let nmeaDataSocket = null;		//data socket for incoming raw nmea data
let rtcmDataSocket = null;		//data socket for incoming raw rtcm data
let syncDataSocket = null;		//data socket for internal data commands rather than rtcm. Packets of data in this socket are just plain strings separated by \r\n
let f9pDriverProcess = null;		//process hangler for f9p driver

//Wrap everything in async function for proper await handling
const main = async () => {

	// Check if receiving socket for communication with f9p application can be opened(if a file from eprivious connection exists it may be a problem)
	try {
		if (fs.existsSync('/tmp/' + nmeaDataSocketName) || fs.existsSync('/tmp/' + rtcmDataSocketName) || fs.existsSync('/tmp/' + syncDataSocketName)) {
			//file exists/ socket cannot be opened
			console.log('Node receiving sockets cannot be opened because temporary files that were created for it was never removed from /tmp directory')

			unlinkSocketFiles();
		} else {
			console.log('Receive sockets can be opened successfully')
		}
	} catch (err) {
		console.error(err)
		console.log('unable to remove socket file(s), gps cannot be started')
		process.exit();
	}


	/*
	Find GPS device by hardware ID's
	*/
	try {
		//get list of all serial devices
		info = await SerialPort.list()

		//look for the one that matches our hardware ID's
		serialDevice = _.find(info, device => device.vendorId === '1546' && device.productId.toLowerCase() === '01a9');

		if (serialDevice) {
			console.log('Serial device that looks like Zed-F9p found on ' + serialDevice.path);
		}
		else {
			//No device that matches vendor and ID found connected
			console.log('GPS Error: It does not appear that GPS Module is connected');
			process.exit();
		}
	} catch (err) {
		console.error(err)
		console.log('unable to find serial device that fits specs')
		process.exit();
	}




	/*
	Open unix socket for interprocess communications(connection with .NET application that configures module)

	Socket for RTCM DATA
	*/
	rtcmDataSocket = net.createServer(socket => {
		socket.on('data', c => {
			//console.log(c.toString());
		});
	});

	//Start listening on a changed for this socket
	rtcmDataSocket.listen('/tmp/' + rtcmDataSocketName);


	/*
	Open unix socket for interprocess communications(connection with .NET application that configures module)

	Socket for NMEA data
	*/
	nmeaDataSocket = net.createServer(socket => {
		try {
			socket.on('data', c => gps && gps.updatePartial(c)); //send character to gps data parser
		} catch (e) {
			console.log("Caught GPS lib error: " + JSON.stringify(e));
		}
	});

	//Start listening on a changed for this socket
	nmeaDataSocket.listen('/tmp/' + nmeaDataSocketName);

	/*
	Open unix socket for interprocess communications(connection with .NET application that configures module)

	Socket for SYNC commands:
	incoming: ACCURACY,SURVEY_VALID,SURVEY_TIME
	outgoing:

	commands separated by \r\n
	*/
	syncDataSocket = net.createServer(socket => {

		//create interface for reading one line at a time
		let rli = rl.createInterface(socket, socket);

		//write line in a console for now
		rli.on('line', line => {
			//console.log(line)
			if (line.includes(':')) {
				let command = line.split(':');

				switch (command[0]) {
					case 'SURVEY_TIME': processDataObject.survey_time = command[1]; break;
					case 'ACCURACY': processDataObject.accuracy = command[1]; break;
					case 'SURVEY_VALID': processDataObject.survey_valid = command[1]; break;
					default: console.log('command undefined:' + command[0]);
				}
			}
		});
	});

	//Start listening on a changed for this socket
	syncDataSocket.listen('/tmp/' + syncDataSocketName);

	//connect f9p driver .net core application
	connectF9pDriver();

	//console.log('gps output hookup...')	
	//wire up data event handler
	//gps.on('data', gpsOutput);

	//commands comming from the http server side
	process.on('message', msg => {
		if (msg.includes('RESTART_SURVEY')) {
			let restartSettings = msg.split(':');
			//console.log(restartSettings[0], restartSettings[1])

			//set new survey parameters and restart gps driver
			gpsAccuracy = restartSettings[1] || 3;

			//update accuracy in outgoing object
			processDataObject.accuracy_setting = gpsAccuracy;

			//restart driver
			disconnectF9pDriver();

			//wait a bit before restarting
			setTimeout(connectF9pDriver, 250);
		}
		// if (msg === 'gps off') gps.off('data');
		// if (msg === 'gps on') gps.on('data', gpsOutput)
		// if (msg === 'rtcm') {
		// 	console.log('rtcm signal received by gps module')


		// }
	})
};

//GPS parser received data and processes it
const gpsOutput = data => {
	if (data.lat && data.lon) {
		processDataObject.lat = data.lat;
		processDataObject.lon = data.lon;
	}
}

/*
Start F9p module reader (.NET application)
*/
const connectF9pDriver = () => {
	console.log('Starting f9p driver application...')

	//array of args to call when spawning the proces
	args = [
		'-server', //server operation mode
		'-com-port', serialDevice.path,
		'-ntrip-server', ntripServer,
		'-ntrip-password', ntripPassword,
		'-ntrip-port', ntripPort,
		'-ntrip-mountpoint', ntripMountpoint,
		'-rtcm-accuracy-req', gpsAccuracy,
		'-rtcm-survey-time', gpsSurveyTime,
	]

	f9pDriverProcess = spawn(__dirname + '/f9p/Zedf9p', args);
	//streamIn.pipe(f9pDriverProcess.stdin);

	f9pDriverProcess.stdout.on('data', data => {
		console.log(('F9p Driver: ' + data).trim());
	});

	f9pDriverProcess.stderr.on('data', data => {
		console.error('F9p Driver Error: ' + data);
	});

	f9pDriverProcess.on('close', code => {
		console.log('F9p Driver: child process exited with code ' + code);
	});

	console.log('gps output hookup...')
	gps = new GPS;
	gps.on('data', gpsOutput)
}

/*
Disconnect f9p driver application
*/
const disconnectF9pDriver = () => {

	//disconnect gps listener(otherwice it can cause an application exception that causes crash)
	gps && gps.off() && (gps = null);

	f9pDriverProcess && console.log(f9pDriverProcess.kill()) && (f9pDriverProcess = null)
}

// Update main process
setInterval(() => process.send && process.send(processDataObject), 150)

//Unlink files assosiated with sockets
const unlinkSocketFiles = () => {
	if (fs.existsSync('/tmp/' + rtcmDataSocketName)) {
		console.log('trying to remove /tmp/' + rtcmDataSocketName)
		fs.unlinkSync('/tmp/' + rtcmDataSocketName)
	}

	if (fs.existsSync('/tmp/' + syncDataSocketName)) {
		console.log('trying to remove /tmp/' + syncDataSocketName)
		fs.unlinkSync('/tmp/' + syncDataSocketName)
	}

	if (fs.existsSync('/tmp/' + nmeaDataSocketName)) {
		console.log('trying to remove /tmp/' + nmeaDataSocketName)
		fs.unlinkSync('/tmp/' + nmeaDataSocketName)
	}
}

//Do any socket cleanup before this app exits
const exitHandler = (options, exitCode) => {
	//if (options.cleanup) console.log('clean');

	//terminate child process
	f9pDriverProcess && console.log(f9pDriverProcess.kill());

	//close unix sockets
	nmeaDataSocket && nmeaDataSocket.close();
	rtcmDataSocket && rtcmDataSocket.close();
	syncDataSocket && syncDataSocket.close();

	//remove socket handlers
	unlinkSocketFiles()

	if (exitCode || exitCode === 0) console.log('Exit Code: ' + exitCode);
	if (options.exit) process.exit();
}

//do something when app is closing
process.on('exit', exitHandler.bind(null, { cleanup: true }));

//catches ctrl+c event
process.on('SIGINT', exitHandler.bind(null, { exit: true }));

// catches "kill pid" (for example: nodemon restart)
process.on('SIGUSR1', exitHandler.bind(null, { exit: true }));
process.on('SIGUSR2', exitHandler.bind(null, { exit: true }));

//catches uncaught exceptions
process.on('uncaughtException', exitHandler.bind(null, { exit: true }));

main();