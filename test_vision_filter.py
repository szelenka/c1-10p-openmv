import unittest

from vision_filter import (
    FRESH_CONFIDENCE,
    HELD_CONFIDENCE,
    NO_CONFIDENCE,
    FaceTrackingFilter,
)


FRAME_CENTER_X = 160
FRAME_CENTER_Y = 120


class FaceTrackingFilterTest(unittest.TestCase):
    def make_filter(self, **overrides):
        defaults = {
            "smoothing_alpha": 0.5,
            "detection_hold_ms": 300,
            "max_consecutive_misses": 3,
            "max_center_jump_px": 50,
        }
        defaults.update(overrides)
        return FaceTrackingFilter(**defaults)

    def update(self, tracker, face, now_ms):
        return tracker.update(face, now_ms, FRAME_CENTER_X, FRAME_CENTER_Y)

    def test_first_valid_detection_initializes_filter_directly(self):
        tracker = self.make_filter()

        result = self.update(tracker, (130, 90, 60, 60), 1000)

        self.assertEqual((0, 0, 60, 60, FRESH_CONFIDENCE, True), result)
        self.assertTrue(tracker.has_target)
        self.assertEqual(0.0, tracker.filtered_x)
        self.assertEqual(0.0, tracker.filtered_y)

    def test_repeated_detections_smooth_toward_measured_position(self):
        tracker = self.make_filter()
        self.update(tracker, (110, 90, 40, 40), 1000)

        result = self.update(tracker, (150, 90, 40, 40), 1100)

        self.assertEqual((-10, -10, 40, 40, FRESH_CONFIDENCE, True), result)

    def test_one_missed_frame_inside_hold_time_keeps_last_target(self):
        tracker = self.make_filter()
        self.update(tracker, (130, 90, 60, 60), 1000)

        result = self.update(tracker, None, 1100)

        self.assertEqual((0, 0, 60, 60, HELD_CONFIDENCE, True), result)

    def test_miss_after_hold_expiry_reports_no_detection(self):
        tracker = self.make_filter()
        self.update(tracker, (130, 90, 60, 60), 1000)
        self.update(tracker, None, 1100)

        result = self.update(tracker, None, 1401)

        self.assertEqual((0, 0, 0, 0, NO_CONFIDENCE, False), result)
        self.assertFalse(tracker.has_target)

    def test_too_many_consecutive_misses_reports_no_detection(self):
        tracker = self.make_filter(max_consecutive_misses=1, detection_hold_ms=1000)
        self.update(tracker, (130, 90, 60, 60), 1000)
        self.update(tracker, None, 1100)

        result = self.update(tracker, None, 1200)

        self.assertEqual((0, 0, 0, 0, NO_CONFIDENCE, False), result)

    def test_small_invalid_box_is_rejected(self):
        tracker = self.make_filter()

        result = self.update(tracker, (150, 110, 10, 10), 1000)

        self.assertEqual((0, 0, 0, 0, NO_CONFIDENCE, False), result)

    def test_sudden_jump_is_rejected_while_target_is_active(self):
        tracker = self.make_filter(max_center_jump_px=50)
        self.update(tracker, (130, 90, 60, 60), 1000)

        result = self.update(tracker, (245, 90, 60, 60), 1100)

        self.assertEqual((0, 0, 60, 60, HELD_CONFIDENCE, True), result)
        self.assertEqual(0.0, tracker.filtered_x)

    def test_new_detection_after_timeout_reacquires_directly(self):
        tracker = self.make_filter(max_center_jump_px=50, detection_hold_ms=300)
        self.update(tracker, (130, 90, 60, 60), 1000)

        result = self.update(tracker, (245, 90, 60, 60), 1401)

        self.assertEqual((115, 0, 60, 60, FRESH_CONFIDENCE, True), result)

    def test_reset_clears_active_target(self):
        tracker = self.make_filter()
        self.update(tracker, (130, 90, 60, 60), 1000)

        tracker.reset()

        self.assertFalse(tracker.has_target)
        self.assertEqual((0, 0, 0, 0, NO_CONFIDENCE, False), self.update(tracker, None, 1100))


if __name__ == "__main__":
    unittest.main()
