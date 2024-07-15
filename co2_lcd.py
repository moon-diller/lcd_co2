import time
from typing import Optional, Union, Tuple, List, Any, ByteString
import struct
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
import numpy
import spidev
import math as m
import pigpio

def color_int_to_tuple(color: int) -> Tuple[int]:
    '''Returns 8bit color tuple'''
    return (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF


def image_to_data(image: Image) -> Any:
    """Generator function to convert a PIL image to 16-bit 565 RGB bytes."""
    # NumPy is much faster at doing this. NumPy code provided by:
    # Keith (https://www.blogger.com/profile/02555547344016007163)
    data = numpy.array(image.convert("RGB")).astype("uint16")
    color = (
        ((data[:, :, 0] & 0xF8) << 8)
        | ((data[:, :, 1] & 0xFC) << 3)
        | (data[:, :, 2] >> 3)
    )
    return numpy.dstack(((color >> 8) & 0xFF, color & 0xFF)).flatten().tolist()


def get_text_image(
    text:str, 
    text_size:int, 
    image_size:Tuple[int], 
    font_color: Tuple[int] = (255, 255, 255),
    bg_color: Tuple[int] = (0, 0, 0)
    ) -> Image:
    '''Returns an image containing printed text'''
    # create an image
    out = Image.new("RGB", size=image_size, color=bg_color)

    # get a font
    fnt = ImageFont.truetype("Pillow/Tests/fonts/FreeMono.ttf", text_size)
    # get a drawing context
    d = ImageDraw.Draw(out)

    # draw multiline text
    d.multiline_text(xy=(0, 0), text=text, font=fnt, fill=font_color)
    return out


class LcdWrapper:
    _NOP = 0x00
    _SWRESET = 0x01
    _RDDID = 0x04
    _RDDST = 0x09

    _SLPIN = 0x10
    _SLPOUT = 0x11
    _PTLON = 0x12
    _NORON = 0x13

    _INVOFF = 0x20
    _INVON = 0x21
    _DISPOFF = 0x28
    _DISPON = 0x29
    _CASET = 0x2A
    _RASET = 0x2B
    _RAMWR = 0x2C
    _RAMRD = 0x2E

    _PTLAR = 0x30
    _COLMOD = 0x3A
    _MADCTL = 0x36

    _FRMCTR1 = 0xB1
    _FRMCTR2 = 0xB2
    _FRMCTR3 = 0xB3
    _INVCTR = 0xB4
    _DISSET5 = 0xB6

    _PWCTR1 = 0xC0
    _PWCTR2 = 0xC1
    _PWCTR3 = 0xC2
    _PWCTR4 = 0xC3
    _PWCTR5 = 0xC4
    _VMCTR1 = 0xC5

    _RDID1 = 0xDA
    _RDID2 = 0xDB
    _RDID3 = 0xDC
    _RDID4 = 0xDD

    _PWCTR6 = 0xFC

    _GMCTRP1 = 0xE0
    _GMCTRN1 = 0xE1


    _COLUMN_SET = _CASET
    _PAGE_SET = _RASET
    _RAM_WRITE = _RAMWR
    _RAM_READ = _RAMRD
    _ENCODE_PIXEL = ">I"
    _ENCODE_POS = ">HH"
    _BUFFER_SIZE = 256
    _DECODE_PIXEL = ">BBB"
    _X_START = 0
    _Y_START = 0

    _RDDPM = 0x0A


    # Colours for convenience
    _COLOR_BLACK = 0x0000  # 0b 00000 000000 00000
    _COLOR_BLUE = 0x001F  # 0b 00000 000000 11111
    _COLOR_GREEN = 0x07E0  # 0b 00000 111111 00000
    _COLOR_RED = 0xF800  # 0b 11111 000000 00000
    _COLOR_CYAN = 0x07FF  # 0b 00000 111111 11111
    _COLOR_MAGENTA = 0xF81F  # 0b 11111 000000 11111
    _COLOR_YELLOW = 0xFFE0  # 0b 11111 111111 00000
    _COLOR_WHITE = 0xFFFF  # 0b 11111 111111 11111


    def __init__(self, spi, width: int, height: int, rotation:int) -> None:
        self._spi = spi
        self.width = width
        self.height = height
        self.rotation = rotation
        self._invert = False
        self._offset_left = 0
        self._offset_top = 0
        self.init()

    def init(self) -> None:
        """Run the initialization commands."""
        # for command, data in self._INIT:
        #     self._spi.write(command, data, delay=0.1)
        # return
        self._spi.write(command=self._SWRESET)    # Software reset
        time.sleep(0.150)                         # delay 150 ms

        self._spi.write(command=self._SLPOUT)     # Out of sleep mode
        time.sleep(0.500)                         # delay 500 ms

         # Frame rate ctrl - normal mode
         # Rate = fosc/(1x2+40) * (LINE+2C+2D)
        self._spi.write(command=self._FRMCTR1, data=b"\x01\x2C\x2D")

        # Frame rate ctrl - idle mode
        # Rate = fosc/(1x2+40) * (LINE+2C+2D)
        self._spi.write(command=self._FRMCTR2, data=b"\x01\x2C\x2D")    

        self._spi.write(command=self._FRMCTR3)    # Frame rate ctrl - partial mode
        self._spi.write(data=b"\x01\x2C\x2D")     # Dot inversion mode
        self._spi.write(data=b"\x01\x2C\x2D")     # Line inversion mode

        self._spi.write(command=self._INVCTR)     # Display inversion ctrl
        self._spi.write(data=b"\x07")             # No inversion

        self._spi.write(command=self._PWCTR1)     # Power control
        self._spi.write(data=b"\xA2\x02\x84")     # -4.6V, auto mode

        self._spi.write(command=self._PWCTR2)     # Power control
        self._spi.write(data=b"\x0A\x00")         # Opamp current small, Boost frequency

        self._spi.write(command=self._PWCTR4)     # Power control
        self._spi.write(data=b"\x8A\x2A")         # BCLK/2, Opamp current small & Medium low

        self._spi.write(command=self._PWCTR5)     # Power control
        self._spi.write(data=b"\x8A\xEE")

        self._spi.write(command=self._VMCTR1)     # Power control
        self._spi.write(data=b"\x0E")

        if self._invert:
            self._spi.write(command=self._INVON)   # Invert display
        else:
            self._spi.write(command=self._INVOFF)  # Don't invert display

        self._spi.write(command=self._MADCTL)     # Memory access control (directions)
        self._spi.write(data=b"\xC0")             # row addr/col addr, bottom to top refresh; Set D3 RGB Bit to 0 for format RGB

        self._spi.write(command=self._COLMOD)     # set color mode
        self._spi.write(data=b"\x05")                 # 16-bit color

        self._spi.write(command=self._CASET)      # Column addr set
        self._spi.write(data=b"\x00")                 # XSTART = 0
        self._spi.write(data=str(self._offset_left).encode())
        self._spi.write(data=b"\x00")                 # XEND = ROWS - height
        self._spi.write(data=str(self.width + self._offset_left - 1).encode())

        self._spi.write(command=self._RASET)      # Row addr set
        self._spi.write(data=b"\x00")                 # XSTART = 0
        self._spi.write(data=str(self._offset_top).encode())
        self._spi.write(data=b"\x00")                 # XEND = COLS - width
        self._spi.write(data=str(self.height + self._offset_top - 1).encode())

        self._spi.write(command=self._GMCTRP1)    # Set Gamma
        self._spi.write(data=b"\x02\x1c\x07\x12\x37\x32\x29\x2d")
        self._spi.write(data=b"\x29\x25\x2B\x39\x00\x01\x03\x10")
       

        self._spi.write(command=self._GMCTRN1)    # Set Gamma
        self._spi.write(data=b"\x03\x1d\x07\x06\x2E\x2C\x29\x2D")
        self._spi.write(data=b"\x2E\x2E\x37\x3F\x00\x00\x02\x10")

        self._spi.write(command=self._NORON)      # Normal display on
        time.sleep(0.10)                # 10 ms

        self.display_on()
        time.sleep(0.100)               # 100 ms

        print("lcd: initialized")

    def display_off(self):
        self._spi.write(command=self._DISPOFF)

    def display_on(self):
        self._spi.write(command=self._DISPON)

    def sleep(self):
        self._spi.write(command=self._SLPIN)

    def wake(self):
        self._spi.write(command=self._SLPOUT)

    def fill_rectangle(
        self, x: int, y: int, width: int, height: int, color: Union[int, Tuple]
    ) -> None:
        """Draw a rectangle at specified position with specified width and
        height, and fill it with the specified color."""
        print(f"lcd rect: {x},{y},{x+width},{y+height}")
        x = min(self.width - 1, max(0, x))
        y = min(self.height - 1, max(0, y))
        width = min(self.width - x, max(1, width))
        height = min(self.height - y, max(1, height))
        self._block(x, y, x + width - 1, y + height - 1, b"0")
        chunks, rest = divmod(width * height, self._BUFFER_SIZE)
        pixel = self._encode_pixel(color)
        if chunks:
            data = pixel * self._BUFFER_SIZE
            for _ in range(chunks):
                self._spi.write(None, data)
        if pixel * rest:
            self._spi.write(None, pixel * rest)

    def fill(self, color: Union[int, Tuple] = 0) -> None:
        """Fill the whole display with the specified color."""
        self.fill_rectangle(0, 0, self.width, self.height, color)

    def _block(
        self, x0: int, y0: int, x1: int, y1: int, data: Optional[ByteString] = None
    ) -> Optional[ByteString]:
        """Read or write a block of data."""
        self._spi.write(
            self._COLUMN_SET, self._encode_pos(x0 + self._X_START, x1 + self._X_START)
        )
        self._spi.write(
            self._PAGE_SET, self._encode_pos(y0 + self._Y_START, y1 + self._Y_START)
        )
        if data is None:
            size = struct.calcsize(self._DECODE_PIXEL)
            return self._spi.read(self._RAM_READ, (x1 - x0 + 1) * (y1 - y0 + 1) * size)
        self._spi.write(self._RAM_WRITE, data)
        return None


    def _encode_pos(self, x: int, y: int) -> bytes:
        """Encode a position into bytes."""
        return struct.pack(self._ENCODE_POS, x, y)

    def _encode_pixel(self, color: Union[int, Tuple]) -> bytes:
        """Encode a pixel color into bytes."""
        return struct.pack(self._ENCODE_PIXEL, color)

    def pixel(
        self, x: int, y: int, color: Optional[Union[int, Tuple]] = None
    ) -> Optional[int]:
        """Read or write a pixel at a given position."""
        if color is None:
            return self._decode_pixel(self._block(x, y, x, y))  # type: ignore[arg-type]

        if 0 <= x < self.width and 0 <= y < self.height:
            self._block(x, y, x, y, self._encode_pixel(color))
        return None

    def image(
        self,
        img: Image,
        rotation: Optional[int] = None,
        x: int = 0,
        y: int = 0,
    ) -> None:
        """Set buffer to value of Python Imaging Library image. The image should
        be in 1 bit mode and a size not exceeding the display size when drawn at
        the supplied origin."""
        if rotation is None:
            rotation = self.rotation
        if not img.mode in ("RGB", "RGBA"):
            raise ValueError("Image must be in mode RGB or RGBA")
        if rotation not in (0, 90, 180, 270):
            raise ValueError("Rotation must be 0/90/180/270")
        if rotation != 0:
            img = img.rotate(rotation, expand=True)
        imwidth, imheight = img.size
        if x + imwidth > self.width or y + imheight > self.height:
            raise ValueError(f"Image must not exceed dimensions of display ({self.width}x{self.height}).")
        pixels = bytes(image_to_data(img))
        self._block(x, y, x + imwidth - 1, y + imheight - 1, pixels)
    
    def draw_text(self,
        text: str,
        text_size: int,
        image_size: Tuple[int],
        pos: Tuple[int],
        font_color: int,
        bg_color: int
        ) -> None:
        '''Draws text on screen'''
        self.image(get_text_image(text, text_size, image_size, color_int_to_tuple(font_color), color_int_to_tuple(bg_color)), None, pos[0], pos[1])


class PinWrapper:
    def __init__(self, pin_id, mode=GPIO.OUT, value=0):
        self._pin_id = pin_id
        self._mode = mode
        GPIO.setup(self._pin_id, self._mode)
        self._value = value
    
    @property
    def value(self) -> int:
        """Return current pin value"""
        return self._value

    @value.setter
    def value(self, val: int) -> None:
        self._value = val
        GPIO.output(self._pin_id, GPIO.HIGH if self._value else GPIO.LOW)

class SpiWrapper:
    def __init__(self, spi_device, dc_pin, rst_pin):
        self._spi_device = spi_device
        self._dc_pin = dc_pin
        self._rst_pin = rst_pin
        self.reset()

    def reset(self) -> None:
        """Reset the device"""
        if not self._rst_pin:
            raise RuntimeError("a reset pin was not provided")
        self._rst_pin.value = 0
        time.sleep(0.050)  # 50 milliseconds
        self._rst_pin.value = 1
        time.sleep(0.050)  # 50 milliseconds

    def write(
        self, command: Optional[int] = None, data: Optional[ByteString] = None, delay: Optional[float] = None
    ) -> None:
        """SPI write to the device: commands and data"""
        # self.write(command, data)
        print(f"spi wr: commmand={command if command else 0:02x}, data={[hex(i) for i in data] if data else None}")
        if command is not None:
            self._dc_pin.value = 0
            self._spi_device.writebytes(bytearray([command]))
        if data is not None:
            self._dc_pin.value = 1
            self._spi_device.writebytes(data)
        if delay: time.sleep(delay)
    
    def read(self, command: Optional[int] = None, count: int = 0) -> ByteString:
        """SPI read from device with optional command"""
        answer = bytearray(count)
        print(f"spi rd: commmand={command if command else 0:02x}, ", end='')

        if command is not None:
            self._dc_pin.value = 0
            self._spi_device.writebytes(bytearray([command]))
        self._dc_pin.value = 1
        # answer = self._spi_device.readbytes(count)
        answer = self._spi_device.xfer2(bytes(count))
        print(f"data={[hex(i) for i in answer]}")
        return answer



# 
# 
# CO2
# 
# 

class I2CWrapper:

    # def __init__(self, i2c_bus, i2c_dev_addr):
    #     self._pi = pigpio.pi()
    #     self._i2c_device = pi.i2c_open(i2c_bus, i2c_dev_addr)

    def __init__(self, pi, i2c_device):
        self._pi = pi
        self._i2c_device = i2c_device

    # def __enter__(self):
    #     return self

    # def __exit__(self, exc_type, exc_value, traceback):
    #     self._pi.i2c_close(i2c_device_handler)

    def write(
        self, addr: int, data: ByteString | None = None
    ) -> None:
        '''Writes data to addr using I2C interface'''
        print(f"i2c wr: addr={addr:x}, data={data}")
        if data is None:
            self._pi.i2c_write_device(self._i2c_device, struct.pack(">B", addr))
        elif len(data) == 1:
            data_byte = struct.unpack(">B", data)[0]
            # works with int only
            self._pi.i2c_write_byte_data(self._i2c_device, addr, data_byte)
        else:
            self._pi.i2c_write_i2c_block_data(self._i2c_device, addr, data)

    
    def read(self, addr: int, count: int = 1) -> ByteString:
        '''Reads data from addr using I2C interface'''
        print(f"i2c rd: addr={addr:x},", end="")
        data = None
        if count == 0:
            raise RuntimeError("Zero byte reading is not implemented")
        elif count == 1:
            
            # for some reason single transaction read doesn't work properly
            # might be speed issue
            # data = self._pi.i2c_read_byte_data(self._i2c_device, addr)

            # so have to use 2-transaction form
            self._pi.i2c_write_device(self._i2c_device, struct.pack(">B", addr))
            data = self._pi.i2c_read_byte(self._i2c_device)
            print(f"data={data:x}")
        else:
            (bytes, data) = self._pi.i2c_read_i2c_block_data(self._i2c_device, addr, count)
            if bytes < 0:
                raise RuntimeError("Got error while reading")
            print(f"data={[hex(i) for i in data] if data else None}")
        return data


class CO2MeterWrapper:
    SW_RESET_ADDR = 0xFF
    SW_RESET_VAL = b"\x11\xE5\x72\x8A"

    HW_ID_ADDR = 0x20
    HW_ID_VAL = 0x81

    STATUS_ADDR = 0x0
    STATUS_REG_FW_MODE_FIELD = (7,7)
    STATUS_REG_APP_VALID_FIELD = (4,4)
    STATUS_REG_DATA_READY_FIELD = (3,3)
    STATUS_REG_ERROR_FIELD = (0,0)

    APP_START_ADDR = 0xF4

    MEAS_MODE_ADDR = 0x1
    MEAS_MODE_REG_DRIVE_MODE_FIELD = (6,4)
    MEAS_MODE_REG_INT_DATARDY_FIELD = (3,3)
    MEAS_MODE_REG_INT_THRESH_FIELD = (2,2)
    DRIVE_MODE_1SEC = 0x01

    ALG_RESULT_DATA_ADDR = 0x2

    ERROR_ID_ADDR = 0xE0
    ERROR_ID_REG_WRITE_REG_INVALID_FIELD = (0,0)
    ERROR_ID_REG_READ_REG_INVALID_FIELD = (1,1)
    ERROR_ID_REG_MEASMODE_INVALID_FIELD = (2,2)
    ERROR_ID_REG_MAX_RESISTANCE_FIELD = (3,3)
    ERROR_ID_REG_HEATER_FAULT_FIELD = (4,4)
    ERROR_ID_REG_HEATER_SUPPLY_FIELD = (5,5)

    def __init__(self, i2c) -> None:
        self._i2c = i2c
        self.reset()

    def reset(self) -> None:
        '''SW reset'''
        print(f"co2: SW RST")
        self._i2c.write(self.SW_RESET_ADDR, self.SW_RESET_VAL)
        time.sleep(0.5)

    def check_devid(self) -> bool:
        res = self._i2c.read(self.HW_ID_ADDR)
        print(f"co2: Expected HW_ID={self.HW_ID_VAL}, received HW_ID={res}")
        return res == self.HW_ID_VAL

    def read_status(self) -> int:
        '''Returns status register value'''
        res = self._i2c.read(self.STATUS_ADDR)
        fw_mode = CO2MeterWrapper.get_field(res, self.STATUS_REG_FW_MODE_FIELD)
        app_valid = CO2MeterWrapper.get_field(res, self.STATUS_REG_APP_VALID_FIELD)
        data_ready = CO2MeterWrapper.get_field(res, self.STATUS_REG_DATA_READY_FIELD)
        error = CO2MeterWrapper.get_field(res, self.STATUS_REG_ERROR_FIELD)
        print(f"co2: FW_MODE={fw_mode:x}, APP_VALID={app_valid:x}, DATA_READY={data_ready:x}, ERROR={error:x}")
        return res

    def check_errid(self) -> bool:
        res = self._i2c.read(self.ERROR_ID_ADDR)
        err_fields = [
            ("write_reg_invalid", CO2MeterWrapper.get_field(res, self.ERROR_ID_REG_WRITE_REG_INVALID_FIELD)),
            ("read_reg_invalid", CO2MeterWrapper.get_field(res, self.ERROR_ID_REG_READ_REG_INVALID_FIELD)),
            ("measmode_invalid", CO2MeterWrapper.get_field(res, self.ERROR_ID_REG_MEASMODE_INVALID_FIELD)),
            ("max_resistance", CO2MeterWrapper.get_field(res, self.ERROR_ID_REG_MAX_RESISTANCE_FIELD)),
            ("heater_fault", CO2MeterWrapper.get_field(res, self.ERROR_ID_REG_HEATER_FAULT_FIELD)),
            ("heater_supply", CO2MeterWrapper.get_field(res, self.ERROR_ID_REG_HEATER_SUPPLY_FIELD)),
        ]
        print("co2:", end="")
        for name, val in err_fields:
            print(f" {name}={val};", end="")
        print()
        return res == 0

    def set_app_mode(self):
        '''Writes application mode'''
        self._i2c.write(self.APP_START_ADDR)
        time.sleep(0.1)

    def setmeas_mode(self, mode: int):
        '''Writes measurement mode to register'''
        meas_mode_regval = self._i2c.read(self.MEAS_MODE_ADDR)
        meas_mode_regval = CO2MeterWrapper.set_field(meas_mode_regval, self.MEAS_MODE_REG_DRIVE_MODE_FIELD, mode)
        print(f"co2: MEAS_MODE={mode:x}")
        # send byte to reg MEAS_MODE_ADDR
        self._i2c.write(self.MEAS_MODE_ADDR, struct.pack(">B", meas_mode_regval))
        time.sleep(0.5)

    def read_meas(self):
        data = self._i2c.read(self.ALG_RESULT_DATA_ADDR, 4)
        eco2 = data[0] << 8 | data[1]
        tvoc = data[2] << 8 | data[3]
        return eco2, tvoc

    @staticmethod
    def get_field(regval:int, field: Tuple[int, int]) -> int:
        ''' Returns register field value'''
        mask = ((0x1 << (1 + field[0] - field[1])) - 1) << field[1]
        return (regval & mask) >> field[1]

    @staticmethod
    def set_field(regval:int, field: Tuple[int, int], fieldval:int) -> int:
        ''' Sets field value and return register value'''
        width = 1 + field[0] - field[1]
        if fieldval: assert((int(m.log2(fieldval)) + 1 <= width))
        mask = ((0x1 << width) - 1) << field[1]
        regval |= mask # set all ones in field
        regval &= (fieldval << field[1]) & mask # copy zeros from fieldval
        return regval






class RectWidget:
    def __init__(self,
        lcd: LcdWrapper,
        parent: "Optional[RectWidget]",
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
        if self.need_redraw:
            self._lcd.fill_rectangle(self.x0, self.y0, self.x1, self.y1, self.color)
            self.need_redraw = False
        for child in self._children:
            child.draw()

    def bbox(self) -> Tuple[int]:
        return (self.x0, self.y0, self.x1, self.y1)


class TextLabel(RectWidget):
    def __init__(
    self,
    lcd: LcdWrapper,
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
        text_size = image_size[1] - 1
        self._lcd.draw_text(self.text, text_size, image_size, (self.x0, self.y0), self._font_color, self.color)
    
    @property
    def text(self) -> str:
        """Return current text"""
        return self._text

    @text.setter
    def text(self, value):
        self._text = value
        self._need_redraw = True


class CO2Widget(RectWidget):
    def __init__(
    self,
    lcd: LcdWrapper,
    parent: RectWidget,
    relx: int,
    rely: int,
    width: int,
    height: int,
    font_color: int,
    bg_color: int,
    co2meter: CO2MeterWrapper
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

        self.text = ["O ", "N "][has_new_val] + f"eCO2={self._eco2} ppm, TVOC={self._tvoc} ppb"
        image_size = (self.x1 - self.x0, self.y1 - self.y0)
        text_size = image_size[1] - 1
        self._lcd.draw_text(self.text, text_size, image_size, (self.x0, self.y0), self._font_color, self.color)
    
    @property
    def text(self) -> str:
        """Return current text"""
        return self._text

    @text.setter
    def text(self, value):
        self._text = value
        self._need_redraw = True




if __name__ == "__main__":
    import time
    
    GPIO.setmode(GPIO.BCM)
    status_led = PinWrapper(26)

    try: 
        status_led.value = 1

        # lcd
        spi_dev = spidev.SpiDev()
        spi_dev.open(bus=0, device=0)
        spi_dev.max_speed_hz = 1000000
        dc_pin = PinWrapper(25)
        rst_pin = PinWrapper(24)
        spi = SpiWrapper(spi_dev, dc_pin, rst_pin)
        lcd = LcdWrapper(spi, 128, 160, rotation=180)

        # co2
        pi = pigpio.pi()
        i2c_device = pi.i2c_open(1, 0x5a)
        i2c = I2CWrapper(pi, i2c_device)
        co2meter = CO2MeterWrapper(i2c)

        status_led.value = 0

        time.sleep(0.2)
        res = spi.read(LcdWrapper._RDDID, 4)
        spi.write(LcdWrapper._NOP, None)
        print("Display ID:", res)

        main_widget = RectWidget(lcd, None, 0, 0, lcd.width, lcd.height, lcd._COLOR_BLACK)
        date_widget = TextLabel(lcd, main_widget, 0, 0, lcd.width, 10, font_color=0xFFFFFF, bg_color=lcd._COLOR_GREEN)
        text_widget = TextLabel(lcd, main_widget, 0, 150, lcd.width, 10, font_color=0xFFFFFF, bg_color=lcd._COLOR_GREEN, text="Hello, world!")
        co2_widget = CO2Widget(lcd, main_widget, 0, 60, lcd.width, 10, font_color=0xFFFFFF, bg_color=lcd._COLOR_GREEN, co2meter=co2meter)
        
        while True:
            date_widget.text = time.ctime()
            co2_widget._need_redraw = True
            main_widget.draw()
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
