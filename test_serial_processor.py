import unittest

from serial_processor import (
    CMD_LED_OFF,
    CMD_LED_ON,
    CMD_LED_SET_BRIGHTNESS,
    CMD_LED_SET_COLOR,
    CMD_LED_SET_PATTERN,
    CMD_TRACKING_SET,
    LED_ID_LEFT_EYE,
    LED_ID_PERISCOPE,
    LED_ID_RIGHT_EYE,
    MAX_PAYLOAD_SIZE,
    SYNC,
    SerialCommandProcessor,
    SerialLedOutput,
)


class FakeUART:
    def __init__(self):
        self._buffer = bytearray()

    def feed(self, data):
        self._buffer.extend(data)

    def any(self):
        return len(self._buffer)

    def read(self, length):
        data = self._buffer[:length]
        del self._buffer[:length]
        return bytes(data)


class FakePixels:
    def __init__(self, count):
        self.values = [(9, 9, 9)] * count
        self.write_count = 0
        self.auto_write = True

    def __len__(self):
        return len(self.values)

    def __setitem__(self, index, color):
        self.values[index] = color

    def fill(self, color):
        self.values = [color] * len(self.values)

    def write(self):
        self.write_count += 1


class FakePulse:
    def __init__(self):
        self.color = None


def frame(cmd, payload):
    checksum = cmd ^ len(payload)
    for byte in payload:
        checksum ^= byte
    return bytes([SYNC, cmd, len(payload)] + payload + [checksum])


def bad_checksum(data):
    corrupted = bytearray(data)
    corrupted[-1] ^= 0xFF
    return bytes(corrupted)


