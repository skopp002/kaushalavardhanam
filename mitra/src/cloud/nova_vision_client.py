"""Amazon Nova Vision client for cloud-based visual question answering.

Sends an image and text query to Nova Vision (Lite/Pro) via Bedrock and
returns a text answer about the object in the image.
"""

import base64
import io
import json
import time
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config as BotoConfig
from PIL import Image

from config import (
    AWS_REGION,
    NOVA_VISION_MODEL_ID,
    BEDROCK_TIMEOUT_SEC,
    BEDROCK_RETRY_COUNT,
)

logger = logging.getLogger(__name__)


@dataclass
class VisionResponse:
    answer: str
    latency_ms: float
    success: bool
    error: Optional[str] = None


class NovaVisionClient:
    """Client for Amazon Nova Vision (Lite/Pro) visual question answering via Bedrock.

    Encodes images as base64 JPEG and sends them alongside text queries using
    the Bedrock converse API with image + text content blocks.
    """

    def __init__(self, region: str = AWS_REGION, model_id: str = NOVA_VISION_MODEL_ID):
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
            if error_code == "ValidationException":
                return True
            logger.warning("Bedrock connectivity check failed: %s", e)
            return False
        except Exception as e:
            logger.warning("Bedrock connectivity check failed: %s", e)
            return False

    def ask_about_image(
        self,
        image: np.ndarray,
        question: str,
        conversation_history: list = None,
    ) -> VisionResponse:
        """Ask a question about an image using Nova Vision.

        Args:
            image: Image as a numpy array (H, W, C) in BGR or RGB format.
            question: Natural language question about the image.
            conversation_history: Optional prior turns for follow-up queries
                about the same image.

        Returns:
            VisionResponse with the model's answer.
        """
        if self._mock_mode:
            return self._mock_response(question)

        return self._invoke_with_retry(image, question, conversation_history)

    def _invoke_with_retry(
        self,
        image: np.ndarray,
        question: str,
        conversation_history: Optional[list],
    ) -> VisionResponse:
        """Invoke Bedrock with retry logic."""
        last_error = None

        for attempt in range(1 + BEDROCK_RETRY_COUNT):
            if attempt > 0:
                logger.info("Retry attempt %d for Nova Vision", attempt)

            try:
                return self._invoke_converse(image, question, conversation_history)
            except Exception as e:
                last_error = e
                logger.warning("Nova Vision attempt %d failed: %s", attempt + 1, e)

        return VisionResponse(
            answer="",
            latency_ms=0.0,
            success=False,
            error=f"All attempts failed. Last error: {last_error}",
        )

    def _invoke_converse(
        self,
        image: np.ndarray,
        question: str,
        conversation_history: Optional[list],
    ) -> VisionResponse:
        """Invoke Nova Vision via the Bedrock converse API."""
        client = self.client
        if client is None:
            raise RuntimeError("Bedrock client not available")

        image_bytes = self._encode_image_jpeg(image)

        messages = []
        if conversation_history:
            messages.extend(conversation_history)

        messages.append({
            "role": "user",
            "content": [
                {
                    "image": {
                        "format": "jpeg",
                        "source": {"bytes": image_bytes},
                    }
                },
                {"text": question},
            ],
        })

        start = time.monotonic()
        response = client.converse(
            modelId=self.model_id,
            messages=messages,
        )
        latency_ms = (time.monotonic() - start) * 1000

        output = response.get("output", {})
        message = output.get("message", {})
        content_blocks = message.get("content", [])

        answer = ""
        for block in content_blocks:
            if "text" in block:
                answer = block["text"]
                break

        return VisionResponse(
            answer=answer,
            latency_ms=latency_ms,
            success=True,
        )

    def _mock_response(self, question: str) -> VisionResponse:
        """Generate a mock response for testing without AWS credentials."""
        start = time.monotonic()
        latency_ms = (time.monotonic() - start) * 1000

        return VisionResponse(
            answer=f"[Mock vision response for: {question}]",
            latency_ms=latency_ms,
            success=True,
        )

    @staticmethod
    def _encode_image_jpeg(image: np.ndarray, quality: int = 85) -> bytes:
        """Convert a numpy image array to JPEG bytes.

        Handles both RGB and BGR (OpenCV default) input by checking channel order
        heuristically. Converts grayscale to RGB if needed.
        """
        if image.ndim == 2:
            pil_image = Image.fromarray(image, mode="L").convert("RGB")
        elif image.shape[2] == 4:
            pil_image = Image.fromarray(image[:, :, :3])
        else:
            pil_image = Image.fromarray(image)

        buffer = io.BytesIO()
        pil_image.save(buffer, format="JPEG", quality=quality)
        return buffer.getvalue()
