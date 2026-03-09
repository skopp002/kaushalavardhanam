"""Amazon Nova Sonic speech-to-speech client via Bedrock.

Sends audio to Nova Sonic for conversational AI processing and receives
spoken audio responses. Falls back to text-based converse API or mock mode
when bidirectional streaming is unavailable.
"""

import base64
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config as BotoConfig

from config import (
    AWS_REGION,
    NOVA_SONIC_MODEL_ID,
    SAMPLE_RATE,
    BEDROCK_TIMEOUT_SEC,
    BEDROCK_RETRY_COUNT,
)

logger = logging.getLogger(__name__)


@dataclass
class SonicResponse:
    audio: Optional[np.ndarray]
    text: Optional[str]
    latency_ms: float
    success: bool
    error: Optional[str] = None


class NovaSonicClient:
    """Client for Amazon Nova Sonic speech-to-speech via Bedrock.

    Primary approach: Bedrock converse-stream API with audio sent as base64.
    Fallback: text-based converse API (TTS handled separately by the caller).
    Mock mode: returns synthetic responses when AWS credentials are unavailable.
    """

    def __init__(self, region: str = AWS_REGION, model_id: str = NOVA_SONIC_MODEL_ID):
        self.region = region
        self.model_id = model_id
        self._client: Optional[boto3.client] = None
        self._mock_mode = False

    @property
    def client(self):
        if self._client is None:
            try:
                boto_config = BotoConfig(
                    region_name=self.region,
                    read_timeout=int(BEDROCK_TIMEOUT_SEC),
                    retries={"max_attempts": 0},
                )
                self._client = boto3.client("bedrock-runtime", config=boto_config)
            except (BotoCoreError, Exception) as e:
                logger.warning("Failed to create Bedrock client, enabling mock mode: %s", e)
                self._mock_mode = True
        return self._client

    def check_connectivity(self) -> bool:
        """Verify that the Bedrock API is reachable."""
        try:
            client = self.client
            if client is None or self._mock_mode:
                return False
            client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({"inputText": "ping"}),
                contentType="application/json",
                accept="application/json",
            )
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            # ValidationException means the API is reachable but input was wrong — that's fine
            if error_code == "ValidationException":
                return True
            logger.warning("Bedrock connectivity check failed: %s", e)
            return False
        except Exception as e:
            logger.warning("Bedrock connectivity check failed: %s", e)
            return False

    def process_speech(
        self,
        audio: np.ndarray,
        sample_rate: int = SAMPLE_RATE,
        system_prompt: str = None,
        conversation_history: list = None,
    ) -> SonicResponse:
        """Process speech audio through Nova Sonic and return a response.

        Attempts the converse API with audio content. If that fails, falls back
        to a text-based flow. In mock mode, returns a synthetic response.
        """
        if self._mock_mode:
            return self._mock_response(audio)

        return self._invoke_with_retry(
            audio=audio,
            sample_rate=sample_rate,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
        )

    def _invoke_with_retry(
        self,
        audio: np.ndarray,
        sample_rate: int,
        system_prompt: Optional[str],
        conversation_history: Optional[list],
    ) -> SonicResponse:
        """Invoke Bedrock with retry logic."""
        last_error = None

        for attempt in range(1 + BEDROCK_RETRY_COUNT):
            if attempt > 0:
                logger.info("Retry attempt %d for Nova Sonic", attempt)

            try:
                return self._invoke_converse(audio, sample_rate, system_prompt, conversation_history)
            except Exception as e:
                last_error = e
                logger.warning("Nova Sonic attempt %d failed: %s", attempt + 1, e)

        return SonicResponse(
            audio=None,
            text=None,
            latency_ms=0.0,
            success=False,
            error=f"All attempts failed. Last error: {last_error}",
        )

    def _invoke_converse(
        self,
        audio: np.ndarray,
        sample_rate: int,
        system_prompt: Optional[str],
        conversation_history: Optional[list],
    ) -> SonicResponse:
        """Invoke Nova Sonic via the Bedrock converse API with audio input."""
        client = self.client
        if client is None:
            raise RuntimeError("Bedrock client not available")

        audio_bytes = self._encode_audio(audio)
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        messages = []
        if conversation_history:
            messages.extend(conversation_history)

        messages.append({
            "role": "user",
            "content": [
                {
                    "audio": {
                        "format": "pcm",
                        "source": {"bytes": audio_b64},
                    }
                }
            ],
        })

        converse_params = {
            "modelId": self.model_id,
            "messages": messages,
        }

        if system_prompt:
            converse_params["system"] = [{"text": system_prompt}]

        start = time.monotonic()
        try:
            response = client.converse(**converse_params)
            latency_ms = (time.monotonic() - start) * 1000

            output = response.get("output", {})
            message = output.get("message", {})
            content_blocks = message.get("content", [])

            response_text = None
            response_audio = None

            for block in content_blocks:
                if "text" in block:
                    response_text = block["text"]
                if "audio" in block:
                    audio_data = block["audio"]
                    if "source" in audio_data and "bytes" in audio_data["source"]:
                        raw = base64.b64decode(audio_data["source"]["bytes"])
                        response_audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

            return SonicResponse(
                audio=response_audio,
                text=response_text,
                latency_ms=latency_ms,
                success=True,
            )

        except ClientError as e:
            latency_ms = (time.monotonic() - start) * 1000
            error_code = e.response["Error"]["Code"]

            if error_code == "ValidationException":
                logger.info("Converse API does not support audio input, falling back to text flow")
                return self._invoke_text_fallback(audio, sample_rate, system_prompt, conversation_history)

            raise

    def _invoke_text_fallback(
        self,
        audio: np.ndarray,
        sample_rate: int,
        system_prompt: Optional[str],
        conversation_history: Optional[list],
    ) -> SonicResponse:
        """Fallback: send audio description as text, get text response.

        When the streaming/audio API isn't available, we send a text prompt
        indicating audio was received. TTS is handled separately by the caller.
        """
        client = self.client
        if client is None:
            raise RuntimeError("Bedrock client not available")

        duration_sec = len(audio) / SAMPLE_RATE
        messages = []
        if conversation_history:
            messages.extend(conversation_history)

        messages.append({
            "role": "user",
            "content": [
                {"text": f"[Audio input received: {duration_sec:.1f}s of speech. Please respond conversationally.]"}
            ],
        })

        converse_params = {
            "modelId": self.model_id,
            "messages": messages,
        }
        if system_prompt:
            converse_params["system"] = [{"text": system_prompt}]

        start = time.monotonic()
        response = client.converse(**converse_params)
        latency_ms = (time.monotonic() - start) * 1000

        output = response.get("output", {})
        message = output.get("message", {})
        content_blocks = message.get("content", [])

        response_text = None
        for block in content_blocks:
            if "text" in block:
                response_text = block["text"]
                break

        return SonicResponse(
            audio=None,
            text=response_text,
            latency_ms=latency_ms,
            success=True,
        )

    def _mock_response(self, audio: np.ndarray) -> SonicResponse:
        """Generate a mock response for testing without AWS credentials."""
        start = time.monotonic()
        duration_sec = len(audio) / SAMPLE_RATE

        mock_audio = np.zeros(int(SAMPLE_RATE * 1.0), dtype=np.float32)
        latency_ms = (time.monotonic() - start) * 1000

        return SonicResponse(
            audio=mock_audio,
            text=f"[Mock response for {duration_sec:.1f}s audio input]",
            latency_ms=latency_ms,
            success=True,
        )

    @staticmethod
    def _encode_audio(audio: np.ndarray) -> bytes:
        """Convert float32 audio array to 16-bit PCM bytes."""
        if audio.dtype == np.float32 or audio.dtype == np.float64:
            clipped = np.clip(audio, -1.0, 1.0)
            pcm = (clipped * 32767).astype(np.int16)
        else:
            pcm = audio.astype(np.int16)
        return pcm.tobytes()
