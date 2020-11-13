//Imports
//const SerialPort = require('serialport')
const GPS = require('gps')
const net = require('net');
const fs = require('fs')
//var rl = require('readline');
const { exec } = require('child_process');

// //Create objects
// const serial = new SerialPort('/dev/ttyACM0', { baudRate: 115200 })
const gps = new GPS;
const socketName = 'Zedf9p';
const path = './file.txt'

// Check if receiving socket for communication with f9p application can be opened
try {
	if (fs.existsSync('/tmp/' + socketName + '.sock')) {
		//file exists/ socket cannot be opened
		console.log('node receiving socket cannot be opened because temporary file that was created for it was never removed from /tmp/' + socketName + '.sock')
		console.log('trying to remove it')
		fs.unlinkSync('/tmp/' + socketName + '.sock')
	} else {
		console.log('no file interference, receive socket can be opened successfully')
	}
} catch (err) {
	console.error(err)
	console.log('unable to remove file, gps cannot be started')
	//exitHandler()
	process.exit();
}


// Open unix socket
var server = net.createServer(socket => {
	socket.on('data', c => {
		//console.log(c.toString());
		gps.updatePartial(c)
	});

	//read one line at a time interface
	// var i = rl.createInterface(socket, socket);
	// i.on('line', function (line) {
	// 	//socket.write(line);
	// 	console.log(line)
	// 	//gps.updatePartial(line)
	// 	gps.update(line)
	// });	

	socket.on('end', () => {
		//server.close();
	});
});

//Start listening on a changed for this socket
server.listen('/tmp/' + socketName + '.sock');

// Start F9p module reader application
const childF9pProcess = exec('/home/pi/f9p/Zedf9p -com-port /dev/ttyACM0  -ntrip-server rtk2go.com -ntrip-password 6n9c2TxqKwuc -ntrip-port 2101 -ntrip-mountpoint Wexford -rtcm-accuracy-req 2.000 -rtcm-survey-time 60', (err, stdout, stderr) => {
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

// //serial port receives data from GPS
// serial.on('data', data => {
// 	gps.updatePartial(data)
// })

// serial.on('error', err => {
// 	//console.log(err.message);
// 	process.send({ error: err.message })
// })

process.on('message', msg => {
	// if (msg === 'gps off') gps.off('data');
	// if (msg === 'gps on') gps.on('data', gpsOutput)
	// if (msg === 'rtcm') {
	// 	console.log('rtcm signal received by gps module')


	// }
})


//Do any socket cleanup before this app exits
function exitHandler(options, exitCode) {
	//if (options.cleanup) console.log('clean');

	//terminate child process
	childF9pProcess && childF9pProcess.kill('SIGINT');

	//close unix socket
	server && server.close();

	if (exitCode || exitCode === 0) console.log(exitCode);
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