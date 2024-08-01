from enum import Enum
from typing import Optional, Tuple, ByteString

import time

import RPi.GPIO as GPIO
import pigpio
import spidev

from threading import Thread, Event, Lock
from queue import SimpleQueue

from st7735lcd.st7735lcd import SpiDriver, LcdDisplay, OutPinWrapper, Logger
from ccs811co2.ccs811co2 import I2cDriver, CO2Meter

class LcdAsyncTransactor(LcdDisplay):
    class TransactionType(Enum):
        READ = 0
        WRITE = 1

    _TRANSACTION_TIMEOUT_SEC = 60

    def __init__(self, spi: SpiDriver, rst_pin: OutPinWrapper, width: int, height: int, rotation: int, logger: Logger) -> None:
        super().__init__(spi, rst_pin, width, height, rotation, logger)
        self._transactions_queue = SimpleQueue()
        self._read_mutex = Lock()
        self._write_mutex = Lock()
        self._read_event = Event()
        self._read_data = b""
        self._thread = None
        self._run()
    
    def write(
        self, command: Optional[int] = None, data: Optional[ByteString] = None
    ) -> None:
        """SPI write to the device: commands and data. Arg data should be either None or non-empty byte string. Non-blocking func"""
        with self._write_mutex:
            self._transactions_queue.put((LcdAsyncTransactor.TransactionType.WRITE, command, data))

    def read(self, command: Optional[int] = None, count: int = 0) -> ByteString:
        """SPI read from device with optional command. Blocking func"""
        with self._read_mutex:
            self._read_data = b""
            self._read_event.clear()
            self._transactions_queue.put((LcdAsyncTransactor.TransactionType.READ, command, count))
            self._read_event.wait(timeout=self._TRANSACTION_TIMEOUT_SEC)
            return self._read_data
    
    def _transactions_thread(self):
        '''Aux method'''
        while True:
            transaction, arg1, arg2 = self._transactions_queue.get(block=True)
            if transaction is LcdAsyncTransactor.TransactionType.READ:
                self._read_data = super(LcdAsyncTransactor, self).read(arg1, arg2)
                self._read_event.set()
            else:
                super(LcdAsyncTransactor, self).write(arg1, arg2)

    def _run(self):
        '''Transactions handle thread'''
        self._thread = Thread(target=self._transactions_thread, daemon=True)
        self._thread.start()


class RectWidget:
    def __init__(self,
        lcd: LcdDisplay,
        parent: "RectWidget | None",
        relx: int,
        rely: int,
        width: int,
        height: int,
        color: int,
        ):

        self._parent = parent
        self._children = []
        self._lcd = lcd
        self.color = color
        self.x0 = (self._parent.x0 if self._parent else 0) + relx
        self.x1 = self.x0 + width
        self.y0 = (self._parent.y0 if self._parent else 0) + rely
        self.y1 = self.y0 + height
        assert(self.x0 <= self.x1)
        assert(self.y0 <= self.y1)
        if self._parent:
            self._parent.add_child(self)
        self.need_redraw = True
    
    def add_child(self, child: "RectWidget") -> None:
        self._children.append(child)
    
    def draw(self):
        self._lcd.fill_rectangle(self.x0, self.y0, self.x1, self.y1, self.color)
        self.need_redraw = False

    def draw_recursive(self):
        # redraw only necessary items
        if self.need_redraw:
            self.draw()
        for child in self._children:
            child.draw_recursive()

    def bbox(self) -> Tuple[int]:
        return (self.x0, self.y0, self.x1, self.y1)


