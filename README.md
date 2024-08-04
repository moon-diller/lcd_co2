# CO2 smart watch project

## Circuit

## Description
Raspberry Pi Zero 2 reads CO2 data from CO2 meter and draws it on LCD display.
This is how interfaces transactionls look like in real time (data is processed with Logic analyzer and PulseWiew tool):

spi_i2c_seq.pic

Also LcdAsyncTransactor object provides ability to run SPI transactions in background thread, having parallel processing of I2C transactions

spi_i2c_par.pic

## Stand overview
stand.pic

## Dependency
This project uses import RPi.GPIO, pigpio and spidev packages. Also it includes submodules of st7735lcd and ccs811co2 drivers that are heavily based on AdaFruit [1](https://github.com/adafruit/Adafruit_CircuitPython_CCS811/), [2](https://github.com/adafruit/Adafruit_CircuitPython_RGB_Display) and Pimoroni [3](https://github.com/pimoroni/st7735-python) work.
This project does not rely on Micropython or Adafruit CircuitPython.

## Installation
`git clone --recurse-submodules git@github.com:moon-diller/lcd_co2.git`

## Usage
Enable RPi SPI and I2C interfaces.

`sudo pigpiod`

`python3 co2_lcd.py`

## License
