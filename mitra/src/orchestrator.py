"""Central orchestrator for Mitra - coordinates all subsystems."""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, List

import numpy as np

from config import (
    DeploymentMode, Language, Intent,
    LANGUAGE_CONFIDENCE_THRESHOLD, IDLE_TIMEOUT_SEC,
    OBJECT_CONFIDENCE_THRESHOLD, BRIDGE_LANGUAGE,
)
from src.audio_io import AudioIO
from src.language_detector import LanguageDetector, DetectionResult
from src.vision_module import VisionModule, VisionResult
from src.logging_subsystem import (
    InteractionLog, LogSerializer, LogStorage,
    QueryInfo, VisionInfo, ResponseInfo, ConfidenceScores,
)

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    role: str  # "user" or "assistant"
    text: str
    language: str
    timestamp: str = ""


@dataclass
class SessionState:
    active_language: Optional[Language] = None
    conversation_history: List[ConversationTurn] = field(default_factory=list)
    last_vision_result: Optional[VisionResult] = None
    deployment_mode: DeploymentMode = DeploymentMode.CLOUD
    is_active: bool = True


class Orchestrator:
    """Coordinates the flow between all Mitra subsystems.

    Manages the pipeline: Audio -> Language Detection -> Intent Classification ->
    {Conversation | Vision | Navigation} -> Response -> Audio Output.
    """

    def __init__(
        self,
        mode: DeploymentMode = DeploymentMode.CLOUD,
        use_file_io: bool = False,
        input_file=None,
        output_dir=None,
        vision_backend: str = "mock",
    ):
        self.mode = mode
        self.session = SessionState(deployment_mode=mode)

        self.audio = AudioIO(
            use_file_io=use_file_io,
            input_file=input_file,
            output_dir=output_dir,
        )
        self.language_detector = LanguageDetector()
        self.vision = VisionModule(backend=vision_backend)
        self.log_storage = LogStorage()

        self._edge_modules = None
        self._cloud_modules = None

        if mode == DeploymentMode.EDGE:
            self._init_edge()
        else:
            self._init_cloud()

    def _init_edge(self):
        from src.edge.asr_engine import ASREngine
        from src.edge.tts_engine import TTSEngine
        from src.edge.slm import SLM
        from src.edge.vision_vqa import EdgeVQA

        asr = ASREngine()
        tts = TTSEngine()
        slm = SLM()
        vqa = EdgeVQA(slm=slm)

        self._edge_modules = {
            "asr": asr,
            "tts": tts,
            "slm": slm,
            "vqa": vqa,
        }

        logger.info("Loading edge models...")
        start = time.time()
        for name, module in self._edge_modules.items():
            if hasattr(module, "load_model"):
                success = module.load_model()
                logger.info("  %s: %s", name, "loaded" if success else "mock mode")
        elapsed = time.time() - start
        logger.info("Edge models loaded in %.1fs", elapsed)

    def _init_cloud(self):
        from src.cloud.nova_sonic_client import NovaSonicClient
        from src.cloud.nova_vision_client import NovaVisionClient
        from src.cloud.translation_bridge import TranslationBridge

        sonic = NovaSonicClient()
        vision_client = NovaVisionClient()
        bridge = TranslationBridge()

        self._cloud_modules = {
            "sonic": sonic,
            "vision_client": vision_client,
            "bridge": bridge,
        }

        if sonic.check_connectivity():
            logger.info("Bedrock API connected")
        else:
            logger.warning("Bedrock API unreachable - cloud features unavailable")

    def run(self):
        """Main loop: listen -> detect language -> process -> respond."""
        logger.info("Mitra started in %s mode", self.mode.value)

        if not self.audio.is_available:
            logger.error("Audio hardware unavailable")
            return

        self.audio.start_listening()

        try:
            while self.session.is_active:
                utterance = self.audio.get_utterance()
                if utterance is None:
                    if self.audio.is_idle:
                        logger.debug("Idle - waiting for speech")
                    continue

                self._process_utterance(utterance)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.shutdown()

    def process_single(self, audio: np.ndarray) -> Optional[str]:
        """Process a single utterance and return response text. For testing."""
        return self._process_utterance(audio)

    def _process_utterance(self, audio: np.ndarray) -> Optional[str]:
        start_time = time.time()
        latency = {}

        # Step 1: Language detection
        t0 = time.time()
        detection = self.language_detector.detect(audio)
        latency["language_detection"] = int((time.time() - t0) * 1000)

        if detection.confidence < LANGUAGE_CONFIDENCE_THRESHOLD:
            self._prompt_repeat(detection)
            return None

        if self.session.active_language != detection.language:
            self.session.active_language = detection.language
            logger.info("Language switched to %s", detection.language.value)

        # Step 2: Classify intent
        intent = self._classify_intent(audio)

        # Step 3: Route to appropriate pipeline
        if self.mode == DeploymentMode.EDGE:
            response_text, response_audio, latency = self._process_edge(
                audio, intent, latency
            )
        else:
            response_text, response_audio, latency = self._process_cloud(
                audio, intent, latency
            )

        # Step 4: Play response
        if response_audio is not None:
            self.audio.play_audio(response_audio)
        elif response_text:
            logger.info("Response (text only): %s", response_text[:100])

        # Step 5: Update conversation history
        if response_text:
            self.session.conversation_history.append(
                ConversationTurn(role="assistant", text=response_text,
                                language=self.session.active_language.value)
            )

        # Step 6: Log interaction
        latency["total"] = int((time.time() - start_time) * 1000)
        self._log_interaction(
            query_text=response_text or "",
            response_text=response_text or "",
            intent=intent,
            latency=latency,
            detection=detection,
        )

        return response_text

    def _process_edge(self, audio, intent, latency):
        asr = self._edge_modules["asr"]
        tts = self._edge_modules["tts"]
        slm = self._edge_modules["slm"]
        vqa = self._edge_modules["vqa"]
        lang = self.session.active_language.value

        # ASR
        t0 = time.time()
        transcription = asr.transcribe(audio, language=lang)
        latency["asr"] = int((time.time() - t0) * 1000)
        query_text = transcription.text

        self.session.conversation_history.append(
            ConversationTurn(role="user", text=query_text, language=lang)
        )

        # Generate response based on intent
        vision_context = None
        if intent == Intent.VISION:
            vision_result = self.vision.recognize_objects()
            self.session.last_vision_result = vision_result
            labels = [d.label for d in vision_result.detections
                      if d.confidence >= OBJECT_CONFIDENCE_THRESHOLD]
            if labels:
                vision_context = ", ".join(labels)

            t0 = time.time()
            vqa_result = vqa.answer_query(
                question=query_text,
                frame=vision_result.frame,
                object_labels=labels,
                language=lang,
            )
            latency["slm"] = int((time.time() - t0) * 1000)
            response_text = vqa_result.answer
        else:
            history = [
                {"role": t.role, "content": t.text}
                for t in self.session.conversation_history[-10:]
            ]
            t0 = time.time()
            gen_result = slm.generate(
                prompt=query_text,
                language=lang,
                conversation_history=history,
            )
            latency["slm"] = int((time.time() - t0) * 1000)
            response_text = gen_result.text

        # TTS
        t0 = time.time()
        synthesis = tts.synthesize(response_text, language=lang)
        latency["tts"] = int((time.time() - t0) * 1000)

        return response_text, synthesis.audio, latency

    def _process_cloud(self, audio, intent, latency):
        sonic = self._cloud_modules["sonic"]
        vision_client = self._cloud_modules["vision_client"]
        bridge = self._cloud_modules["bridge"]
        lang = self.session.active_language

        if intent == Intent.VISION:
            return self._process_cloud_vision(audio, bridge, vision_client, lang, latency)

        return self._process_cloud_conversation(audio, bridge, sonic, lang, latency)

    def _process_cloud_conversation(self, audio, bridge, sonic, lang, latency):
        system_prompt = self._build_system_prompt(lang)
        history = [
            {"role": t.role, "content": t.text}
            for t in self.session.conversation_history[-10:]
        ]

        t0 = time.time()
        sonic_response = sonic.process_speech(
            audio=audio,
            system_prompt=system_prompt,
            conversation_history=history,
        )
        latency["nova_sonic"] = int((time.time() - t0) * 1000)

        if not sonic_response.success:
            logger.error("Nova Sonic error: %s", sonic_response.error)
            return None, None, latency

        response_text = sonic_response.text or ""

        # Translate back if needed
        response_audio = sonic_response.audio
        if bridge.is_bridge_needed(lang) and response_text:
            t0 = time.time()
            translated = bridge.translate_from_bridge(response_text, lang)
            latency["translation_out"] = int((time.time() - t0) * 1000)
            response_text = translated.translated_text

        self.session.conversation_history.append(
            ConversationTurn(role="user", text="[audio input]", language=lang.value)
        )

        return response_text, response_audio, latency

    def _process_cloud_vision(self, audio, bridge, vision_client, lang, latency):
        vision_result = self.vision.recognize_objects()
        self.session.last_vision_result = vision_result
        frame = vision_result.frame

        # For VQA we need the query as text - use a simple transcription approach
        query_text = "[object query]"

        # Translate query to bridge language if needed
        if bridge.is_bridge_needed(lang):
            t0 = time.time()
            translated_query = bridge.translate_to_bridge(query_text, lang)
            latency["translation_in"] = int((time.time() - t0) * 1000)
            query_for_vision = translated_query.translated_text
        else:
            query_for_vision = query_text

        t0 = time.time()
        vision_response = vision_client.ask_about_image(
            image=frame,
            question=query_for_vision,
        )
        latency["nova_vision"] = int((time.time() - t0) * 1000)

        if not vision_response.success:
            logger.error("Nova Vision error: %s", vision_response.error)
            return None, None, latency

        response_text = vision_response.answer

        # Translate back if needed
        if bridge.is_bridge_needed(lang):
            t0 = time.time()
            translated_response = bridge.translate_from_bridge(response_text, lang)
            latency["translation_out"] = int((time.time() - t0) * 1000)
            response_text = translated_response.translated_text

        return response_text, None, latency

    def _classify_intent(self, audio: np.ndarray) -> Intent:
        """Classify user intent. Currently uses a simple heuristic.

        A full implementation would use the transcribed text + a classifier.
        For now, check if a new frame is available from the vision module.
        """
        if self.vision.is_available:
            frame = self.vision.capture_frame()
            if frame is not None:
                return Intent.VISION
        return Intent.CONVERSATION

    def _build_system_prompt(self, lang: Language) -> str:
        lang_name = "Kannada" if lang == Language.KANNADA else "Sanskrit"
        return (
            f"You are Mitra (मित्र), a friendly multilingual conversational robot. "
            f"Respond in {lang_name}. Be helpful, concise, and conversational. "
            f"If the user asks about an object they are showing, describe what you see."
        )

    def _prompt_repeat(self, detection: DetectionResult):
        logger.info(
            "Low confidence (%.2f) for language detection, prompting repeat",
            detection.confidence,
        )

    def _log_interaction(self, query_text, response_text, intent, latency, detection):
        try:
            vision_info = VisionInfo()
            if self.session.last_vision_result:
                top = self.session.last_vision_result.detections
                if top:
                    vision_info = VisionInfo(
                        object_label=top[0].label,
                        confidence=top[0].confidence,
                    )

            bridge_used = (
                self.mode == DeploymentMode.CLOUD
                and self.session.active_language is not None
                and self._cloud_modules is not None
                and self._cloud_modules["bridge"].is_bridge_needed(
                    self.session.active_language
                )
            )

            log = InteractionLog(
                active_language=self.session.active_language.value if self.session.active_language else "unknown",
                deployment_mode=self.mode.value,
                query=QueryInfo(
                    transcribed_text=query_text,
                    source="asr" if self.mode == DeploymentMode.EDGE else "nova_sonic",
                ),
                vision=vision_info,
                response=ResponseInfo(
                    text=response_text,
                    translation_bridge_used=bridge_used,
                    bridge_language=BRIDGE_LANGUAGE if bridge_used else None,
                ),
                confidence_scores=ConfidenceScores(
                    language_detection=detection.confidence,
                ),
                latency_ms=latency.get("total", 0),
            )
            self.log_storage.save_interaction(log)
        except Exception as e:
            logger.warning("Failed to log interaction: %s", e)

    def shutdown(self):
        logger.info("Shutting down Mitra...")
        self.audio.stop()
        self.vision.stop()

        if self._edge_modules:
            for module in self._edge_modules.values():
                if hasattr(module, "unload_model"):
                    module.unload_model()

        logger.info("Mitra stopped")
