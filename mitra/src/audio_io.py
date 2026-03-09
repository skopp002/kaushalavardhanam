"""Audio input/output with Voice Activity Detection for Mitra conversational robot."""

import logging
import struct
import time
import wave
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Optional

import numpy as np

from config import (
    AUDIO_CHANNELS,
    AUDIO_CHUNK_SIZE,
    IDLE_TIMEOUT_SEC,
    SAMPLE_RATE,
    SILENCE_TIMEOUT_SEC,
    VAD_AGGRESSIVENESS,
)

logger = logging.getLogger(__name__)


def load_audio(filepath: Path, target_sr: int = SAMPLE_RATE) -> np.ndarray:
    """Load a WAV file and return audio as a float32 numpy array normalized to [-1, 1]."""
    try:
        import librosa
        audio, _ = librosa.load(filepath, sr=target_sr, mono=True)
        return audio
    except ImportError:
        import soundfile as sf
        audio, sr = sf.read(filepath, dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != target_sr:
            # Simple resampling via scipy if available
            try:
                from scipy.signal import resample
                num_samples = int(len(audio) * target_sr / sr)
                audio = resample(audio, num_samples).astype(np.float32)
            except ImportError:
                pass
        return audio


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    """Normalize audio amplitude to [-1, 1] range."""
    if len(audio) == 0:
        return audio
    max_val = np.abs(audio).max()
    if max_val > 0:
        return audio / max_val
    return audio


def trim_silence(audio: np.ndarray, sr: int, top_db: int = 20) -> np.ndarray:
    """Remove leading and trailing silence from audio."""
    try:
        import librosa
        trimmed, _ = librosa.effects.trim(audio, top_db=top_db)
        return trimmed
    except ImportError:
        # Simple energy-based trim: remove samples below threshold
        threshold = np.max(np.abs(audio)) * (10 ** (-top_db / 20))
        above = np.where(np.abs(audio) > threshold)[0]
        if len(above) == 0:
            return audio
        return audio[above[0]:above[-1] + 1]


def _float_to_int16(audio: np.ndarray) -> np.ndarray:
    """Convert float32 audio [-1, 1] to int16."""
    return np.clip(audio * 32767, -32768, 32767).astype(np.int16)


def _int16_to_float(audio: np.ndarray) -> np.ndarray:
    """Convert int16 audio to float32 [-1, 1]."""
    return audio.astype(np.float32) / 32768.0


class AudioIO:
    """Handles microphone capture with VAD and speaker playback.

    Supports two modes:
    - Live mode: captures from microphone, plays through speaker.
    - File mode: reads from a WAV file, writes output to a directory.
    """

    def __init__(
        self,
        use_file_io: bool = False,
        input_file: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        self._use_file_io = use_file_io
        self._input_file = input_file
        self._output_dir = output_dir
        self._stop_event = Event()
        self._last_speech_time: float = time.monotonic()
        self._lock = Lock()
        self._listening = False

        self._mic_available = False
        self._speaker_available = False
        self._stream = None
        self._pyaudio_instance = None
        self._listen_thread: Optional[Thread] = None
        self._utterance_buffer: list[bytes] = []
        self._utterance_ready = Event()

        self._vad = None

        if use_file_io:
            self._mic_available = input_file is not None and input_file.exists()
            self._speaker_available = output_dir is not None
            if self._output_dir:
                self._output_dir.mkdir(parents=True, exist_ok=True)
            self._output_counter = 0
        else:
            self._init_live_audio()
            self._init_vad()

    def _init_vad(self) -> None:
        """Initialize the WebRTC voice activity detector."""
        try:
            import webrtcvad

            self._vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        except ImportError:
            logger.warning("webrtcvad not installed; VAD will be disabled")
        except Exception as e:
            logger.warning("Failed to initialize VAD: %s", e)

    def _init_live_audio(self) -> None:
        """Probe for microphone and speaker availability using PyAudio."""
        try:
            import pyaudio

            pa = pyaudio.PyAudio()
            self._pyaudio_instance = pa

            info = pa.get_host_api_info_by_index(0)
            device_count = info.get("deviceCount", 0)

            for i in range(device_count):
                dev = pa.get_device_info_by_index(i)
                if dev.get("maxInputChannels", 0) > 0:
                    self._mic_available = True
                if dev.get("maxOutputChannels", 0) > 0:
                    self._speaker_available = True

            if not self._mic_available:
                logger.warning("No microphone detected")
            if not self._speaker_available:
                logger.warning("No speaker detected")

        except ImportError:
            logger.warning("pyaudio not installed; live audio unavailable")
        except Exception as e:
            logger.warning("Failed to initialize audio hardware: %s", e)

    @property
    def is_available(self) -> bool:
        """True if at least a microphone or speaker is accessible."""
        return self._mic_available or self._speaker_available

    def is_idle(self) -> bool:
        """True if no speech has been detected for IDLE_TIMEOUT_SEC."""
        return (time.monotonic() - self._last_speech_time) > IDLE_TIMEOUT_SEC

    def start_listening(self) -> None:
        """Begin VAD-monitored listening on the microphone or prepare file input."""
        if self._listening:
            return

        self._stop_event.clear()
        self._listening = True
        self._last_speech_time = time.monotonic()

        if self._use_file_io:
            return

        if not self._mic_available:
            logger.error("Cannot start listening: no microphone available")
            self._listening = False
            return

        self._listen_thread = Thread(target=self._capture_loop, daemon=True)
        self._listen_thread.start()

    def _capture_loop(self) -> None:
        """Background thread that captures audio chunks and applies VAD."""
        import pyaudio

        pa = self._pyaudio_instance
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=AUDIO_CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=AUDIO_CHUNK_SIZE,
            )
        except Exception as e:
            logger.error("Failed to open audio stream: %s", e)
            self._listening = False
            return

        self._stream = stream
        speech_frames: list[bytes] = []
        silence_start: Optional[float] = None
        in_speech = False

        try:
            while not self._stop_event.is_set():
                try:
                    data = stream.read(AUDIO_CHUNK_SIZE, exception_on_overflow=False)
                except Exception as e:
                    logger.debug("Audio read error: %s", e)
                    continue

                is_speech = self._is_speech(data)

                if is_speech:
                    self._last_speech_time = time.monotonic()
                    speech_frames.append(data)
                    in_speech = True
                    silence_start = None
                elif in_speech:
                    speech_frames.append(data)
                    if silence_start is None:
                        silence_start = time.monotonic()
                    elif (time.monotonic() - silence_start) >= SILENCE_TIMEOUT_SEC:
                        with self._lock:
                            self._utterance_buffer = list(speech_frames)
                        self._utterance_ready.set()
                        speech_frames.clear()
                        in_speech = False
                        silence_start = None
        finally:
            stream.stop_stream()
            stream.close()
            self._stream = None

    def _is_speech(self, audio_bytes: bytes) -> bool:
        """Determine whether an audio chunk contains speech using VAD."""
        if self._vad is None:
            rms = struct.unpack(f"{len(audio_bytes) // 2}h", audio_bytes)
            energy = sum(s * s for s in rms) / len(rms)
            return energy > 500
        try:
            return self._vad.is_speech(audio_bytes, SAMPLE_RATE)
        except Exception:
            return False

    def get_utterance(self) -> Optional[np.ndarray]:
        """Block until a complete utterance is captured, delimited by silence.

        In file mode, reads the entire input file as a single utterance.
        Returns the utterance as a float32 numpy array, or None if stopped.
        """
        if self._use_file_io:
            return self._get_utterance_from_file()

        if not self._listening:
            logger.warning("get_utterance called before start_listening")
            return None

        while not self._stop_event.is_set():
            if self._utterance_ready.wait(timeout=0.5):
                self._utterance_ready.clear()
                with self._lock:
                    frames = self._utterance_buffer
                    self._utterance_buffer = []
                if frames:
                    raw = b"".join(frames)
                    int16_array = np.frombuffer(raw, dtype=np.int16)
                    return _int16_to_float(int16_array)

        return None

    def _get_utterance_from_file(self) -> Optional[np.ndarray]:
        """Read the input WAV file and return its contents as a float32 array."""
        if self._input_file is None or not self._input_file.exists():
            logger.error("Input file not found: %s", self._input_file)
            return None

        self._last_speech_time = time.monotonic()
        audio = load_audio(self._input_file, target_sr=SAMPLE_RATE)
        audio = normalize_audio(audio)
        audio = trim_silence(audio, SAMPLE_RATE)
        return audio

    def play_audio(self, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
        """Play audio through the speaker, or write to file in file-I/O mode.

        Args:
            audio: Float32 audio data in [-1, 1] range.
            sample_rate: Sample rate of the audio.
        """
        if self._use_file_io:
            self._write_audio_to_file(audio, sample_rate)
            return

        if not self._speaker_available:
            logger.warning("No speaker available for playback")
            return

        import pyaudio

        pa = self._pyaudio_instance
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=AUDIO_CHANNELS,
                rate=sample_rate,
                output=True,
            )
            int16_data = _float_to_int16(audio)
            stream.write(int16_data.tobytes())
            stream.stop_stream()
            stream.close()
        except Exception as e:
            logger.error("Playback failed: %s", e)

    def _write_audio_to_file(self, audio: np.ndarray, sample_rate: int) -> None:
        """Write audio to a WAV file in the output directory."""
        if self._output_dir is None:
            logger.error("No output directory configured for file I/O")
            return

        self._output_counter += 1
        filepath = self._output_dir / f"output_{self._output_counter:04d}.wav"

        int16_data = _float_to_int16(audio)
        with wave.open(str(filepath), "wb") as wf:
            wf.setnchannels(AUDIO_CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(int16_data.tobytes())

        logger.info("Wrote audio to %s", filepath)

    def play_file(self, filepath: Path) -> None:
        """Load a WAV file and play it through the speaker."""
        if not filepath.exists():
            logger.error("Audio file not found: %s", filepath)
            return

        audio = load_audio(filepath, target_sr=SAMPLE_RATE)
        self.play_audio(audio, sample_rate=SAMPLE_RATE)

    def stop(self) -> None:
        """Stop listening and release audio resources."""
        self._stop_event.set()
        self._listening = False

        if self._listen_thread is not None:
            self._listen_thread.join(timeout=3.0)
            self._listen_thread = None

        if self._pyaudio_instance is not None and not self._use_file_io:
            try:
                self._pyaudio_instance.terminate()
            except Exception:
                pass
            self._pyaudio_instance = None