class SerialCommandProcessorTest(unittest.TestCase):
    def setUp(self):
        self.uart = FakeUART()
        self.right_pixels = FakePixels(7)
        self.left_pixels = FakePixels(7)
        self.periscope_pixels = FakePixels(1)
        self.right_pulse = FakePulse()
        self.left_pulse = FakePulse()
        self.periscope_output = SerialLedOutput(self.periscope_pixels)
        self.tracking_updates = []
        self.processor = SerialCommandProcessor(
            self.uart,
            self.right_pixels,
            self.left_pixels,
            self.periscope_pixels,
            animations_by_led_id={
                LED_ID_RIGHT_EYE: self.right_pulse,
                LED_ID_LEFT_EYE: self.left_pulse,
                LED_ID_PERISCOPE: self.periscope_output,
            },
            on_tracking_set=self.tracking_updates.append,
        )

    def feed_frame(self, cmd, payload):
        self.uart.feed(frame(cmd, payload))
        self.processor.poll()

    def test_initial_state_sets_eye_pulses_and_keeps_periscope_off(self):
        self.assertEqual((0, 0, 255), self.right_pulse.color)
        self.assertEqual((0, 0, 255), self.left_pulse.color)
        self.assertEqual((0, 0, 0), self.periscope_output.color)
        self.assertEqual(0, self.right_pixels.write_count)
        self.assertEqual(0, self.left_pixels.write_count)
        self.assertEqual(0, self.periscope_pixels.write_count)

    def test_known_esp32_eye_color_frames_update_pulse_colors(self):
        self.uart.feed(bytes.fromhex("A5 01 05 01 FF 00 00 00 FA"))
        self.processor.poll()
        self.assertEqual((255, 0, 0), self.right_pulse.color)

        self.uart.feed(bytes.fromhex("A5 01 05 02 FF 00 00 00 F9"))
        self.processor.poll()
        self.assertEqual((255, 0, 0), self.left_pulse.color)

        self.uart.feed(bytes.fromhex("A5 01 05 01 00 00 FF 00 FA"))
        self.processor.poll()
        self.assertEqual((0, 0, 255), self.right_pulse.color)

        self.uart.feed(bytes.fromhex("A5 01 05 02 00 00 FF 00 F9"))
        self.processor.poll()
        self.assertEqual((0, 0, 255), self.left_pulse.color)

    def test_back_to_back_eye_frames_update_both_pulses_in_one_poll(self):
        self.uart.feed(
            bytes.fromhex(
                "A5 01 05 01 FF 00 00 00 FA"
                "A5 01 05 02 FF 00 00 00 F9"
            )
        )

        self.processor.poll()

        self.assertEqual((255, 0, 0), self.right_pulse.color)
        self.assertEqual((255, 0, 0), self.left_pulse.color)

    def test_mirrored_eye_color_command_updates_both_pulses(self):
        uart = FakeUART()
        right_pulse = FakePulse()
        left_pulse = FakePulse()
        processor = SerialCommandProcessor(
            uart,
            self.right_pixels,
            self.left_pixels,
            self.periscope_pixels,
            animations_by_led_id={
                LED_ID_RIGHT_EYE: right_pulse,
                LED_ID_LEFT_EYE: left_pulse,
                LED_ID_PERISCOPE: self.periscope_output,
            },
            mirror_eye_commands=True,
        )

        uart.feed(bytes.fromhex("A5 01 05 01 FF 00 00 00 FA"))
        processor.poll()

        self.assertEqual((255, 0, 0), right_pulse.color)
        self.assertEqual((255, 0, 0), left_pulse.color)

        uart.feed(bytes.fromhex("A5 01 05 02 00 00 FF 00 F9"))
        processor.poll()

        self.assertEqual((0, 0, 255), right_pulse.color)
        self.assertEqual((0, 0, 255), left_pulse.color)

    def test_white_channel_is_folded_into_rgb_and_clamped(self):
        self.feed_frame(CMD_LED_SET_COLOR, [LED_ID_RIGHT_EYE, 250, 10, 0, 20])

        self.assertEqual((255, 30, 20), self.right_pulse.color)

    def test_brightness_scales_stored_color(self):
        self.feed_frame(CMD_LED_SET_COLOR, [LED_ID_RIGHT_EYE, 200, 100, 50, 0])
        self.feed_frame(CMD_LED_SET_BRIGHTNESS, [LED_ID_RIGHT_EYE, 128])

        self.assertEqual((100, 50, 25), self.right_pulse.color)

    def test_led_off_and_on_use_stored_color_without_direct_eye_writes(self):
        self.feed_frame(CMD_LED_SET_COLOR, [LED_ID_RIGHT_EYE, 120, 60, 30, 0])
        self.feed_frame(CMD_LED_SET_BRIGHTNESS, [LED_ID_RIGHT_EYE, 128])
        self.feed_frame(CMD_LED_OFF, [LED_ID_RIGHT_EYE])

        self.assertEqual((0, 0, 0), self.right_pulse.color)
        self.assertEqual(0, self.right_pixels.write_count)

        self.feed_frame(CMD_LED_ON, [LED_ID_RIGHT_EYE])

        self.assertEqual((60, 30, 15), self.right_pulse.color)
        self.assertEqual(0, self.right_pixels.write_count)

    def test_periscope_color_renders_on_next_output_phase(self):
        self.feed_frame(CMD_LED_SET_COLOR, [LED_ID_PERISCOPE, 0, 255, 0, 0])

        self.assertEqual((0, 255, 0), self.periscope_output.color)
        self.assertEqual(0, self.periscope_pixels.write_count)

        self.assertTrue(self.periscope_output.animate())
        self.assertEqual([(0, 255, 0)], self.periscope_pixels.values)
        self.assertEqual(1, self.periscope_pixels.write_count)

    def test_periscope_led_off_turns_off_on_next_output_phase(self):
        self.feed_frame(CMD_LED_SET_COLOR, [LED_ID_PERISCOPE, 255, 0, 0, 0])
        self.periscope_output.animate()

        self.feed_frame(CMD_LED_OFF, [LED_ID_PERISCOPE])

        self.assertEqual((0, 0, 0), self.periscope_output.color)
        self.assertEqual([(255, 0, 0)], self.periscope_pixels.values)
        self.assertEqual(1, self.periscope_pixels.write_count)

        self.assertTrue(self.periscope_output.animate())
        self.assertEqual([(0, 0, 0)], self.periscope_pixels.values)
        self.assertEqual(2, self.periscope_pixels.write_count)

    def test_periscope_led_on_restores_stored_color(self):
        self.feed_frame(CMD_LED_SET_COLOR, [LED_ID_PERISCOPE, 40, 80, 120, 0])
        self.feed_frame(CMD_LED_OFF, [LED_ID_PERISCOPE])
        self.periscope_output.animate()

        self.feed_frame(CMD_LED_ON, [LED_ID_PERISCOPE])

        self.assertEqual((40, 80, 120), self.periscope_output.color)
        self.assertEqual(1, self.periscope_pixels.write_count)

        self.assertTrue(self.periscope_output.animate())
        self.assertEqual([(40, 80, 120)], self.periscope_pixels.values)
        self.assertEqual(2, self.periscope_pixels.write_count)

    def test_removed_periscope_state_command_is_ignored(self):
        self.feed_frame(CMD_LED_SET_COLOR, [LED_ID_PERISCOPE, 255, 0, 0, 0])
        self.feed_frame(CMD_LED_OFF, [LED_ID_PERISCOPE])

        self.uart.feed(frame(0x20, [1]))
        self.processor.poll()

        self.assertEqual((0, 0, 0), self.periscope_output.color)

    def test_tracking_set_updates_state_and_callback(self):
        self.feed_frame(CMD_TRACKING_SET, [1])
        self.feed_frame(CMD_TRACKING_SET, [0])

        self.assertFalse(self.processor.tracking_enabled)
        self.assertEqual([True, False], self.tracking_updates)

    def test_led_set_pattern_is_ignored(self):
        before = self.right_pulse.color

        self.feed_frame(CMD_LED_SET_PATTERN, [LED_ID_RIGHT_EYE, 3])

        self.assertEqual(before, self.right_pulse.color)

    def test_bad_checksum_frame_is_ignored(self):
        self.feed_frame(CMD_LED_SET_COLOR, [LED_ID_RIGHT_EYE, 255, 0, 0, 0])
        self.uart.feed(
            bad_checksum(frame(CMD_LED_SET_COLOR, [LED_ID_RIGHT_EYE, 0, 255, 0, 0]))
        )
        self.processor.poll()

        self.assertEqual((255, 0, 0), self.right_pulse.color)

    def test_partial_frame_completes_across_polls(self):
        data = frame(CMD_LED_SET_COLOR, [LED_ID_LEFT_EYE, 0, 255, 0, 0])

        self.uart.feed(data[:3])
        self.processor.poll()
        self.assertEqual((0, 0, 255), self.left_pulse.color)

        self.uart.feed(data[3:])
        self.processor.poll()
        self.assertEqual((0, 255, 0), self.left_pulse.color)

    def test_oversized_payload_resets_parser_and_next_valid_frame_succeeds(self):
        oversized = bytes([SYNC, CMD_LED_SET_COLOR, MAX_PAYLOAD_SIZE + 1])
        self.uart.feed(oversized)
        self.processor.poll()

        self.feed_frame(CMD_LED_SET_COLOR, [LED_ID_LEFT_EYE, 255, 0, 0, 0])

        self.assertEqual((255, 0, 0), self.left_pulse.color)

    def test_unknown_led_and_unknown_command_are_ignored(self):
        self.uart.feed(frame(0x7F, [1, 2, 3]))
        self.processor.poll()
        self.feed_frame(CMD_LED_SET_COLOR, [99, 255, 0, 0, 0])

        self.assertEqual((0, 0, 255), self.right_pulse.color)
        self.assertEqual((0, 0, 255), self.left_pulse.color)


if __name__ == "__main__":
    unittest.main()
