# CO2 smart watch project

## Circuit
![Alt text](pics/board.png?raw=true "board.pic")

## Description
Raspberry Pi Zero 2 reads CO2 data from CO2 meter and draws it on LCD display.

This is how interfaces transactionls look like in real time (data is processed with logic analyzer and PulseView tool):
![Alt text](pics/spi_i2c_seq.png?raw=true "spi_i2c_seq.pic")

Also LcdAsyncTransactor object provides ability to run SPI transactions in background thread, having parallel processing of I2C transactions.
![Alt text](pics/spi_i2c_par.png?raw=true "spi_i2c_par.pic")

## Stand overview
![Alt text](pics/stand.jpg?raw=true "stand.pic")

## Dependency
This project uses import RPi.GPIO, pigpio and spidev packages. Also it includes submodules of st7735lcd and ccs811co2 drivers that are heavily based on AdaFruit [1](https://github.com/adafruit/Adafruit_CircuitPython_CCS811/), [2](https://github.com/adafruit/Adafruit_CircuitPython_RGB_Display) and Pimoroni [3](https://github.com/pimoroni/st7735-python) work.
This project does not rely on Micropython or Adafruit CircuitPython.

## Installation
`git clone https://github.com/moon-diller/lcd_co2.git`

`cd lcd_co2`

`sed  's/git@github.com:/https:\/\/github\.com\//g' -i .gitmodules`

`git submodule update --init`

## Usage
Enable RPi SPI and I2C interfaces.

`sudo pigpiod`

`python3 co2_lcd.py`
