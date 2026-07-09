"""Thin wrapper over the ``reachy-mini`` SDK: camera, microphone, speaker, head.

All hardware access in Mitra goes through this module (DESIGN §2). The same
wrapper talks to a real Reachy Mini Lite over USB or to the MuJoCo simulation
daemon (``mjpython -m reachy_mini.daemon.app.main --sim``) — the daemon API is
identical, so nothing above this layer knows which one is running.
``FakeReachy`` is the in-process test double (no daemon at all).
"""

from __future__ import annotations

import threading
import time
from collections import deque

import numpy as np

from mitra.audio import resample

_PLAYBACK_CHUNK_S = 0.25  # push audio in small chunks so barge-in can stop it


class ReachyRobot:
    """Connects to the reachy-mini daemon (real robot or --sim)."""

    def __init__(self, mic_chunk_s: float = 0.08):
        try:
            from reachy_mini import ReachyMini
            from reachy_mini.utils import create_head_pose
        except ImportError as e:
            raise ImportError(
                "The 'reachy-mini' package is required for the real/sim robot. "
                "Install with: pip install 'reachy-mini[mujoco]'"
            ) from e
        self._create_head_pose = create_head_pose
        self._mini = ReachyMini()
        self._mini.media.start_recording()
        self._mini.media.start_playing()
        self._in_sr = int(self._mini.media.get_input_audio_samplerate())
        self._out_sr = int(self._mini.media.get_output_audio_samplerate())
        self._mic_chunk_s = mic_chunk_s
        self._stop_playback = threading.Event()
        self._playing = threading.Event()
        # Dedicated drain thread: the SDK's appsink queue holds only ~2 s, so
        # the mic must be drained at realtime even while consumers (wake ASR,
        # Whisper) block — otherwise GStreamer drops samples.
        self._closed = threading.Event()
        self._mic_buf: deque[np.ndarray] = deque()
        self._mic_samples = 0
        self._mic_cap = 30 * self._in_sr  # ring: keep at most 30 s
        self._mic_ready = threading.Condition()
        threading.Thread(target=self._mic_drain_loop, daemon=True).start()

    # --- camera ---

    def camera_read(self) -> np.ndarray:
        """One frame, numpy (H, W, 3) uint8."""
        return self._mini.media.get_frame()

    # --- microphone ---

    @property
    def mic_samplerate(self) -> int:
        return self._in_sr

    def _mic_drain_loop(self) -> None:
        """Continuously pull ~10 ms buffers from the SDK into our ring buffer.

        get_audio_sample() returns ONE buffered chunk per call (or None), so
        it must be called in a tight loop to keep up with realtime.
        """
        while not self._closed.is_set():
            try:
                samples = self._mini.media.get_audio_sample()
            except Exception:
                time.sleep(0.1)
                continue
            if samples is None or len(samples) == 0:
                time.sleep(0.003)
                continue
            mono = np.asarray(samples, dtype=np.float32)
            if mono.ndim == 2:
                mono = mono.mean(axis=1)
            with self._mic_ready:
                self._mic_buf.append(mono)
                self._mic_samples += len(mono)
                while self._mic_samples > self._mic_cap:  # drop oldest
                    self._mic_samples -= len(self._mic_buf.popleft())
                self._mic_ready.notify_all()

    def mic_read(self) -> np.ndarray:
        """Mono float32 chunk of ~mic_chunk_s from the ring buffer; blocks up
        to ~one chunk length. Slow consumers delay processing, never capture."""
        target = int(self._in_sr * self._mic_chunk_s)
        deadline = time.monotonic() + max(0.2, 2 * self._mic_chunk_s)
        with self._mic_ready:
            while self._mic_samples < target and not self._closed.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._mic_ready.wait(timeout=remaining)
            if not self._mic_buf:
                return np.zeros(0, dtype=np.float32)
            chunks, taken = [], 0
            while self._mic_buf and taken < target:
                chunk = self._mic_buf.popleft()
                chunks.append(chunk)
                taken += len(chunk)
            self._mic_samples -= taken
        return np.concatenate(chunks)

    # --- speaker ---

    def speaker_play(self, wav: np.ndarray, samplerate: int, block: bool = True) -> None:
        wav = resample(wav, samplerate, self._out_sr)
        self._stop_playback.clear()
        thread = threading.Thread(target=self._playback_worker, args=(wav,), daemon=True)
        self._playing.set()
        thread.start()
        if block:
            thread.join()

    def _playback_worker(self, wav: np.ndarray) -> None:
        chunk = max(1, int(self._out_sr * _PLAYBACK_CHUNK_S))
        try:
            for i in range(0, len(wav), chunk):
                if self._stop_playback.is_set():
                    break
                part = wav[i:i + chunk]
                self._mini.media.push_audio_sample(part.reshape(-1, 1))
                # push is non-blocking; pace at realtime so stop can interrupt
                time.sleep(len(part) / self._out_sr)
        finally:
            self._playing.clear()

    def speaker_stop(self) -> None:
        self._stop_playback.set()

    def speaker_busy(self) -> bool:
        return self._playing.is_set()

    # --- head ---

    def nod(self) -> None:
        """Single brief nod — the wake acknowledgment (FR-1.3, FR-5.1)."""
        down = self._create_head_pose(pitch=12, degrees=True)
        self._mini.goto_target(head=down, duration=0.3)
        self._mini.goto_target(head=self._create_head_pose(), duration=0.3)

    def close(self) -> None:
        self._closed.set()
        self._stop_playback.set()
        with self._mic_ready:
            self._mic_ready.notify_all()
        try:
            self._mini.media.stop_recording()
            self._mini.media.stop_playing()
        finally:
            self._mini.__exit__(None, None, None)


class FakeReachy:
    """Test double with the same surface as ReachyRobot (DESIGN §2, §9)."""

    def __init__(self, mic_samplerate: int = 16000):
        self._mic_sr = mic_samplerate
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.nods = 0
        self.played: list[np.ndarray] = []
        self.stops = 0
        self.closed = False
        self.hold_playback = False  # True → speaker stays busy until speaker_stop()
        self._playing = False
        self._mic_queue: deque[np.ndarray] = deque()

    # camera
    def camera_read(self) -> np.ndarray:
        return self.frame

    # microphone
    @property
    def mic_samplerate(self) -> int:
        return self._mic_sr

    def feed_mic(self, chunk: np.ndarray) -> None:
        self._mic_queue.append(np.asarray(chunk, dtype=np.float32))

    def mic_read(self) -> np.ndarray:
        if self._mic_queue:
            return self._mic_queue.popleft()
        return np.zeros(0, dtype=np.float32)

    # speaker
    def speaker_play(self, wav: np.ndarray, samplerate: int, block: bool = True) -> None:
        self.played.append(np.asarray(wav))
        self._playing = self.hold_playback and not block

    def speaker_stop(self) -> None:
        self.stops += 1
        self._playing = False

    def speaker_busy(self) -> bool:
        return self._playing

    # head
    def nod(self) -> None:
        self.nods += 1

    def close(self) -> None:
        self.closed = True
