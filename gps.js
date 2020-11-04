//Imports
const SerialPort = require('serialport')
const GPS = require('gps')

//Create objects
const TTYS0 = new SerialPort('/dev/ttyACM0', { baudRate: 115200 })
const gps = new GPS



//wire up data event handler
gps.on('data', gpsOutput)

//serial port receives data from GPS
TTYS0.on('data', data => {
	gps.updatePartial(data)
})

TTYS0.on('error', err => {
	//console.log(err.message);
	process.send({ error: err.message })
})

process.on('message', msg => {
	if (msg === 'gps off') gps.off('data');
	if (msg === 'gps on') gps.on('data', gpsOutput)
})

process.on('sigterm', () => {
	//put gps to sleep?
})

//GPS parser received data and processes it
gpsOutput = data => {
	if (data.lat && data.lon) {
		//write message to parent caller
		process.send({ lat: data.lat, lon: data.lon })
	}
}