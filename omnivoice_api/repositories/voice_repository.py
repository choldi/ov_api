"""Repository for managing cloned voices in SQLite."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import aiosqlite
from loguru import logger

from omnivoice_api.core.exceptions import VoiceNotFoundError
from omnivoice_api.settings import get_settings


class VoiceRepository:
    """Repository for cloned voices using SQLite."""

    def __init__(self, db_path: str | None = None):
        """Initialize the repository with database path."""
        self._settings = get_settings()
        url = db_path or self._settings.DATABASE_URL
        # Strip SQLAlchemy driver prefix to get a plain file path
        for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
            if url.startswith(prefix):
                url = url[len(prefix):]
                break
        self._db_path = url
        # Ensure the directory exists
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get a database connection."""
        conn = await aiosqlite.connect(self._db_path)
        # Enable foreign keys
        await conn.execute("PRAGMA foreign_keys = ON")
        return conn

    async def initialize(self) -> None:
        """Initialize the database schema."""
        # Get connection
        conn = await self._get_connection()
        try:
            await conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cloned_voices (
                    id           TEXT PRIMARY KEY,        -- UUIDv4
                    name         TEXT NOT NULL UNIQUE,
                    language     TEXT NOT NULL,           -- ISO 639-1
                    reference_path TEXT NOT NULL,
                    duration_sec REAL NOT NULL,
                    created_at   TEXT NOT NULL,
                    metadata     TEXT                     -- JSON extendido
                );
                
                CREATE INDEX IF NOT EXISTS idx_cloned_voices_language 
                ON cloned_voices(language);
                
                CREATE INDEX IF NOT EXISTS idx_cloned_voices_created_at 
                ON cloned_voices(created_at);
                """
            )
            await conn.commit()
        finally:
            await conn.close()
        logger.info(f"Voice repository initialized at {self._db_path}")

    async def create(
        self,
        name: str,
        language: str,
        reference_path: str,
        duration_sec: float,
        metadata: dict | None = None,
    ) -> str:
        """Create a new cloned voice record.
        
        Args:
            name: Unique name for the voice
            language: Language code (ISO 639-1)
            reference_path: Path to the reference audio file
            duration_sec: Duration of the reference audio in seconds
            metadata: Optional metadata as dictionary
            
        Returns:
            str: The UUID of the created voice record
            
        Raises:
            ValueError: If a voice with the same name already exists
        """
        voice_id = str(uuid4())
        now = datetime.utcnow().isoformat()
        metadata_json = json.dumps(metadata or {})
        
        # Get connection
        conn = await self._get_connection()
        try:
            await conn.execute(
                """
                INSERT INTO cloned_voices 
                (id, name, language, reference_path, duration_sec, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (voice_id, name, language, reference_path, duration_sec, now, metadata_json),
            )
            await conn.commit()
            logger.info(f"Created cloned voice '{name}' with ID {voice_id}")
            return voice_id
        except aiosqlite.IntegrityError as e:
            if "UNIQUE constraint failed: cloned_voices.name" in str(e):
                raise ValueError(f"Voice with name '{name}' already exists") from e
            raise
        finally:
            await conn.close()

    async def get_by_id(self, voice_id: str) -> dict:
        """Get a voice by its ID.
        
        Args:
            voice_id: The UUID of the voice
            
        Returns:
            dict: Voice data including id, name, language, reference_path, duration_sec, created_at, metadata
            
        Raises:
            VoiceNotFoundError: If no voice is found with the given ID
        """
        # Get connection
        conn = await self._get_connection()
        try:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT id, name, language, reference_path, duration_sec, created_at, metadata
                FROM cloned_voices
                WHERE id = ?
                """,
                (voice_id,),
            )
            row = await cursor.fetchone()
            
            if row is None:
                raise VoiceNotFoundError(voice_id, "cloned")
                
            return {
                "id": row["id"],
                "name": row["name"],
                "language": row["language"],
                "reference_path": row["reference_path"],
                "duration_sec": row["duration_sec"],
                "created_at": row["created_at"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            }
        finally:
            await conn.close()

    async def get_by_name(self, name: str) -> dict:
        """Get a voice by its name.
        
        Args:
            name: The name of the voice
            
        Returns:
            dict: Voice data
            
        Raises:
            VoiceNotFoundError: If no voice is found with the given name
        """
        # Get connection
        conn = await self._get_connection()
        try:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT id, name, language, reference_path, duration_sec, created_at, metadata
                FROM cloned_voices
                WHERE name = ?
                """,
                (name,),
            )
            row = await cursor.fetchone()
            
            if row is None:
                raise VoiceNotFoundError(name, "cloned (by name)")
                
            return {
                "id": row["id"],
                "name": row["name"],
                "language": row["language"],
                "reference_path": row["reference_path"],
                "duration_sec": row["duration_sec"],
                "created_at": row["created_at"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            }
        finally:
            await conn.close()

    async def list(
        self, 
        language: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[dict]:
        """List voices with optional filtering.
        
        Args:
            language: Filter by language (ISO 639-1)
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            list[dict]: List of voice dictionaries
        """
        # Get connection
        conn = await self._get_connection()
        try:
            conn.row_factory = aiosqlite.Row
            
            if language:
                cursor = await conn.execute(
                    """
                    SELECT id, name, language, reference_path, duration_sec, created_at, metadata
                    FROM cloned_voices
                    WHERE language = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (language, limit, offset),
                )
            else:
                cursor = await conn.execute(
                    """
                    SELECT id, name, language, reference_path, duration_sec, created_at, metadata
                    FROM cloned_voices
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )
            
            rows = await cursor.fetchall()
            
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "language": row["language"],
                    "reference_path": row["reference_path"],
                    "duration_sec": row["duration_sec"],
                    "created_at": row["created_at"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                }
                for row in rows
            ]
        finally:
            await conn.close()

    async def update(
        self, 
        voice_id: str, 
        name: str | None = None,
        metadata: dict | None = None
    ) -> bool:
        """Update a voice's metadata.
        
        Args:
            voice_id: The UUID of the voice to update
            name: New name for the voice (optional)
            metadata: New metadata to merge with existing (optional)
            
        Returns:
            bool: True if the voice was updated, False if not found
            
        Raises:
            ValueError: If the new name conflicts with an existing voice
        """
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
            
        if metadata is not None:
            # Get current metadata and merge
            current = await self.get_by_id(voice_id)
            merged_metadata = {**current["metadata"], **metadata}
            updates.append("metadata = ?")
            params.append(json.dumps(merged_metadata))
            
        if not updates:
            return False
            
        updates.append("created_at = ?")  # Update timestamp
        params.append(datetime.utcnow().isoformat())
        params.append(voice_id)  # FOR WHERE clause
        # Get connection
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                f'UPDATE cloned_voices SET {", ".join(updates)} WHERE id = ?',
                params,
            )
            await conn.commit()
            
            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Updated cloned voice {voice_id}")
            return updated
        except aiosqlite.IntegrityError as e:
            if "UNIQUE constraint failed: cloned_voices.name" in str(e):
                raise ValueError(f"Voice with name '{name}' already exists") from e
            raise
        finally:
            await conn.close()

    async def delete(self, voice_id: str) -> bool:
        """Delete a voice by its ID.
        
        Args:
            voice_id: The UUID of the voice to delete
            
        Returns:
            bool: True if the voice was deleted, False if not found
        """
        # Get connection
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "DELETE FROM cloned_voices WHERE id = ?",
                (voice_id,),
            )
            await conn.commit()
            
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted cloned voice {voice_id}")
            return deleted
        finally:
            await conn.close()

    async def voice_exists(self, voice_id: str) -> bool:
        """Check if a voice exists by ID.
        
        Args:
            voice_id: The UUID to check
            
        Returns:
            bool: True if the voice exists
        """
        try:
            await self.get_by_id(voice_id)
            return True
        except VoiceNotFoundError:
            return False
