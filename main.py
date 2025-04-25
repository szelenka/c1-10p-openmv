
import machine
import neopixel
import pyb
import time

from adafruit_led_animation.color import (
    RED,
    GREEN,
    BLUE,
    DILLUTED_RED,
    calculate_intensity
)
from adafruit_led_animation.animation.comet import Comet
from adafruit_led_animation.animation.pulse import Pulse
from adafruit_led_animation.helper import PixelSubset
from adafruit_led_animation.group import AnimationGroup

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


group = AnimationGroup(
    Comet(
        pixel_ladder,
        speed=1/16, # duration until next animation step (in seconds)
        color=calculate_intensity(DILLUTED_RED, 0.1),
        background_color=calculate_intensity(RED, 0.1),
        tail_length=4,
        bounce=True
    ),
    Pulse(
        pixel_eye_right,
        speed=0.01, # duration until next initenxity increase (in seconds)
        color=BLUE,
        period=5,
        breath=0,
        min_intensity=0.01,
        max_intensity=0.3
    ),
    Pulse(
        pixel_eye_left,
        speed=0.01, # duration until next initenxity increase (in seconds)
        color=BLUE,
        period=5,
        breath=0,
        min_intensity=0.01,
        max_intensity=0.3
    )
)


while True:
    group.animate()
