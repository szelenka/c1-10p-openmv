VISION_UPDATE_MS = 100
SMOOTHING_ALPHA = 0.35
DETECTION_HOLD_MS = 300
MAX_CONSECUTIVE_MISSES = 3

MIN_FACE_WIDTH = 20
MIN_FACE_HEIGHT = 20
MAX_FACE_WIDTH = 220
MAX_FACE_HEIGHT = 180
MAX_CENTER_JUMP_PX = 90

FRESH_CONFIDENCE = 255
HELD_CONFIDENCE = 160
NO_CONFIDENCE = 0


def _round_int(value):
    if value >= 0:
        return int(value + 0.5)
    return int(value - 0.5)


class FaceTrackingFilter:
    def __init__(
        self,
        smoothing_alpha=SMOOTHING_ALPHA,
        detection_hold_ms=DETECTION_HOLD_MS,
        max_consecutive_misses=MAX_CONSECUTIVE_MISSES,
        min_face_width=MIN_FACE_WIDTH,
        min_face_height=MIN_FACE_HEIGHT,
        max_face_width=MAX_FACE_WIDTH,
        max_face_height=MAX_FACE_HEIGHT,
        max_center_jump_px=MAX_CENTER_JUMP_PX,
    ):
        self.smoothing_alpha = smoothing_alpha
        self.detection_hold_ms = detection_hold_ms
        self.max_consecutive_misses = max_consecutive_misses
        self.min_face_width = min_face_width
        self.min_face_height = min_face_height
        self.max_face_width = max_face_width
        self.max_face_height = max_face_height
        self.max_center_jump_px = max_center_jump_px
        self.reset()

    def reset(self):
        self.has_target = False
        self.filtered_x = 0.0
        self.filtered_y = 0.0
        self.filtered_width = 0.0
        self.filtered_height = 0.0
        self.last_detected_ms = 0
        self.consecutive_misses = 0

    def update(self, face, now_ms, frame_center_x, frame_center_y):
        measured = self._measurement_from_face(face, frame_center_x, frame_center_y)
        if measured and self._accepts_measurement(measured, now_ms):
            self._update_filter(measured, now_ms)
            return self._result(FRESH_CONFIDENCE, True)

        self.consecutive_misses += 1
        if self._can_hold_target(now_ms):
            return self._result(HELD_CONFIDENCE, True)

        self.reset()
        return (0, 0, 0, 0, NO_CONFIDENCE, False)

    def _measurement_from_face(self, face, frame_center_x, frame_center_y):
        if not face:
            return None
        x, y, width, height = face
        if (
            width < self.min_face_width or
            height < self.min_face_height or
            width > self.max_face_width or
            height > self.max_face_height
        ):
            return None
        center_x = x + ((width + 1) // 2) - frame_center_x
        center_y = y + ((height + 1) // 2) - frame_center_y
        return (center_x, center_y, width, height)

    def _accepts_measurement(self, measurement, now_ms):
        if not self.has_target or not self._recent_detection(now_ms):
            return True

        center_x, center_y, _, _ = measurement
        return (
            abs(center_x - self.filtered_x) <= self.max_center_jump_px and
            abs(center_y - self.filtered_y) <= self.max_center_jump_px
        )

    def _update_filter(self, measurement, now_ms):
        center_x, center_y, width, height = measurement
        if not self.has_target or not self._recent_detection(now_ms):
            self.filtered_x = float(center_x)
            self.filtered_y = float(center_y)
            self.filtered_width = float(width)
            self.filtered_height = float(height)
            self.has_target = True
        else:
            alpha = self.smoothing_alpha
            self.filtered_x += alpha * (center_x - self.filtered_x)
            self.filtered_y += alpha * (center_y - self.filtered_y)
            self.filtered_width += alpha * (width - self.filtered_width)
            self.filtered_height += alpha * (height - self.filtered_height)

        self.last_detected_ms = now_ms
        self.consecutive_misses = 0

    def _can_hold_target(self, now_ms):
        return (
            self.has_target and
            self._recent_detection(now_ms) and
            self.consecutive_misses <= self.max_consecutive_misses
        )

    def _recent_detection(self, now_ms):
        return self._elapsed_ms(now_ms, self.last_detected_ms) <= self.detection_hold_ms

    def _elapsed_ms(self, now_ms, earlier_ms):
        if now_ms >= earlier_ms:
            return now_ms - earlier_ms
        return now_ms

    def _result(self, confidence, detected):
        return (
            _round_int(self.filtered_x),
            _round_int(self.filtered_y),
            _round_int(self.filtered_width),
            _round_int(self.filtered_height),
            confidence,
            detected,
        )
