# 🌿 LCD CO₂ Monitor for Raspberry Pi Zero W 2

This project reads CO₂ and TVOC data from a **CCS811 air quality sensor**  
and displays it on a **ST7735 SPI LCD** using a lightweight widget system.  

---

## Circuit
![Alt text](pics/board.png?raw=true "board.pic")

## Description
Raspberry Pi Zero 2 reads CO2 data from CO2 meter and draws it on LCD display.

This is how interfaces transactionls look in real time (data is processed with logic analyzer and PulseView tool):
![Alt text](pics/spi_i2c_seq.png?raw=true "spi_i2c_seq.pic")

Also LcdAsyncTransactor object provides ability to run SPI transactions in background thread, having parallel processing of I2C transactions.
![Alt text](pics/spi_i2c_par.png?raw=true "spi_i2c_par.pic")

## Stand overview
![Alt text](pics/stand.jpg?raw=true "stand.pic")

## Dependency
This project uses import RPi.GPIO, pigpio and spidev packages. Also it includes submodules of st7735lcd and ccs811co2 drivers that are heavily based on AdaFruit [1](https://github.com/adafruit/Adafruit_CircuitPython_CCS811/), [2](https://github.com/adafruit/Adafruit_CircuitPython_RGB_Display) and Pimoroni [3](https://github.com/pimoroni/st7735-python) work.
This project does not rely on Micropython or Adafruit CircuitPython.

## 🛠 Hardware Requirements

- Raspberry Pi Zero W 2 (or similar)
- ST7735 128×160 SPI LCD
- CCS811 I²C CO₂ + TVOC sensor
- Jumper wires

## Installation
`git clone https://github.com/moon-diller/lcd_co2.git`

`cd lcd_co2`

`sed  's/git@github.com:/https:\/\/github\.com\//g' -i .gitmodules`

`git submodule update --init`

## 🔌 Wiring

### LCD → Raspberry Pi
| Display Module  | RPi BCM Pin     |
|-----------------|-----------------|
| VCC             | 3.3V            |
| GND             | GND             |
| CS              | GPIO 8 - CE0    |
| RESET           | GPIO 24         |
| A0              | GPIO 25         |
| SDA             | GPIO 10         |
| SCK             | GPIO 11 - SCLK  |
| LED             | 3.3 V           |

### Raspberry Pi - CCS811 
|  RPi BCM Pin  | CCS811 Pin |
|---------------|------------|
| 3.3V          | VCC        |
| GPIO 2 (SDA)  | SDA        |
| GPIO 3 (SCL)  | SCL        |
| GND           | GND        |
| GND           | WAK        |

## Usage
Enable RPi SPI and I2C interfaces.

`sudo pigpiod`

`python3 co2_lcd.py`

## License
MIT — see LICENSE for details.

## Credits
Inspired by Adafruit and Pimoroni drivers
