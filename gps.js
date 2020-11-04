//Imports
const SerialPort = require('serialport')
const GPS = require('gps')

//Create objects
const serial = new SerialPort('/dev/ttyACM0', { baudRate: 115200 })
const gps = new GPS

//GPS parser received data and processes it
const gpsOutput = data => {
	if (data.lat && data.lon) {
		//write message to parent caller
		process.send({ lat: data.lat, lon: data.lon })
	}
}

//wire up data event handler
gps.on('data', gpsOutput)

//serial port receives data from GPS
serial.on('data', data => {
	gps.updatePartial(data)
})

serial.on('error', err => {
	//console.log(err.message);
	process.send({ error: err.message })
})

process.on('message', msg => {
	if (msg === 'gps off') gps.off('data');
	if (msg === 'gps on') gps.on('data', gpsOutput)
	if (msg === 'rtcm') gps.on('data', gpsOutput)
})

process.on('sigterm', () => {
	//put gps to sleep?
})