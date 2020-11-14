//Imports
var SerialPort = require('serialport');
const GPS = require('gps')
const net = require('net');
const fs = require('fs')
const { exec } = require('child_process');
var _ = require('lodash');

//Create objects
const gps = new GPS;
const socketName = 'Zedf9p';

//SETTINGS
const ntripServer = 'rtk2go.com';
const ntripPassword = '6n9c2TxqKwuc';
const ntripMountpoint = 'Wexford';
const ntripPort = 2101;
const gpsAccuracy = 3.000;		//in meters
const gpsSurveyTime = 60;		//in seconds	

//local vars
let serialDevice = null;
let server = null;
let childF9pProcess = null;

//Wrap everything in async function for proper await handling
(async () => {

	// Check if receiving socket for communication with f9p application can be opened(if a file from eprivious connection exists it may be a problem)
	try {
		if (fs.existsSync('/tmp/' + socketName + '.sock')) {
			//file exists/ socket cannot be opened
			console.log('Node receiving socket cannot be opened because temporary file that was created for it was never removed from /tmp/' + socketName + '.sock')
			console.log('trying to remove it')
			fs.unlinkSync('/tmp/' + socketName + '.sock')
		} else {
			console.log('Receive socket can be opened successfully')
		}
	} catch (err) {
		console.error(err)
		console.log('unable to remove file, gps cannot be started')
		process.exit();
	}


	//Find GPS device by hardware ID's
	try {
		//get list of all serial devices
		info = await SerialPort.list()

		//look for the one that matches our hardware ID's
		serialDevice = _.find(info, device => device.vendorId === '1546' && device.productId.toLowerCase() === '01a9');

		if (serialDevice) {
			console.log('Serial device that looks like ours found on ' + serialDevice.path);
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

	// Open unix socket for interprocess communications(connection with .NET application that configures module)
	server = net.createServer(socket => {
		socket.on('data', c => {
			//console.log(c.toString());
			gps.updatePartial(c)
		});

		socket.on('end', () => {
			//server.close();
		});
	});

	//Start listening on a changed for this socket
	server.listen('/tmp/' + socketName + '.sock');

	// Start F9p module reader (.NET application)
	childF9pProcess = exec('/home/pi/f9p/Zedf9p -server -com-port ' + serialDevice.path + '  -ntrip-server ' + ntripServer + ' -ntrip-password ' + ntripPassword + ' -ntrip-port ' + ntripPort + ' -ntrip-mountpoint ' + ntripMountpoint + ' -rtcm-accuracy-req ' + gpsAccuracy + ' -rtcm-survey-time ' + gpsSurveyTime, (err, stdout, stderr) => {
		if (err) {
			//some err occurred
			console.error(err)
		} else {
			// the *entire* stdout and stderr (buffered)
			console.log(`stdout: ${stdout}`);
			console.log(`stderr: ${stderr}`);
		}
	});

	//GPS parser received data and processes it
	const gpsOutput = data => {
		if (data.lat && data.lon) {
			console.log(data.lat, data.lon)

			//write message to parent caller
			process.send && process.send({ lat: data.lat, lon: data.lon })
		}
	}

	//wire up data event handler
	gps.on('data', gpsOutput)

	process.on('message', msg => {
		// if (msg === 'gps off') gps.off('data');
		// if (msg === 'gps on') gps.on('data', gpsOutput)
		// if (msg === 'rtcm') {
		// 	console.log('rtcm signal received by gps module')


		// }
	})
})();

//Do any socket cleanup before this app exits
function exitHandler(options, exitCode) {
	//if (options.cleanup) console.log('clean');

	//terminate child process
	childF9pProcess && childF9pProcess.kill('SIGINT');

	//close unix socket
	server && server.close();

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