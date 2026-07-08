"""Tests for VisionModule with mock backend."""

import numpy as np
import pytest

from src.vision_module import VisionModule, VisionResult, ObjectDetection


@pytest.fixture
def vision_with_file(sample_image, tmp_dir):
    """VisionModule configured with a temp image file and mock backend."""
    import cv2

    img_path = tmp_dir / "test_input.png"
    cv2.imwrite(str(img_path), sample_image)
    vm = VisionModule(backend="mock", use_file=img_path)
    yield vm
    vm.stop()


class TestVisionModule:

    def test_capture_frame_returns_numpy_array(self, vision_with_file):
        frame = vision_with_file.capture_frame()
        assert frame is not None
        assert isinstance(frame, np.ndarray)
        assert frame.ndim == 3

    def test_recognize_objects_returns_vision_result(self, vision_with_file):
        frame = vision_with_file.capture_frame()
        result = vision_with_file.recognize_objects(frame)

        assert isinstance(result, VisionResult)
        assert isinstance(result.detections, list)
        assert len(result.detections) > 0

        for det in result.detections:
            assert isinstance(det, ObjectDetection)
            assert isinstance(det.label, str)
            assert 0.0 <= det.confidence <= 1.0

    def test_get_last_frame_returns_most_recent(self, vision_with_file):
        assert vision_with_file.get_last_frame() is None

        frame = vision_with_file.capture_frame()
        last = vision_with_file.get_last_frame()

        assert last is not None
        assert np.array_equal(frame, last)

    def test_save_frame_writes_image_file(self, vision_with_file, tmp_dir):
        frame = vision_with_file.capture_frame()
        out_path = tmp_dir / "saved_frame.png"
        result_path = vision_with_file.save_frame(frame, filepath=out_path)

        assert result_path.exists()
        assert result_path.stat().st_size > 0

    def test_is_available_with_mock_backend(self, vision_with_file):
        assert vision_with_file.is_available is True
