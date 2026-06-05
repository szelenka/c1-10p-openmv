SYNC = 0xA5
MAX_PAYLOAD_SIZE = 16

CMD_LED_SET_COLOR = 0x01
CMD_LED_SET_BRIGHTNESS = 0x02
CMD_LED_SET_PATTERN = 0x03
CMD_LED_OFF = 0x04
CMD_LED_ON = 0x05
CMD_TRACKING_SET = 0x10

LED_ID_RIGHT_EYE = 1
LED_ID_LEFT_EYE = 2
LED_ID_PERISCOPE = 4

WAIT_SYNC = 0
WAIT_CMD = 1
WAIT_LEN = 2
WAIT_PAYLOAD = 3
WAIT_CHECKSUM = 4

DEFAULT_COLOR = (0, 0, 255, 0)
OFF = (0, 0, 0)


class SerialLedOutput:
    def __init__(self, pixel_object, color=OFF, name=None):
        self.pixel_object = pixel_object
        self.name = name
        self._color = color
        self._dirty = True
        self._needs_show = False
        self._paused = False
        self.draw_count = 0
        self.cycle_count = 0
        self.cycle_complete = False
        self.notify_cycles = 1
        try:
            self.pixel_object.auto_write = False
        except AttributeError:
            pass

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        if self._color == color:
            return
        self._color = color
        self._dirty = True

    def animate(self, show=True):
        if self._paused or not self._dirty:
            return False

        self.draw_count += 1
        self._fill_pixels(self._color)
        self._dirty = False
        self._needs_show = True
        if show:
            self.show()
        return True

    def show(self):
        if not self._needs_show:
            return
        if hasattr(self.pixel_object, "write"):
            self.pixel_object.write()
        elif hasattr(self.pixel_object, "show"):
            self.pixel_object.show()
        self._needs_show = False

    def fill(self, color):
        self.color = color

    def freeze(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def reset(self):
        self._dirty = True

    def on_cycle_complete(self):
        self.cycle_count += 1

    def add_cycle_complete_receiver(self, callback):
        pass

    def _fill_pixels(self, color):
        if hasattr(self.pixel_object, "fill"):
            self.pixel_object.fill(color)
        else:
            for index in range(len(self.pixel_object)):
                self.pixel_object[index] = color


class SerialCommandProcessor:
    def __init__(
        self,
        uart,
        pixel_eye_right,
        pixel_eye_left,
        pixel_periscope,
        animations_by_led_id=None,
        on_tracking_set=None,
        mirror_eye_commands=False,
    ):
        self.uart = uart
        self.pixels_by_led_id = {
            LED_ID_RIGHT_EYE: pixel_eye_right,
            LED_ID_LEFT_EYE: pixel_eye_left,
            LED_ID_PERISCOPE: pixel_periscope,
        }
        self.led_state = {
            LED_ID_RIGHT_EYE: self._new_led_state(),
            LED_ID_LEFT_EYE: self._new_led_state(),
            LED_ID_PERISCOPE: self._new_led_state(),
        }
        self.led_state[LED_ID_PERISCOPE]["enabled"] = False
        self.animations_by_led_id = animations_by_led_id or {}
        self.mirror_eye_commands = mirror_eye_commands
        self.tracking_enabled = False
        self.on_tracking_set = on_tracking_set
        self._reset_frame()
        self.apply_all()

    def _new_led_state(self):
        return {
            "enabled": True,
            "color": DEFAULT_COLOR,
            "brightness": 255,
        }

    def _reset_frame(self):
        self._parser_state = WAIT_SYNC
        self._cmd = 0
        self._length = 0
        self._payload = []
        self._checksum = 0

    def poll(self):
        while True:
            available = self.uart.any()
            if not available:
                return
            data = self.uart.read(available)
            if not data:
                return
            for byte in data:
                self.process_byte(byte)

    def process_byte(self, byte):
        if self._parser_state == WAIT_SYNC:
            if byte == SYNC:
                self._parser_state = WAIT_CMD
            return

        if self._parser_state == WAIT_CMD:
            self._cmd = byte
            self._checksum = byte
            self._parser_state = WAIT_LEN
            return

        if self._parser_state == WAIT_LEN:
            self._length = byte
            if self._length > MAX_PAYLOAD_SIZE:
                self._reset_frame()
                return
            self._payload = []
            self._checksum ^= byte
            if self._length == 0:
                self._parser_state = WAIT_CHECKSUM
            else:
                self._parser_state = WAIT_PAYLOAD
            return

        if self._parser_state == WAIT_PAYLOAD:
            self._payload.append(byte)
            self._checksum ^= byte
            if len(self._payload) >= self._length:
                self._parser_state = WAIT_CHECKSUM
            return

        if self._parser_state == WAIT_CHECKSUM:
            if byte == self._checksum:
                self.dispatch_frame(self._cmd, self._payload)
            self._reset_frame()

    def dispatch_frame(self, cmd, payload):
        if cmd == CMD_LED_SET_COLOR:
            self._handle_led_set_color(payload)
        elif cmd == CMD_LED_SET_BRIGHTNESS:
            self._handle_led_set_brightness(payload)
        elif cmd == CMD_LED_SET_PATTERN:
            return
        elif cmd == CMD_LED_OFF:
            self._handle_led_off(payload)
        elif cmd == CMD_LED_ON:
            self._handle_led_on(payload)
        elif cmd == CMD_TRACKING_SET:
            self._handle_tracking_set(payload)

    def _handle_led_set_color(self, payload):
        if len(payload) != 5:
            return
        led_id = payload[0]
        if led_id not in self.led_state:
            return
        color = (payload[1], payload[2], payload[3], payload[4])
        for target_led_id in self._target_led_ids(led_id):
            self.led_state[target_led_id]["color"] = color
            self.led_state[target_led_id]["enabled"] = True
            self.apply_led(target_led_id)

    def _handle_led_set_brightness(self, payload):
        if len(payload) != 2:
            return
        led_id = payload[0]
        if led_id not in self.led_state:
            return
        for target_led_id in self._target_led_ids(led_id):
            self.led_state[target_led_id]["brightness"] = payload[1]
            self.apply_led(target_led_id)

    def _handle_led_off(self, payload):
        if len(payload) != 1:
            return
        led_id = payload[0]
        if led_id not in self.led_state:
            return
        for target_led_id in self._target_led_ids(led_id):
            self.led_state[target_led_id]["enabled"] = False
            self._turn_off_led_id(target_led_id)

    def _handle_led_on(self, payload):
        if len(payload) != 1:
            return
        led_id = payload[0]
        if led_id not in self.led_state:
            return
        for target_led_id in self._target_led_ids(led_id):
            self.led_state[target_led_id]["enabled"] = True
            self.apply_led(target_led_id)

    def _handle_tracking_set(self, payload):
        if len(payload) != 1:
            return
        self.tracking_enabled = payload[0] != 0
        if self.on_tracking_set:
            self.on_tracking_set(self.tracking_enabled)

    def apply_all(self):
        self.apply_led(LED_ID_RIGHT_EYE)
        self.apply_led(LED_ID_LEFT_EYE)
        self.apply_led(LED_ID_PERISCOPE)

    def _target_led_ids(self, led_id):
        if self.mirror_eye_commands and (
            led_id == LED_ID_RIGHT_EYE or led_id == LED_ID_LEFT_EYE
        ):
            return (LED_ID_RIGHT_EYE, LED_ID_LEFT_EYE)
        return (led_id,)

    def apply_led(self, led_id):
        state = self.led_state.get(led_id)
        if not state:
            return
        if not state["enabled"]:
            self._turn_off_led_id(led_id)
            return

        color = state["color"]
        rgb = self._rgb_from_rgbw(color)
        scaled = self._scale_rgb(rgb, state["brightness"])
        animation = self.animations_by_led_id.get(led_id)
        if animation:
            animation.color = scaled
            return
        self._fill(self.pixels_by_led_id[led_id], scaled)

    def _turn_off_led_id(self, led_id):
        animation = self.animations_by_led_id.get(led_id)
        if animation:
            animation.color = OFF
            return
        pixels = self.pixels_by_led_id.get(led_id)
        if pixels:
            self._fill(pixels, OFF)

    def _rgb_from_rgbw(self, color):
        r, g, b, w = color
        return (
            min(255, r + w),
            min(255, g + w),
            min(255, b + w),
        )

    def _scale_rgb(self, color, brightness):
        return (
            (color[0] * brightness) // 255,
            (color[1] * brightness) // 255,
            (color[2] * brightness) // 255,
        )

    def _fill(self, pixels, color):
        if hasattr(pixels, "fill"):
            pixels.fill(color)
        else:
            for index in range(len(pixels)):
                pixels[index] = color

        if hasattr(pixels, "write"):
            pixels.write()
        elif hasattr(pixels, "show"):
            pixels.show()
