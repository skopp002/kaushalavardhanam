"""Tests for LogSerializer and LogStorage."""

import json
import sqlite3
from pathlib import Path

import pytest

from src.logging_subsystem import (
    InteractionLog,
    QueryInfo,
    VisionInfo,
    ResponseInfo,
    ConfidenceScores,
    LogSerializer,
    LogStorage,
)


@pytest.fixture
def sample_log():
    """A fully populated InteractionLog for testing."""
    return InteractionLog(
        timestamp="2025-01-01T00:00:00+00:00",
        active_language="kn",
        deployment_mode="cloud",
        query=QueryInfo(transcribed_text="namaskara", source="microphone"),
        vision=VisionInfo(object_label="person", confidence=0.92, image_path="/tmp/f.png"),
        response=ResponseInfo(
            text="hello response",
            translation_bridge_used=True,
            bridge_language="hi",
        ),
        confidence_scores=ConfidenceScores(asr=0.9, language_detection=0.85, overall=0.87),
        latency_ms=123.4,
    )


@pytest.fixture
def temp_storage(tmp_path):
    """LogStorage backed by a temporary SQLite database."""
    db_path = tmp_path / "test_mitra.db"
    storage = LogStorage(db_path=db_path)
    yield storage
    # Cleanup is automatic since tmp_path is removed by pytest.


class TestInteractionLog:

    def test_creation_with_all_fields(self, sample_log):
        assert sample_log.active_language == "kn"
        assert sample_log.deployment_mode == "cloud"
        assert sample_log.query.transcribed_text == "namaskara"
        assert sample_log.vision.object_label == "person"
        assert sample_log.response.translation_bridge_used is True
        assert sample_log.confidence_scores.asr == 0.9
        assert sample_log.latency_ms == 123.4

    def test_default_timestamp_populated(self):
        log = InteractionLog()
        assert log.timestamp  # non-empty ISO string


class TestLogSerializer:

    def test_round_trip_json(self, sample_log):
        json_str = LogSerializer.to_json(sample_log)
        restored = LogSerializer.from_json(json_str)

        assert restored.active_language == sample_log.active_language
        assert restored.query.transcribed_text == sample_log.query.transcribed_text
        assert restored.vision.object_label == sample_log.vision.object_label
        assert restored.response.text == sample_log.response.text
        assert restored.confidence_scores.asr == sample_log.confidence_scores.asr
        assert restored.latency_ms == sample_log.latency_ms

    def test_to_dict_returns_dict(self, sample_log):
        d = LogSerializer.to_dict(sample_log)
        assert isinstance(d, dict)
        assert d["active_language"] == "kn"

    def test_from_dict_round_trip(self, sample_log):
        d = LogSerializer.to_dict(sample_log)
        restored = LogSerializer.from_dict(d)
        assert restored.active_language == sample_log.active_language


class TestLogStorage:

    def test_save_and_retrieve(self, temp_storage, sample_log):
        row_id = temp_storage.save_interaction(sample_log)
        assert isinstance(row_id, int)
        assert row_id > 0

        logs = temp_storage.get_interactions(limit=10)
        assert len(logs) >= 1
        assert logs[0].active_language == "kn"

    def test_count_interactions(self, temp_storage, sample_log):
        initial = temp_storage.count_interactions()
        temp_storage.save_interaction(sample_log)
        assert temp_storage.count_interactions() == initial + 1

    def test_storage_uses_sqlite(self, tmp_path):
        db_path = tmp_path / "verify_sqlite.db"
        storage = LogStorage(db_path=db_path)
        assert db_path.exists()

        # Verify it is a valid SQLite database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='interactions'"
        )
        tables = cursor.fetchall()
        conn.close()
        assert len(tables) == 1
