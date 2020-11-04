const Raspi = require('raspi');
const I2C = require('raspi-i2c').I2C;
const ADS1x15 = require('raspi-kit-ads1x15');
const Async = require('async');
const _ = require('lodash');

//import custom lodash methods
//var at = require('lodash/at');
//var mapValues = require('lodash/fp/mapValues'); - does not work for some reason returns empty object
//var fp = require('lodash/fp');

let adc; //set Analog-digital conv
const channels={
	CHANNEL_0:[],
	CHANNEL_1:[],
	CHANNEL_2:[],
	CHANNEL_3:[]
};

// Init Raspi Modules and ADC
Raspi.init(() => {
	// Init Raspi-I2c
	const i2c = new I2C();

	// Init the ADC
	adc = new ADS1x15({
		i2c,                                    // i2c interface
		chip: ADS1x15.chips.IC_ADS1115,         // chip model
		address: ADS1x15.address.ADDRESS_0x48,  // i2c address on the bus

		// Defaults for future readings
		pga: ADS1x15.pga.PGA_4_096V,            // power-gain-amplifier range
		sps: ADS1x15.spsADS1115.SPS_860         // data rate (samples per second)
	});

	//Get data every 20ms
	setInterval(getVoltage,20);
});

//Get readings from ADC
function getVoltage(){
	//Get reading from all 4 channels in series
	Async.eachSeries(
	  Object.keys(channels),
	  (channel, nextChannel) => {
		adc.readChannel(ADS1x15.channel[channel], (err, value, volts) => {
		  if (!err) {
			  channels[channel].unshift(value); //put new value into beginning of array
			  if(channels[channel].length>100) channels[channel].pop(); //remove last element
		  }
		  nextChannel(err);
		})
	  },
	  (err) => {
		  //console.log(channels);
	  }
	);
}

//Send average data to main process every quarter second
setInterval(()=>{
	//calculate average value and send
	if(process.send) process.send(
		_.mapValues(channels, channel => channel.reduce( ( p, c ) => p + c, 0 ) / channel.length)
	);
}, 250);