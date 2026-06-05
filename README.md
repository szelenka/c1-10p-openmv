# C1-10P for OpenMV camera module

This repo contains the OpenMV MicroPython runtime for the C1-10P dome camera
and lighting module. It works with the companion ESP32 controller repo in
`szelenka/c1-10p-esp32`.

The OpenMV module is responsible for:

- receiving ESP32 serial commands for dome eye and periscope LEDs
- running NeoPixel animations on the OpenMV pins
- enabling/disabling face tracking when commanded by the ESP32
- detecting frontal faces with OpenMV's Haar cascade detector
- smoothing and filtering vision results before sending them back to ESP32
- sending bounding-box packets over UART for ESP32 dome tracking

## Runtime Overview

`main.py` is the OpenMV entry point. It initializes the camera, NeoPixels, UART,
serial command parser, and face tracking filter.

Runtime files:

| File | Purpose |
| --- | --- |
| `main.py` | OpenMV hardware setup and main loop |
| `serial_processor.py` | ESP32/OpenMV serial framing, LED command handling, and vision-result frame encoding |
| `vision_filter.py` | Face tracking smoothing, hold time, and bad-box rejection |

Support files:

| File | Purpose |
| --- | --- |
| `test_serial_processor.py` | Host-side serial protocol and LED behavior tests |
| `test_vision_filter.py` | Host-side tracking filter tests |
| `ESP32_SERIAL_COMMAND_PLAN.md` | Serial command implementation notes |
| `HAAR_TRACKING_STABILITY_PLAN.md` | Face tracking stability plan and tuning notes |

## Developer Environment Setup

For on-device development:

- [OpenMV IDE](https://openmv.io/pages/download)
- OpenMV camera module with firmware that includes `image.HaarCascade`
- ESP32 controller running the companion `szelenka/c1-10p-esp32` firmware

For host-side tests:

- Python 3

Run all local tests:

```bash
python3 -m unittest discover
```

Run syntax checks for host-compatible modules:

```bash
python3 -m py_compile main.py serial_processor.py vision_filter.py test_serial_processor.py test_vision_filter.py
```

## OpenMV Deployment

Install these runtime files on the OpenMV filesystem:

- `main.py`
- `serial_processor.py`
- `vision_filter.py`

The OpenMV IDE framebuffer will update only while face tracking is enabled,
because `sensor.snapshot()` is gated by the ESP32 tracking command.

## Hardware Mapping

Current OpenMV pin usage:

| OpenMV pin | Device |
| --- | --- |
| `P0` | right eye NeoPixel strip |
| `P1` | left/center eye NeoPixel strip |
| `P2` | ladder NeoPixel strip |
| `P3` | periscope NeoPixel |

Current UART settings:

| Setting | Value |
| --- | --- |
| UART bus | `3` |
| Baud | `115200` |
| Read buffer | `256` bytes |

The companion ESP32 protocol documentation in `../chopper/docs/design/openmv-protocol.md`
describes the ESP32 side as UART2 at 115200 baud.

## Serial Protocol

All ESP32/OpenMV frames use:

```text
[0xA5][cmd_id][len][payload bytes...][checksum]
checksum = cmd_id ^ len ^ payload[0] ^ ... ^ payload[len - 1]
max payload len = 16
```

ESP32 to OpenMV commands:

| Command | Value | Payload |
| --- | ---: | --- |
| `LED_SET_COLOR` | `0x01` | `led_id, red, green, blue, white` |
| `LED_SET_BRIGHTNESS` | `0x02` | `led_id, brightness` |
| `LED_SET_PATTERN` | `0x03` | `led_id, pattern_id` |
| `LED_OFF` | `0x04` | `led_id` |
| `LED_ON` | `0x05` | `led_id` |
| `TRACKING_SET` | `0x10` | `enabled` |

OpenMV to ESP32 vision result:

| Command | Value | Payload |
| --- | ---: | --- |
| `VISION_RESULT` | `0x80` | `center_x, center_y, width, height, confidence, detected` |

`VISION_RESULT` uses big-endian fields:

- `center_x`: signed int16, pixels relative to frame center
- `center_y`: signed int16, pixels relative to frame center
- `width`: unsigned int16 bounding-box width
- `height`: unsigned int16 bounding-box height
- `confidence`: unsigned 8-bit synthetic confidence
- `detected`: `1` when a target is active, `0` when no target is active

Coordinate convention:

- `(0, 0)` is the center of the camera frame
- positive X is right
- positive Y is down

## LED IDs

| LED ID | Target |
| ---: | --- |
| `1` | right eye NeoPixel strip |
| `2` | left/center eye NeoPixel strip |
| `4` | periscope NeoPixel |

`main.py` enables `MIRROR_EYE_COMMANDS`, so commands for either eye ID update
both eye animations together.

## Face Tracking

The ESP32 toggles tracking with the dome controller `SL+SR` two-second hold.
When enabled, `OpenMvBridgeNode` sends `TRACKING_SET = 1` to the OpenMV. When
disabled, it sends `TRACKING_SET = 0`.

OpenMV tracking flow:

1. Capture a QVGA grayscale frame.
2. Run `image.HaarCascade("frontalface")`.
3. Select the largest detected face.
4. Pass the bounding box through `FaceTrackingFilter`.
5. Send a `VISION_RESULT` serial frame back to ESP32.

`FaceTrackingFilter` makes Haar output more stable by:

- rate-limiting vision updates to 10 Hz
- smoothing center and bounding-box size
- holding the last target briefly across isolated missed frames
- rejecting boxes that are too small, too large, or jump too far in one update

The OpenMV does not make motor decisions. The ESP32 `DomeNode` consumes
`VISION_RESULT` and turns horizontal error into dome motor speed.

## Common Hardware Checks

Known ESP32 eye color frames:

```text
Right eye red:    A5 01 05 01 FF 00 00 00 FA
Left/center red:  A5 01 05 02 FF 00 00 00 F9
Right eye blue:   A5 01 05 01 00 00 FF 00 FA
Left/center blue: A5 01 05 02 00 00 FF 00 F9
```

Tracking-on frame:

```text
A5 10 01 01 10
```

Tracking-off frame:

```text
A5 10 01 00 11
```

## Tuning

Face tracking constants live in `vision_filter.py`:

- `VISION_UPDATE_MS`
- `SMOOTHING_ALPHA`
- `DETECTION_HOLD_MS`
- `MAX_CONSECUTIVE_MISSES`
- `MIN_FACE_WIDTH`
- `MIN_FACE_HEIGHT`
- `MAX_FACE_WIDTH`
- `MAX_FACE_HEIGHT`
- `MAX_CENTER_JUMP_PX`

If the dome twitches, lower `SMOOTHING_ALPHA` or increase `VISION_UPDATE_MS`.
If tracking lags, raise `SMOOTHING_ALPHA` or lower `VISION_UPDATE_MS`.
If tracking drops out too easily, increase `DETECTION_HOLD_MS`.
