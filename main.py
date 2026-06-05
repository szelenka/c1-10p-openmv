
import machine
import neopixel
import pyb

from adafruit_led_animation.color import (
    RED,
    BLUE,
    DILLUTED_RED,
    calculate_intensity
)
from adafruit_led_animation.animation.comet import Comet
from adafruit_led_animation.animation.pulse import Pulse
from adafruit_led_animation.helper import PixelSubset
from adafruit_led_animation.group import AnimationGroup
from serial_processor import (
    LED_ID_LEFT_EYE,
    LED_ID_PERISCOPE,
    LED_ID_RIGHT_EYE,
    SerialLedOutput,
    SerialCommandProcessor
)

UART_BUS = 2
UART_BAUDRATE = 115200

# setup neopixel
# For RGBW NeoPixels, simply change the ORDER to RGBW or GRBW.
# ORDER = "GRB"
pixel_eye_right = neopixel.NeoPixel(machine.Pin.board.P0, 7)
pixel_eye_left = neopixel.NeoPixel(machine.Pin.board.P1, 7)
pixel_ladder = PixelSubset(
    neopixel.NeoPixel(machine.Pin.board.P2, 16),
    2,
    16
)
pixel_periscope = neopixel.NeoPixel(machine.Pin.board.P3, 1)
periscope_output = SerialLedOutput(pixel_periscope, name="periscope")

pulse_eye_right = Pulse(
    pixel_eye_right,
    speed=0.01, # duration until next initenxity increase (in seconds)
    color=BLUE,
    period=5,
    breath=0,
    min_intensity=0.01,
    max_intensity=0.3
)
pulse_eye_left = Pulse(
    pixel_eye_left,
    speed=0.01, # duration until next initenxity increase (in seconds)
    color=BLUE,
    period=5,
    breath=0,
    min_intensity=0.01,
    max_intensity=0.3
)

group = AnimationGroup(
    Comet(
        pixel_ladder,
        speed=1/16, # duration until next animation step (in seconds)
        color=calculate_intensity(DILLUTED_RED, 0.1),
        background_color=calculate_intensity(RED, 0.1),
        tail_length=4,
        bounce=True
    ),
    pulse_eye_right,
    pulse_eye_left,
    periscope_output
)

uart = pyb.UART(UART_BUS, UART_BAUDRATE, timeout_char=0)
serial_commands = SerialCommandProcessor(
    uart,
    pixel_eye_right,
    pixel_eye_left,
    pixel_periscope,
    animations_by_led_id={
        LED_ID_RIGHT_EYE: pulse_eye_right,
        LED_ID_LEFT_EYE: pulse_eye_left,
        LED_ID_PERISCOPE: periscope_output,
    },
    on_tracking_set=lambda _: print(_)
)


while True:
    serial_commands.poll()
    group.animate()
