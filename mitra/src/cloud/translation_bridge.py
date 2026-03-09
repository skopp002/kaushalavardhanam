"""Translation bridge between active languages and Hindi (bridge language).

Kannada uses Amazon Translate. Sanskrit uses a self-hosted IndicTrans2 sidecar.
If services are unavailable, falls back to a mock translator for testing.
"""

import time
import logging
from dataclasses import dataclass
from typing import Optional

import boto3
import requests
from botocore.exceptions import ClientError, BotoCoreError

from config import (
    AWS_REGION,
    BRIDGE_LANGUAGE,
    TRANSLATE_TIMEOUT_SEC,
    AMAZON_TRANSLATE_SUPPORTED,
    INDICTRANS2_REQUIRED,
    Language,
)

logger = logging.getLogger(__name__)

INDICTRANS2_URL = "http://localhost:8500/translate"


@dataclass
class TranslationResult:
    translated_text: str
    source_language: str
    target_language: str
    method: str  # "amazon_translate", "indictrans2", "mock"
    latency_ms: float


class TranslationBridge:
    """Translates between an active language (Kannada/Sanskrit) and the bridge language (Hindi).

    Hindi serves as the bridge because Amazon Nova Sonic supports it natively.
    If a language is ever supported directly by Nova Sonic, bridging can be skipped.
    """

    # Languages that Nova Sonic supports natively (no bridging needed)
    _native_nova_sonic_languages: set = set()

    def __init__(self, bridge_language: str = BRIDGE_LANGUAGE, region: str = AWS_REGION):
        self.bridge_language = bridge_language
        self.region = region
        self._translate_client: Optional[boto3.client] = None

    @property
    def translate_client(self):
        if self._translate_client is None:
            try:
                self._translate_client = boto3.client("translate", region_name=self.region)
            except (BotoCoreError, Exception) as e:
                logger.warning("Failed to create Amazon Translate client: %s", e)
        return self._translate_client

    def is_bridge_needed(self, language: Language) -> bool:
        """Check if the language requires translation bridging through Hindi."""
        return language.value not in self._native_nova_sonic_languages

    def translate_to_bridge(self, text: str, source_language: Language) -> TranslationResult:
        """Translate from the active language to the bridge language (Hindi)."""
        if not self.is_bridge_needed(source_language):
            return TranslationResult(
                translated_text=text,
                source_language=source_language.value,
                target_language=source_language.value,
                method="bypass",
                latency_ms=0.0,
            )
        return self._dispatch(text, source_language.value, self.bridge_language, source_language)

    def translate_from_bridge(self, text: str, target_language: Language) -> TranslationResult:
        """Translate from the bridge language (Hindi) back to the active language."""
        if not self.is_bridge_needed(target_language):
            return TranslationResult(
                translated_text=text,
                source_language=target_language.value,
                target_language=target_language.value,
                method="bypass",
                latency_ms=0.0,
            )
        return self._dispatch(text, self.bridge_language, target_language.value, target_language)

    def _dispatch(self, text: str, source: str, target: str, language: Language) -> TranslationResult:
        """Route to the appropriate translation backend based on language."""
        if language in AMAZON_TRANSLATE_SUPPORTED:
            try:
                return self._translate_amazon(text, source, target)
            except Exception as e:
                logger.warning("Amazon Translate failed, falling back to mock: %s", e)
                return self._translate_mock(text, source, target)

        if language in INDICTRANS2_REQUIRED:
            try:
                return self._translate_indictrans2(text, source, target)
            except Exception as e:
                logger.warning("IndicTrans2 unavailable, falling back to mock: %s", e)
                return self._translate_mock(text, source, target)

        logger.warning("No translation backend configured for %s, using mock", language)
        return self._translate_mock(text, source, target)

    def _translate_amazon(self, text: str, source: str, target: str) -> TranslationResult:
        """Translate using Amazon Translate service."""
        client = self.translate_client
        if client is None:
            raise RuntimeError("Amazon Translate client not available")

        start = time.monotonic()
        response = client.translate_text(
            Text=text,
            SourceLanguageCode=source,
            TargetLanguageCode=target,
        )
        latency_ms = (time.monotonic() - start) * 1000

        if latency_ms > TRANSLATE_TIMEOUT_SEC * 1000:
            logger.warning("Amazon Translate took %.0fms (limit %dms)", latency_ms, TRANSLATE_TIMEOUT_SEC * 1000)

        return TranslationResult(
            translated_text=response["TranslatedText"],
            source_language=source,
            target_language=target,
            method="amazon_translate",
            latency_ms=latency_ms,
        )

    def _translate_indictrans2(self, text: str, source: str, target: str) -> TranslationResult:
        """Translate using the self-hosted IndicTrans2 sidecar service."""
        start = time.monotonic()
        response = requests.post(
            INDICTRANS2_URL,
            json={"text": text, "src_lang": source, "tgt_lang": target},
            timeout=TRANSLATE_TIMEOUT_SEC,
        )
        response.raise_for_status()
        latency_ms = (time.monotonic() - start) * 1000

        data = response.json()
        translated = data.get("translated_text") or data.get("translation") or data.get("text", text)

        return TranslationResult(
            translated_text=translated,
            source_language=source,
            target_language=target,
            method="indictrans2",
            latency_ms=latency_ms,
        )

    def _translate_mock(self, text: str, source: str, target: str) -> TranslationResult:
        """Mock translator for testing when real services are unavailable."""
        start = time.monotonic()
        mock_text = f"[mock {source}->{target}] {text}"
        latency_ms = (time.monotonic() - start) * 1000

        return TranslationResult(
            translated_text=mock_text,
            source_language=source,
            target_language=target,
            method="mock",
            latency_ms=latency_ms,
        )
