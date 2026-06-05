import image
import machine
import neopixel
import pyb
import sensor

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
    SerialCommandProcessor,
    send_vision_result
)

UART_BUS = 3
UART_BAUDRATE = 115200
UART_READ_BUFFER = 256
MIRROR_EYE_COMMANDS = True

FACE_CASCADE_STAGES = 25
FACE_DETECTION_THRESHOLD = 0.75
FACE_DETECTION_SCALE = 1.25
VISION_DETECTED_CONFIDENCE = 255


def configure_camera():
    sensor.reset()
    sensor.set_contrast(3)
    sensor.set_gainceiling(16)
    sensor.set_pixformat(sensor.GRAYSCALE)
    sensor.set_framesize(sensor.QVGA)
    sensor.skip_frames(time=2000)


def find_largest_face(img, face_cascade):
    faces = img.find_features(
        face_cascade,
        threshold=FACE_DETECTION_THRESHOLD,
        scale_factor=FACE_DETECTION_SCALE
    )
    if not faces:
        return None
    largest_face = None
    largest_area = 0
    for rect in faces:
        area = rect[2] * rect[3]
        if area > largest_area:
            largest_area = area
            largest_face = rect
        img.draw_rectangle(rect)
    return largest_face


def send_face_result(uart, face, frame_center_x, frame_center_y):
    if not face:
        send_vision_result(uart, 0, 0, 0, 0, 0, False)
        return

    x, y, width, height = face
    face_center_x = x + ((width + 1) // 2)
    face_center_y = y + ((height + 1) // 2)
    send_vision_result(
        uart,
        face_center_x - frame_center_x,
        face_center_y - frame_center_y,
        width,
        height,
        VISION_DETECTED_CONFIDENCE,
        True
    )


def poll_face_tracking(
    uart,
    serial_commands,
    face_cascade,
    frame_center_x,
    frame_center_y
):
    if not serial_commands.tracking_enabled:
        return

    img = sensor.snapshot()
    send_face_result(
        uart,
        find_largest_face(img, face_cascade),
        frame_center_x,
        frame_center_y
    )


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
periscope_output = Pulse(
    pixel_periscope,
    speed=0.01, # duration until next initenxity increase (in seconds)
    color=BLUE,
    period=5,
    breath=0,
    min_intensity=0.01,
    max_intensity=0.3
)

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

eye_group = AnimationGroup(
    pulse_eye_right,
    pulse_eye_left,
    sync=True
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
    eye_group,
    periscope_output
)

uart = pyb.UART(
    UART_BUS,
    UART_BAUDRATE,
    timeout_char=0,
    read_buf_len=UART_READ_BUFFER
)
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
    on_tracking_set=lambda _: print(_),
    mirror_eye_commands=MIRROR_EYE_COMMANDS
)

configure_camera()
FRAME_CENTER_X = sensor.width() // 2
FRAME_CENTER_Y = sensor.height() // 2
face_cascade = image.HaarCascade("frontalface", stages=FACE_CASCADE_STAGES)


while True:
    serial_commands.poll()
    poll_face_tracking(
        uart,
        serial_commands,
        face_cascade,
        FRAME_CENTER_X,
        FRAME_CENTER_Y
    )
    group.animate()
