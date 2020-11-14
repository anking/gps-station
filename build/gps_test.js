"use strict";
// //Imports
var SerialPort = require('serialport');
var Readline = require('@serialport/parser-readline');
var _ = require('lodash');
var _a = require('bitwise-buffer'), xor = _a.xor, and = _a.and, or = _a.or, nor = _a.nor, not = _a.not, leftShift = _a.leftShift, rightShift = _a.rightShift, lshift = _a.lshift, rshift = _a.rshift;
var Serial = null; //this cannot be const
var lineParser = new Readline();
var packetCfg = {};
connectSerial();
//connect serial port
function connectSerial() {
    SerialPort.list()
        .then(function (info) {
        //output info about all serisl devices
        //console.log(info)
        //Find our device
        var device = _.find(info, function (device) { return device.vendorId === '1546' && device.productId.toLowerCase() === '01a9'; });
        if (device) {
            console.log('Serial device that looks like ours found on ' + device.path);
            //Find our device and initialize it
            Serial = new SerialPort(device.path, { baudRate: 115200 });
            //when serial port receives data from the module send it to gps parser
            Serial.on('data', function (data) {
                //console.log('serial data received')
                console.log(data);
            });
            //If port error happened
            Serial.on('error', function (err) {
                //console.log(err)
                console.log('Oops, serial port error occured: ' + err.message);
            });
            //If port is closed
            Serial.on('close', function (info) {
                //console.log(err);
                console.log('Oops, looks like serial port got disconnected');
            });
            //Create serial port parser for NMEA strings
            //Serial.pipe(lineParser); //this parser freezes for some reason
            //console log parsed NMEA strings if needed
            //lineParser.on('data',console.log);
            enableRTCMmessage(UBX_RTCM_1074, COM_PORT_I2C, 1);
        }
        else {
            //No device that matches vendor and ID found connected
            console.log('GPS Error: It does not appear that GPS Module is connected');
        }
    })
        .catch(console.log);
}
;
//Registers
var UBX_SYNCH_1 = Buffer.from('B5', 'hex'); //(0xB5);
var UBX_SYNCH_2 = Buffer.from('62', 'hex');
var UBX_RTCM_1074 = Buffer.from('4A', 'hex'); //GPS MSM4
var COM_PORT_I2C = Buffer.from('00', 'hex');
var COM_PORT_UART1 = Buffer.from('01', 'hex');
var COM_PORT_UART2 = Buffer.from('02', 'hex');
var COM_PORT_USB = Buffer.from('03', 'hex');
var COM_PORT_SPI = Buffer.from('04', 'hex');
var UBX_RTCM_MSB = Buffer.from('F5', 'hex'); //All RTCM enable commands have 0xF5 as MSB
var UBX_CLASS_CFG = Buffer.from('06', 'hex'); //Configuration Input Messages: Configure the receiver.
var UBX_CFG_MSG = Buffer.from('01', 'hex'); //Poll a message configuration, or Set Message Rate(s), or Set Message Rate
var Status;
(function (Status) {
    Status[Status["SFE_UBLOX_STATUS_SUCCESS"] = 0] = "SFE_UBLOX_STATUS_SUCCESS";
    Status[Status["SFE_UBLOX_STATUS_FAIL"] = 1] = "SFE_UBLOX_STATUS_FAIL";
    Status[Status["SFE_UBLOX_STATUS_CRC_FAIL"] = 2] = "SFE_UBLOX_STATUS_CRC_FAIL";
    Status[Status["SFE_UBLOX_STATUS_TIMEOUT"] = 3] = "SFE_UBLOX_STATUS_TIMEOUT";
    Status[Status["SFE_UBLOX_STATUS_COMMAND_NACK"] = 4] = "SFE_UBLOX_STATUS_COMMAND_NACK";
    Status[Status["SFE_UBLOX_STATUS_OUT_OF_RANGE"] = 5] = "SFE_UBLOX_STATUS_OUT_OF_RANGE";
    Status[Status["SFE_UBLOX_STATUS_INVALID_ARG"] = 6] = "SFE_UBLOX_STATUS_INVALID_ARG";
    Status[Status["SFE_UBLOX_STATUS_INVALID_OPERATION"] = 7] = "SFE_UBLOX_STATUS_INVALID_OPERATION";
    Status[Status["SFE_UBLOX_STATUS_MEM_ERR"] = 8] = "SFE_UBLOX_STATUS_MEM_ERR";
    Status[Status["SFE_UBLOX_STATUS_HW_ERR"] = 9] = "SFE_UBLOX_STATUS_HW_ERR";
    Status[Status["SFE_UBLOX_STATUS_DATA_SENT"] = 10] = "SFE_UBLOX_STATUS_DATA_SENT";
    Status[Status["SFE_UBLOX_STATUS_DATA_RECEIVED"] = 11] = "SFE_UBLOX_STATUS_DATA_RECEIVED";
    Status[Status["SFE_UBLOX_STATUS_I2C_COMM_FAILURE"] = 12] = "SFE_UBLOX_STATUS_I2C_COMM_FAILURE";
    Status[Status["SFE_UBLOX_STATUS_DATA_OVERWRITTEN"] = 13] = "SFE_UBLOX_STATUS_DATA_OVERWRITTEN"; // This is an error - the data was valid but has been or _is being_ overwritten by another packet
})(Status || (Status = {}));
var _printDebug = true;
//Given a message, calc and store the two byte "8-Bit Fletcher" checksum over the entirety of the message
//This is called before we send a command message
function calcChecksum(msg) {
    if (msg.len) {
        msg.checksumA = Buffer.from('00', 'hex');
        msg.checksumB = Buffer.from('00', 'hex');
        msg.checksumA = and(msg.checksumA, msg.cls);
        msg.checksumB = and(msg.checksumB, msg.checksumA);
        msg.checksumA = and(msg.checksumA, msg.id);
        msg.checksumB = and(msg.checksumB, msg.checksumA);
        msg.checksumA = and(msg.checksumA, and(msg.len, Buffer.from('FF', 'hex')));
        msg.checksumB = and(msg.checksumB, msg.checksumA);
        msg.checksumA = and(msg.checksumA, rshift(msg.len, 8));
        msg.checksumB = and(msg.checksumB, msg.checksumA);
        // for (var i = 0; i < msg.len.readInt16BE(); i++) {
        // 	msg.checksumA = msg.payload[i];
        // 	msg.checksumB = msg.checksumA;
        // }
    }
}
var sendSerialCommand = function (outgoingUBX) {
    //Write header bytes
    Serial.write(UBX_SYNCH_1, 'hex'); //μ - oh ublox, you're funny. I will call you micro-blox from now on.
    Serial.write(UBX_SYNCH_2, 'hex'); //b
    Serial.write(outgoingUBX.cls, 'hex');
    Serial.write(outgoingUBX.id, 'hex');
    Serial.write(and(outgoingUBX.len, Buffer.from('FF', 'hex')), 'hex'); //LSB
    Serial.write(rshift(outgoingUBX.len, 8), 'hex'); //MSB
    //Write payload.
    //   for (int i = 0; i < outgoingUBX->len; i++)
    //   {
    //   serial.write(outgoingUBX->payload[i]);
    //   }
    //Write checksum
    Serial.write(outgoingUBX.checksumA, 'hex');
    Serial.write(outgoingUBX.checksumB, 'hex');
};
function sendCommand(outgoingUBX, maxWait) {
    var retVal = Status.SFE_UBLOX_STATUS_SUCCESS;
    calcChecksum(outgoingUBX); //Sets checksum A and B bytes of the packet
    if (_printDebug == true) {
        console.log("Sending: ", outgoingUBX);
    }
    sendSerialCommand(outgoingUBX);
    // if (maxWait > 0) {
    // 	//Depending on what we just sent, either we need to look for an ACK or not
    // 	if (outgoingUBX -> cls == UBX_CLASS_CFG) {
    // 		if (_printDebug == true) {
    // 			_debugSerial -> println(F("sendCommand: Waiting for ACK response"));
    // 		}
    // 		retVal = waitForACKResponse(outgoingUBX, outgoingUBX -> cls, outgoingUBX -> id, maxWait); //Wait for Ack response
    // 	}
    // 	else {
    // 		if (_printDebug == true) {
    // 			_debugSerial -> println(F("sendCommand: Waiting for No ACK response"));
    // 		}
    // 		retVal = waitForNoACKResponse(outgoingUBX, outgoingUBX -> cls, outgoingUBX -> id, maxWait); //Wait for Ack response
    // 	}
    // }
    //return retVal;
    return Status.SFE_UBLOX_STATUS_DATA_RECEIVED;
}
function configureMessage(msgClass, msgID, portID, sendRate, maxWait) {
    //Poll for the current settings for a given message
    packetCfg.cls = UBX_CLASS_CFG;
    packetCfg.id = UBX_CFG_MSG;
    packetCfg.len = Buffer.from('02', 'hex');
    packetCfg.startingSpot = Buffer.from('00', 'hex');
    //payloadCfg[0] = msgClass;
    //payloadCfg[1] = msgID;
    //This will load the payloadCfg array with current settings of the given register
    if (sendCommand(packetCfg, maxWait) != Status.SFE_UBLOX_STATUS_DATA_RECEIVED) // We are expecting data and an ACK
        return (false); //If command send fails then bail
    //Now send it back with new mods
    //packetCfg.len = Buffer.from('8','hex');
    //payloadCfg is now loaded with current bytes. Change only the ones we need to
    //payloadCfg[2 + portID] = sendRate; //Send rate is relative to the event a message is registered on. For example, if the rate of a navigation message is set to 2, the message is sent every 2nd navigation solution.
    //return ((sendCommand(&packetCfg, maxWait)) == Status.SFE_UBLOX_STATUS_DATA_SENT); // We are only expecting an ACK
    return true;
}
function enableRTCMmessage(messageNumber, portID, sendRate, maxWait) {
    if (maxWait === void 0) { maxWait = 0; }
    return (configureMessage(UBX_RTCM_MSB, messageNumber, portID, sendRate, maxWait));
}
// //-=-=-=-=- UBX binary specific variables
// struct ubxPacket
// {
// 	uint8_t cls;
// 	uint8_t id;
// 	uint16_t len;		   //Length of the payload. Does not include cls, id, or checksum bytes
// 	uint16_t counter;	   //Keeps track of number of overall bytes received. Some responses are larger than 255 bytes.
// 	uint16_t startingSpot; //The counter value needed to go past before we begin recording into payload array
// 	uint8_t *payload;
// 	uint8_t checksumA; //Given to us from module. Checked against the rolling calculated A/B checksums.
// 	uint8_t checksumB;
// 	sfe_ublox_packet_validity_e valid;			 //Goes from NOT_DEFINED to VALID or NOT_VALID when checksum is checked
// 	sfe_ublox_packet_validity_e classAndIDmatch; // Goes from NOT_DEFINED to VALID or NOT_VALID when the Class and ID match the requestedClass and requestedID
// } ubxPacket;
// ubxPacket packetAck = {0, 0, 0, 0, 0, payloadAck, 0, 0, SFE_UBLOX_PACKET_VALIDITY_NOT_DEFINED, SFE_UBLOX_PACKET_VALIDITY_NOT_DEFINED};
// ubxPacket packetCfg = {0, 0, 0, 0, 0, payloadCfg, 0, 0, SFE_UBLOX_PACKET_VALIDITY_NOT_DEFINED, SFE_UBLOX_PACKET_VALIDITY_NOT_DEFINED};
