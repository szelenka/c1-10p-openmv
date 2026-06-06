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
from vision_filter import (
    FaceTrackingFilter,
    VISION_UPDATE_MS
)

UART_BUS = 3
UART_BAUDRATE = 115200
UART_READ_BUFFER = 256
MIRROR_EYE_COMMANDS = True
DEBUG_RECEIVED_PACKETS = True

FACE_CASCADE_STAGES = 25
FACE_DETECTION_THRESHOLD = 0.75
FACE_DETECTION_SCALE = 1.25


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


def poll_face_tracking(
    uart,
    serial_commands,
    face_cascade,
    tracker,
    frame_center_x,
    frame_center_y
):
    global last_vision_update_ms

    if not serial_commands.tracking_enabled:
        tracker.reset()
        last_vision_update_ms = 0
        return

    now_ms = pyb.millis()
    if (
        last_vision_update_ms and
        pyb.elapsed_millis(last_vision_update_ms) < VISION_UPDATE_MS
    ):
        return
    last_vision_update_ms = now_ms

    img = sensor.snapshot()
    result = tracker.update(
        find_largest_face(img, face_cascade),
        now_ms,
        frame_center_x,
        frame_center_y
    )
    send_vision_result(
        uart,
        result[0],
        result[1],
        result[2],
        result[3],
        result[4],
        result[5]
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

face_tracker = FaceTrackingFilter()
last_vision_update_ms = 0

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
    mirror_eye_commands=MIRROR_EYE_COMMANDS,
    debug_received_packets=DEBUG_RECEIVED_PACKETS
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
        face_tracker,
        FRAME_CENTER_X,
        FRAME_CENTER_Y
    )
    group.animate()
