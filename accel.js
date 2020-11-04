var lsm303 = require('lsm303');
var ls  = new lsm303();
const _ = require('lodash');

var accel = ls.accelerometer();
var mag = ls.magnetometer();
var data = {heading:[]}

accel.readAxes(function(err,axes){
    if(err){
        console.log("Error reading Accelerometer Axes : " + err);
    }
    if (axes) {
        //console.log(axes);
    }
});

//read heading periodically
setInterval(()=>{
	mag.readHeading(function(err, heading){
      if(err){
         console.log("Error reading Magnetometer Heading : " + err);
      }   
      if (heading) {
		data.heading.unshift(heading); //put new value into beginning of array
		if(data.heading.length>40) data.heading.pop(); //remove last element
      }   
    });
}, 25);

//Send average data to main process every quarter second
setInterval(()=>{
	//calculate average value and send
	//if(process.send) process.send(data);
	if(process.send) process.send(_.mapValues(data, values => values.reduce( ( p, c ) => p + c, 0 ) / values.length))
}, 250);