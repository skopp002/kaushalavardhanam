"""Vision module for Mitra: camera capture and object recognition.

Provides a pluggable vision backend supporting YOLOv8 object detection
and a mock backend for testing without hardware or model dependencies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore[assignment]

from config import (
    CAMERA_INDEX,
    CAMERA_HEIGHT,
    CAMERA_WIDTH,
    IMAGE_DIR,
    OBJECT_CONFIDENCE_THRESHOLD,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ObjectDetection:
    """A single detected object in a frame."""

    label: str
    confidence: float
    bbox: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h


@dataclass
class VisionResult:
    """Result of running object recognition on a frame."""

    detections: List[ObjectDetection]
    frame: np.ndarray
    timestamp: str  # ISO-8601 format


# ---------------------------------------------------------------------------
# Backend helpers
# ---------------------------------------------------------------------------

def _run_yolo(frame: np.ndarray, confidence_threshold: float) -> List[ObjectDetection]:
    """Run YOLOv8 inference on *frame* and return detections."""
    try:
        from ultralytics import YOLO  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "ultralytics package is required for the 'yolo' backend. "
            "Install it with: pip install ultralytics"
        ) from exc

    # Cache the model on the function object to avoid reloading every call.
    if not hasattr(_run_yolo, "_model"):
        logger.info("Loading YOLOv8s model (first call)...")
        _run_yolo._model = YOLO("yolov8s.pt")  # type: ignore[attr-defined]

    model = _run_yolo._model  # type: ignore[attr-defined]
    results = model(frame, verbose=False)

    detections: List[ObjectDetection] = []
    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
        for box in boxes:
            conf = float(box.conf[0])
            if conf < confidence_threshold:
                continue
            cls_id = int(box.cls[0])
            label = model.names.get(cls_id, f"class_{cls_id}")
            # Convert from xyxy to xywh
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            bbox = (int(x1), int(y1), int(x2 - x1), int(y2 - y1))
            detections.append(ObjectDetection(label=label, confidence=round(conf, 4), bbox=bbox))

    return detections


def _run_mock(frame: np.ndarray, confidence_threshold: float) -> List[ObjectDetection]:
    """Return placeholder detections for testing without a real model."""
    h, w = frame.shape[:2]
    mock_objects = [
        ObjectDetection(label="person", confidence=0.92, bbox=(50, 50, w // 3, h // 2)),
        ObjectDetection(label="chair", confidence=0.78, bbox=(w // 2, h // 3, w // 4, h // 3)),
        ObjectDetection(label="cup", confidence=0.65, bbox=(w // 4, h // 4, 80, 80)),
    ]
    return [d for d in mock_objects if d.confidence >= confidence_threshold]


_BACKENDS = {
    "yolo": _run_yolo,
    "mock": _run_mock,
}


# ---------------------------------------------------------------------------
# VisionModule
# ---------------------------------------------------------------------------

class VisionModule:
    """Camera capture and object recognition with pluggable backends.

    Parameters
    ----------
    backend : str
        Detection backend name (``"yolo"`` or ``"mock"``).
    camera_index : int
        Index of the camera device (default from config).
    use_file : Path | None
        If provided, read this image file instead of using a live camera.
    """

    def __init__(
        self,
        backend: str = "mock",
        camera_index: int = CAMERA_INDEX,
        use_file: Optional[Path] = None,
    ) -> None:
        if cv2 is None:
            raise ImportError(
                "opencv-python is required for VisionModule. "
                "Install it with: pip install opencv-python"
            )

        if backend not in _BACKENDS:
            raise ValueError(f"Unknown backend '{backend}'. Choose from: {list(_BACKENDS)}")

        self._backend_name = backend
        self._backend_fn = _BACKENDS[backend]
        self._camera_index = camera_index
        self._use_file = Path(use_file) if use_file is not None else None
        self._confidence_threshold = OBJECT_CONFIDENCE_THRESHOLD

        self._last_frame: Optional[np.ndarray] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self._available = False

        self._init_source()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_source(self) -> None:
        """Open the camera or validate the image file."""
        if self._use_file is not None:
            if not self._use_file.is_file():
                logger.error("Image file not found: %s", self._use_file)
                self._available = False
                return
            # Quick validation: try reading the file
            test_frame = cv2.imread(str(self._use_file))
            if test_frame is None:
                logger.error("Failed to decode image file: %s", self._use_file)
                self._available = False
                return
            self._available = True
            logger.info("VisionModule initialised with image file: %s", self._use_file)
            return

        # Live camera
        try:
            self._cap = cv2.VideoCapture(self._camera_index)
            if not self._cap.isOpened():
                logger.error(
                    "Camera index %d could not be opened.", self._camera_index
                )
                self._available = False
                return
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            self._available = True
            logger.info(
                "VisionModule initialised with camera index %d (%dx%d).",
                self._camera_index,
                CAMERA_WIDTH,
                CAMERA_HEIGHT,
            )
        except Exception:
            logger.exception("Error opening camera index %d", self._camera_index)
            self._available = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """Whether the vision source (camera or file) is usable."""
        return self._available

    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame from the configured source.

        Returns
        -------
        np.ndarray or None
            BGR image array, or ``None`` if capture failed.
        """
        if not self._available:
            logger.warning("Vision source is not available; cannot capture frame.")
            return None

        frame: Optional[np.ndarray] = None

        if self._use_file is not None:
            frame = cv2.imread(str(self._use_file))
            if frame is None:
                logger.error("Failed to read image file: %s", self._use_file)
                return None
            # Ensure minimum resolution by resizing if necessary
            h, w = frame.shape[:2]
            if w < CAMERA_WIDTH or h < CAMERA_HEIGHT:
                frame = cv2.resize(frame, (CAMERA_WIDTH, CAMERA_HEIGHT))
        else:
            if self._cap is None or not self._cap.isOpened():
                logger.error("Camera is not open.")
                self._available = False
                return None
            ret, frame = self._cap.read()
            if not ret or frame is None:
                logger.error("Failed to read frame from camera.")
                return None

        self._last_frame = frame
        return frame

    def recognize_objects(self, frame: Optional[np.ndarray] = None) -> VisionResult:
        """Run object recognition on a frame.

        If *frame* is ``None``, the last captured frame is reused (useful for
        follow-up VQA questions on the same scene).

        Parameters
        ----------
        frame : np.ndarray or None
            BGR image to analyse. Captures a new frame when ``None`` and no
            previous frame is cached.

        Returns
        -------
        VisionResult
            Detections and the frame used.

        Raises
        ------
        RuntimeError
            If no frame is available from any source.
        """
        if frame is None:
            frame = self._last_frame
        if frame is None:
            frame = self.capture_frame()
        if frame is None:
            raise RuntimeError(
                "No frame available. Ensure a camera or image file is configured."
            )

        self._last_frame = frame
        timestamp = datetime.now(timezone.utc).isoformat()

        detections = self._backend_fn(frame, self._confidence_threshold)
        logger.info(
            "Recognised %d object(s) via '%s' backend.",
            len(detections),
            self._backend_name,
        )

        return VisionResult(detections=detections, frame=frame, timestamp=timestamp)

    def get_last_frame(self) -> Optional[np.ndarray]:
        """Return the most recently captured frame, or ``None``."""
        return self._last_frame

    def save_frame(self, frame: np.ndarray, filepath: Optional[Path] = None) -> Path:
        """Write *frame* to disk as a PNG image.

        Parameters
        ----------
        frame : np.ndarray
            BGR image array.
        filepath : Path or None
            Destination path.  When ``None``, a timestamped file is created
            inside the configured ``IMAGE_DIR``.

        Returns
        -------
        Path
            Absolute path to the saved image.
        """
        if filepath is None:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")
            filepath = IMAGE_DIR / f"frame_{ts}.png"
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(filepath), frame)
        logger.info("Frame saved to %s", filepath)
        return filepath

    def stop(self) -> None:
        """Release camera resources."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera released.")
        self._available = False

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "VisionModule":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()