class TextLabel(RectWidget):
    def __init__(
    self,
    lcd: LcdDisplay,
    parent: RectWidget,
    relx: int,
    rely: int,
    width: int,
    height: int,
    font_color: int,
    bg_color: int,
    text: str = ""
    ):
        super().__init__(lcd, parent, relx, rely, width, height, bg_color)
        self.text = text
        self._font_color = font_color
    
    def draw(self):
        image_size = (self.x1 - self.x0, self.y1 - self.y0)
        text_size = max(8, image_size[1] // (self.text.strip().count('\n') + 1) - 2)
        self._lcd.draw_text(self.text, text_size, image_size, (self.x0, self.y0), self._font_color, self.color)
        self.need_redraw = False
    
    @property
    def text(self) -> str:
        """Return current text"""
        return self._text

    @text.setter
    def text(self, value):
        self._text = value
        self.need_redraw = True


class CO2Widget(RectWidget):
    def __init__(
    self,
    lcd: LcdDisplay,
    parent: RectWidget,
    relx: int,
    rely: int,
    width: int,
    height: int,
    font_color: int,
    bg_color: int,
    co2meter: CO2Meter
    ):
        super().__init__(lcd, parent, relx, rely, width, height, bg_color)
        self.text = ""
        self._font_color = font_color
        self._co2meter = co2meter

        self._co2meter.check_devid()
        self._co2meter.read_status()
        self._co2meter.check_errid()
        self._co2meter.set_app_mode()
        
        status = self._co2meter.read_status()

        fw_mode = self._co2meter.get_field(status, self._co2meter.STATUS_REG_FW_MODE_FIELD)
        if not fw_mode:
            raise RuntimeError("co2: wrong fw_mode:", fw_mode)
        if self._co2meter.get_field(status, self._co2meter.STATUS_REG_ERROR_FIELD):
            self._co2meter.check_errid()
            raise RuntimeError("co2: got err bit")        

        self._co2meter.setmeas_mode(self._co2meter.DRIVE_MODE_1SEC)

        self._eco2, self._tvoc = 0, 0
    
    def draw(self):
        status = self._co2meter.read_status()
        has_new_val = self._co2meter.get_field(status, self._co2meter.STATUS_REG_DATA_READY_FIELD)
        if self._co2meter.get_field(status, self._co2meter.STATUS_REG_ERROR_FIELD):
            self._co2meter.check_errid()
            raise RuntimeError("co2: got err bit")  
        if has_new_val:
            self._eco2, self._tvoc = self._co2meter.read_meas()

        self.text = f"eCO2={self._eco2} ppm,\nTVOC={self._tvoc} ppb"
        image_size = (self.x1 - self.x0, self.y1 - self.y0)
        text_size = max(8, image_size[1] // (self.text.strip().count('\n') + 1) - 2)
        self._lcd.draw_text(self.text, text_size, image_size, (self.x0, self.y0), self._font_color, self.color)
    
    @property
    def text(self) -> str:
        """Return current text"""
        return self._text

    @text.setter
    def text(self, value):
        self._text = value
        self.need_redraw = True



if __name__ == "__main__":
    
    GPIO.setmode(GPIO.BCM)
    status_led = OutPinWrapper(26)

    try: 
        status_led.value = 1

        # lcd
        spi_dev = spidev.SpiDev()
        spi_dev.open(bus=0, device=0)
        spi_dev.max_speed_hz = 1000000
        dc_pin = OutPinWrapper(25)
        rst_pin = OutPinWrapper(24)
        spi_logger = Logger("spi", verbosity=Logger.Verbosity.MIN)
        spi = SpiDriver(spi_dev, dc_pin, logger=spi_logger)
        lcd = LcdAsyncTransactor(spi, rst_pin, 128, 160, rotation=180, logger=Logger("lcd", verbosity=Logger.Verbosity.MED))

        lcd.init()

        # co2
        pi = pigpio.pi()
        i2c_device = pi.i2c_open(1, 0x5a)
        i2c = I2cDriver(pi, i2c_device, logger=Logger("i2c", verbosity=Logger.Verbosity.MIN))
        co2meter = CO2Meter(i2c, logger=Logger("co2", verbosity=Logger.Verbosity.MED))

        status_led.value = 0

        time.sleep(0.2)
        res = spi.read(LcdDisplay._RDDID, 4)
        spi.write(LcdDisplay._NOP, None)
        print("Display ID:", res)

        main_widget = RectWidget(lcd, None, 0, 0, lcd.width, lcd.height, lcd.COLOR_BLACK)
        date_widget = TextLabel(lcd, main_widget, 0, 0, lcd.width, 43, font_color=lcd.COLOR_WHITE, bg_color=lcd.COLOR_BLACK)
        text_widget = TextLabel(lcd, main_widget, 0, 145, lcd.width, 15, font_color=lcd.COLOR_WHITE, bg_color=lcd.COLOR_BLACK, text="CO2 smart watch")
        co2_widget = CO2Widget(lcd, main_widget, 0, 69, lcd.width, 28, font_color=lcd.COLOR_WHITE, bg_color=lcd.COLOR_BLACK, co2meter=co2meter)
        
        while True:
            date_widget.text = time.strftime('%d %b %Y\n%H:%M:%S\n%A')
            main_widget.draw_recursive()
            time.sleep(0.2)

    finally:
        print("Releasing resources...")
        status_led.value = 0
        if i2c_device is not None:
            pi.i2c_close(i2c_device)
            print("i2c bus closed...")
        GPIO.cleanup()
        spi_dev.close()
        GPIO.cleanup()
