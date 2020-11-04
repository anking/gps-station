const LCD = require('lcdi2c');

//Create objects
const lcd = new LCD( 1, 0x27, 20, 4 ); //set lcd
//clear LCD
lcd.clear();

process.on('message', (msg) => {
  if(msg.data){
	lcd.println(msg.data.ln0,1);
	lcd.println(msg.data.ln1,2);
    lcd.println(msg.data.ln2,3);
	lcd.println(msg.data.ln3,4);
  }
});