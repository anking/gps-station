//Imports
//const SerialPort = require('serialport')
const GPS = require('gps')
const net = require('net');
const fs = require('fs')
var rl = require('readline');


const socketName = 'Zedf9p';
const gps = new GPS
const path = './file.txt'

// Check if receiving socket can be opened
try {
  if (fs.existsSync(path)) {
	//file exists/ socket cannot be opened
	console.log('node receiving socket cannot be opened because temporary file that was created for it was never removed from /tmp/'+socketName+'.sock')
  }
} catch(err) {
  console.error(err)
}


// Open unix socket
var server = net.createServer(socket => {
	socket.on('data', c => {
		//console.log(c.toString());

	});

	var i = rl.createInterface(socket, socket);
	i.on('line', function (line) {
		//socket.write(line);
		console.log(line)
		gps.updatePartial(line)
	});

	socket.on('end', () => {
		//server.close();
	});
});

server.listen('/tmp/'+socketName+'.sock');

//var stream = net.connect('/tmp/Zedf9p.sock');
//stream.write('hello');
//stream.end();

// var path = require("path");

// var server = net.createServer(function (client) {
//     client.on('data', function (data) {
//         console.log("data: " + data.toString());
//     });
// });

// server.listen(path.join('\\\\.\\pipe', pipeName), function() {
//     console.log("connected");
// });

// //Create objects
// const serial = new SerialPort('/dev/ttyACM0', { baudRate: 115200 })
// const gps = new GPS

//GPS parser received data and processes it
const gpsOutput = data => {
	if (data.lat && data.lon) {
		console.log(data.lat, data.lon)

		//write message to parent caller
		process.send({ lat: data.lat, lon: data.lon })
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
	
	//close unix socket
	server && server.close();

    if (exitCode || exitCode === 0) console.log(exitCode);
    if (options.exit) process.exit();
}

//do something when app is closing
process.on('exit', exitHandler.bind(null,{cleanup:true}));

//catches ctrl+c event
process.on('SIGINT', exitHandler.bind(null, {exit:true}));

// catches "kill pid" (for example: nodemon restart)
process.on('SIGUSR1', exitHandler.bind(null, {exit:true}));
process.on('SIGUSR2', exitHandler.bind(null, {exit:true}));

//catches uncaught exceptions
process.on('uncaughtException', exitHandler.bind(null, {exit:true}));