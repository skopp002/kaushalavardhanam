"""Structured JSON logging and SQLite persistence for Mitra interactions.

Provides:
- ``InteractionLog`` -- pydantic model describing a single interaction.
- ``LogSerializer`` -- round-trip JSON serialisation for ``InteractionLog``.
- ``LogStorage`` -- SQLite-backed persistent storage with automatic size cleanup.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config import LOG_DB_PATH, LOG_MAX_SIZE_MB

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class QueryInfo(BaseModel):
    """Transcribed user query and its source."""

    transcribed_text: str = ""
    source: str = ""  # e.g. "microphone", "text_input"


class VisionInfo(BaseModel):
    """Vision-related metadata attached to an interaction."""

    object_label: Optional[str] = None
    confidence: Optional[float] = None
    image_path: Optional[str] = None


class ResponseInfo(BaseModel):
    """Generated response metadata."""

    text: str = ""
    translation_bridge_used: bool = False
    bridge_language: Optional[str] = None


class ConfidenceScores(BaseModel):
    """Per-stage confidence scores for an interaction."""

    asr: Optional[float] = None
    language_detection: Optional[float] = None
    vision: Optional[float] = None
    overall: Optional[float] = None


class InteractionLog(BaseModel):
    """Complete record of a single user interaction.

    This schema follows the Mitra requirements specification.
    """

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    active_language: str = ""
    deployment_mode: str = ""
    query: QueryInfo = Field(default_factory=QueryInfo)
    vision: VisionInfo = Field(default_factory=VisionInfo)
    response: ResponseInfo = Field(default_factory=ResponseInfo)
    confidence_scores: ConfidenceScores = Field(default_factory=ConfidenceScores)
    latency_ms: Optional[float] = None


# ---------------------------------------------------------------------------
# Serialiser
# ---------------------------------------------------------------------------

class LogSerializer:
    """Round-trip JSON serialisation for ``InteractionLog``."""

    @staticmethod
    def to_json(log: InteractionLog) -> str:
        """Serialise an ``InteractionLog`` to a JSON string.

        Parameters
        ----------
        log : InteractionLog
            The interaction to serialise.

        Returns
        -------
        str
            JSON representation.
        """
        return log.model_dump_json(indent=2)

    @staticmethod
    def to_dict(log: InteractionLog) -> Dict[str, Any]:
        """Convert an ``InteractionLog`` to a plain dict.

        Parameters
        ----------
        log : InteractionLog

        Returns
        -------
        dict
        """
        return log.model_dump()

    @staticmethod
    def from_json(data: str) -> InteractionLog:
        """Deserialise a JSON string to an ``InteractionLog``.

        Parameters
        ----------
        data : str
            JSON string produced by :meth:`to_json`.

        Returns
        -------
        InteractionLog
        """
        return InteractionLog.model_validate_json(data)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> InteractionLog:
        """Create an ``InteractionLog`` from a plain dict.

        Parameters
        ----------
        data : dict

        Returns
        -------
        InteractionLog
        """
        return InteractionLog.model_validate(data)


# ---------------------------------------------------------------------------
# SQLite storage
# ---------------------------------------------------------------------------

class LogStorage:
    """SQLite-backed storage for ``InteractionLog`` records.

    Parameters
    ----------
    db_path : Path or None
        Database file location.  Defaults to ``LOG_DB_PATH`` from config.
    max_size_mb : float
        Maximum on-disk database size in megabytes before auto-cleanup
        discards the oldest entries.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        max_size_mb: float = LOG_MAX_SIZE_MB,
    ) -> None:
        self._db_path = Path(db_path) if db_path is not None else LOG_DB_PATH
        self._max_size_bytes = int(max_size_mb * 1024 * 1024)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        """Create and return a new database connection."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def init_database(self) -> None:
        """Create the ``interactions`` table if it does not exist."""
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp       TEXT    NOT NULL,
                    active_language TEXT    NOT NULL DEFAULT '',
                    deployment_mode TEXT    NOT NULL DEFAULT '',
                    query_json      TEXT    NOT NULL DEFAULT '{}',
                    vision_json     TEXT    NOT NULL DEFAULT '{}',
                    response_json   TEXT    NOT NULL DEFAULT '{}',
                    confidence_json TEXT    NOT NULL DEFAULT '{}',
                    latency_ms      REAL,
                    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_interactions_timestamp
                ON interactions (timestamp)
            """)
            conn.commit()
            logger.info("Interactions table ready at %s", self._db_path)
        except sqlite3.Error:
            logger.exception("Failed to initialise database at %s", self._db_path)
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save_interaction(self, log: InteractionLog) -> int:
        """Persist an interaction log to the database.

        After writing, the storage size is checked and the oldest entries
        are pruned if the database exceeds ``max_size_mb``.

        Parameters
        ----------
        log : InteractionLog
            The interaction record to save.

        Returns
        -------
        int
            Row ID of the inserted record.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO interactions
                    (timestamp, active_language, deployment_mode,
                     query_json, vision_json, response_json,
                     confidence_json, latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log.timestamp,
                    log.active_language,
                    log.deployment_mode,
                    log.query.model_dump_json(),
                    log.vision.model_dump_json(),
                    log.response.model_dump_json(),
                    log.confidence_scores.model_dump_json(),
                    log.latency_ms,
                ),
            )
            row_id = cursor.lastrowid
            conn.commit()
            logger.debug("Saved interaction id=%d", row_id)
        except sqlite3.Error:
            logger.exception("Failed to save interaction")
            raise
        finally:
            conn.close()

        self._enforce_size_limit()
        return row_id  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_interactions(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[InteractionLog]:
        """Retrieve interaction logs ordered by timestamp descending.

        Parameters
        ----------
        limit : int
            Maximum number of records to return.
        offset : int
            Number of records to skip (for pagination).

        Returns
        -------
        list[InteractionLog]
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM interactions
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()
        except sqlite3.Error:
            logger.exception("Failed to retrieve interactions")
            raise
        finally:
            conn.close()

        logs: List[InteractionLog] = []
        for row in rows:
            try:
                log = InteractionLog(
                    timestamp=row["timestamp"],
                    active_language=row["active_language"],
                    deployment_mode=row["deployment_mode"],
                    query=QueryInfo.model_validate_json(row["query_json"]),
                    vision=VisionInfo.model_validate_json(row["vision_json"]),
                    response=ResponseInfo.model_validate_json(row["response_json"]),
                    confidence_scores=ConfidenceScores.model_validate_json(
                        row["confidence_json"]
                    ),
                    latency_ms=row["latency_ms"],
                )
                logs.append(log)
            except Exception:
                logger.exception("Failed to parse interaction row id=%s", row["id"])
        return logs

    def count_interactions(self) -> int:
        """Return the total number of stored interactions."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM interactions")
            return cursor.fetchone()[0]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Size management
    # ------------------------------------------------------------------

    def _get_db_size_bytes(self) -> int:
        """Return the current database file size in bytes."""
        try:
            return os.path.getsize(self._db_path)
        except OSError:
            return 0

    def _enforce_size_limit(self) -> None:
        """Delete the oldest interactions if the DB exceeds the size limit."""
        current_size = self._get_db_size_bytes()
        if current_size <= self._max_size_bytes:
            return

        logger.warning(
            "Database size %.2f MB exceeds limit %.2f MB -- pruning oldest entries.",
            current_size / (1024 * 1024),
            self._max_size_bytes / (1024 * 1024),
        )

        conn = self._get_connection()
        try:
            # Delete the oldest 10% of rows in each pass.
            total = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
            delete_count = max(1, total // 10)

            conn.execute(
                """
                DELETE FROM interactions
                WHERE id IN (
                    SELECT id FROM interactions
                    ORDER BY timestamp ASC
                    LIMIT ?
                )
                """,
                (delete_count,),
            )
            conn.commit()

            # Reclaim disk space.
            conn.execute("VACUUM")
            logger.info(
                "Pruned %d oldest interactions. New size: %.2f MB.",
                delete_count,
                self._get_db_size_bytes() / (1024 * 1024),
            )
        except sqlite3.Error:
            logger.exception("Failed during size-limit enforcement")
        finally:
            conn.close()
