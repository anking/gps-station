//Imports
const SerialPort = require('serialport');
const GPS = require('gps')
const net = require('net');
const fs = require('fs')
const { exec } = require('child_process');
const _ = require('lodash');
const rl = require('readline');

//Create objects
const gps = new GPS;
const nmeaDataSocketName = 'zed-f9p-nmea-data.sock';
const rtcmDataSocketName = 'zed-f9p-rtcm-data.sock';
const syncDataSocketName = 'zed-f9p-sync-data.sock';
var processDataObject = {		//this object is being used to send data to the main process
	lat: null,
	lon: null,
	survey_time: null,
	accuracy: null,
	survey_valid: false
};

//SETTINGS
const ntripServer = 'rtk2go.com';
const ntripPassword = '6n9c2TxqKwuc';
const ntripMountpoint = 'Wexford';
const ntripPort = 2101;
const gpsAccuracy = 3.000;		//in meters
const gpsSurveyTime = 60;		//in seconds	

//local vars
let serialDevice = null;
let nmeaDataSocket = null;		//data socket for incoming raw nmea data
let rtcmDataSocket = null;		//data socket for incoming raw rtcm data
let syncDataSocket = null;		//data socket for internal data commands rather than rtcm. Packets of data in this socket are just plain strings separated by \r\n
let childF9pProcess = null;		//process hangler for f9p driver

//Wrap everything in async function for proper await handling
(async () => {

	// Check if receiving socket for communication with f9p application can be opened(if a file from eprivious connection exists it may be a problem)
	try {
		if (fs.existsSync('/tmp/' + nmeaDataSocketName) || fs.existsSync('/tmp/' + syncDataSocketName) || fs.existsSync('/tmp/' + syncDataSocketName)) {
			//file exists/ socket cannot be opened
			console.log('Node receiving sockets cannot be opened because temporary files that were created for it was never removed from /tmp directory')

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
		socket.on('data', c => gps.updatePartial(c)); //send character to gps data parser
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
			if(line.includes(':')){
				let command = line.split(':');

				switch(command[0]){
					case 'SURVEY_TIME': processDataObject.survey_time = command[1]; break;
					case 'ACCURACY': processDataObject.accuracy = command[1]; break;
					case 'SURVEY_VALID': processDataObject.survey_valid = command[1]; break;
					default: console.log('command undefined:'+command[0]);
				}
			}
		});
	});

	//Start listening on a changed for this socket
	syncDataSocket.listen('/tmp/' + syncDataSocketName);




	/*
	Start F9p module reader (.NET application)
	*/
	console.log('Starting f9p driver application...')
	let runCommand = __dirname+'/f9p/Zedf9p -server -com-port ' + serialDevice.path + '  -ntrip-server ' + ntripServer + ' -ntrip-password ' + ntripPassword + ' -ntrip-port ' + ntripPort + ' -ntrip-mountpoint ' + ntripMountpoint + ' -rtcm-accuracy-req ' + gpsAccuracy + ' -rtcm-survey-time ' + gpsSurveyTime
	console.log('>'+runCommand);
	childF9pProcess = exec(runCommand, 
	(error, stdout, stderr) => {
		if (error) {
			//some error occurred
			console.error('Error while starting driver: ' + error);
			process.exit();
		} else {
			// the *entire* stdout and stderr (buffered)
			console.log('stdout: ' + stdout);
			console.log('stderr: ' + stderr);
		}
	});

	console.log('gps output hookup...')

	//GPS parser received data and processes it
	//wire up data event handler
	gps.on('data', data => {
		if (data.lat && data.lon) {
			processDataObject.lat = data.lat;
			processDataObject.lon = data.lon;

			//console.log(data.lat, data.lon)

			//write message to parent caller
			//process.send && process.send({ lat: data.lat, lon: data.lon })
		}
	});

	//commands comming from the http server side
	process.on('message', msg => {
		// if (msg === 'gps off') gps.off('data');
		// if (msg === 'gps on') gps.on('data', gpsOutput)
		// if (msg === 'rtcm') {
		// 	console.log('rtcm signal received by gps module')


		// }
	})
})();

// Update main process
setInterval(() => process.send && process.send(processDataObject), 150)

//Do any socket cleanup before this app exits
const exitHandler = (options, exitCode) => {
	//if (options.cleanup) console.log('clean');

	//terminate child process
	childF9pProcess && childF9pProcess.kill('SIGINT');

	//close unix sockets
	nmeaDataSocket && nmeaDataSocket.close();
	rtcmDataSocket && rtcmDataSocket.close();
	syncDataSocket && syncDataSocket.close();

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