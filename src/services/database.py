"""
Database Service - SQLite storage for practice transcripts and coaching results.

Provides async database operations for storing and retrieving
practice session data.
"""

import os
import json
import logging
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("starcoach.database")

DEFAULT_DB_PATH = "data/starcoach.db"


class Database:
    """Async SQLite database service for STARCoach."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Initialize database and create tables if needed."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS interviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    applicant_id INTEGER NOT NULL,
                    applicant_name TEXT NOT NULL,
                    guild_id INTEGER NOT NULL,
                    channel_name TEXT,
                    transcript TEXT,
                    started_at TIMESTAMP,
                    ended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id INTEGER NOT NULL,
                    fit_score INTEGER,
                    recommended BOOLEAN,
                    scores JSON,
                    strengths JSON,
                    concerns JSON,
                    red_flags JSON,
                    evidence_quotes JSON,
                    summary TEXT,
                    raw_response JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (interview_id) REFERENCES interviews(id)
                );

                CREATE INDEX IF NOT EXISTS idx_interviews_guild 
                    ON interviews(guild_id);
                CREATE INDEX IF NOT EXISTS idx_interviews_applicant 
                    ON interviews(applicant_id);
                CREATE INDEX IF NOT EXISTS idx_analysis_interview 
                    ON analysis_results(interview_id);
            """)
            await db.commit()
            logger.info(f"Database initialized at {self.db_path}")

    async def save_transcript(
        self,
        applicant_id: int,
        applicant_name: str,
        guild_id: int,
        channel_name: str,
        transcript: str,
        started_at: datetime,
    ) -> int:
        """Save a practice session transcript."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO interviews 
                (applicant_id, applicant_name, guild_id, channel_name, transcript, started_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    applicant_id,
                    applicant_name,
                    guild_id,
                    channel_name,
                    transcript,
                    started_at.isoformat(),
                ),
            )
            await db.commit()
            
            interview_id = cursor.lastrowid
            logger.info(f"Saved transcript for session #{interview_id}")
            return interview_id

    async def create_interview(
        self,
        applicant_id: int,
        applicant_name: str,
        guild_id: int,
        channel_name: str,
        started_at: datetime,
    ) -> int:
        """Create a placeholder interview row and return its ID.
        
        Called at session start so the interview_id is available
        for display in text-channel embeds throughout the session.
        The transcript is filled in later via update_interview_transcript().
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO interviews 
                (applicant_id, applicant_name, guild_id, channel_name, transcript, started_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    applicant_id,
                    applicant_name,
                    guild_id,
                    channel_name,
                    "",  # placeholder — filled later
                    started_at.isoformat(),
                ),
            )
            await db.commit()
            interview_id = cursor.lastrowid
            logger.info(f"Created placeholder session #{interview_id}")
            return interview_id

    async def update_interview_transcript(
        self,
        interview_id: int,
        transcript: str,
    ) -> None:
        """Update the transcript and ended_at timestamp for an existing interview."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE interviews 
                SET transcript = ?, ended_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (transcript, interview_id),
            )
            await db.commit()
            logger.info(f"Updated transcript for session #{interview_id}")

    async def save_analysis(self, interview_id: int, analysis: dict) -> int:
        """Save coaching analysis results for a practice session."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO analysis_results
                (interview_id, fit_score, recommended, scores, strengths, 
                 concerns, red_flags, evidence_quotes, summary, raw_response)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    interview_id,
                    analysis.get("fit_score", analysis.get("readiness_score")),
                    analysis.get("recommended", False),
                    json.dumps(analysis.get("scores", {})),
                    json.dumps(analysis.get("strengths", [])),
                    json.dumps(analysis.get("concerns", analysis.get("improvement_areas", []))),
                    json.dumps(analysis.get("red_flags", [])),
                    json.dumps(analysis.get("evidence_quotes", {})),
                    analysis.get("summary", analysis.get("overall_feedback")),
                    json.dumps(analysis),
                ),
            )
            await db.commit()
            
            analysis_id = cursor.lastrowid
            logger.info(f"Saved analysis #{analysis_id} for session #{interview_id}")
            return analysis_id

    async def get_interview(self, interview_id: int) -> Optional[dict]:
        """Get practice session details with coaching analysis."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute(
                "SELECT * FROM interviews WHERE id = ?",
                (interview_id,),
            )
            row = await cursor.fetchone()
            
            if not row:
                return None

            interview = dict(row)
            
            cursor = await db.execute(
                "SELECT * FROM analysis_results WHERE interview_id = ?",
                (interview_id,),
            )
            analysis_row = await cursor.fetchone()
            
            if analysis_row:
                analysis = dict(analysis_row)
                for field in ["scores", "strengths", "concerns", "red_flags", "evidence_quotes"]:
                    if analysis.get(field):
                        try:
                            analysis[field] = json.loads(analysis[field])
                        except json.JSONDecodeError:
                            pass
                interview["analysis"] = analysis
                interview["fit_score"] = analysis.get("fit_score")
                interview["recommended"] = analysis.get("recommended")

            return interview

    async def get_recent_interviews(
        self,
        guild_id: int,
        limit: int = 10,
    ) -> list[dict]:
        """Get recent practice sessions for a guild."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute(
                """
                SELECT i.*, ar.fit_score, ar.recommended
                FROM interviews i
                LEFT JOIN analysis_results ar ON i.id = ar.interview_id
                WHERE i.guild_id = ?
                ORDER BY i.created_at DESC
                LIMIT ?
                """,
                (guild_id, limit),
            )
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_interviews_by_applicant(
        self,
        applicant_id: int,
        guild_id: Optional[int] = None,
    ) -> list[dict]:
        """Get all practice sessions for a specific user."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if guild_id:
                cursor = await db.execute(
                    """
                    SELECT i.*, ar.fit_score, ar.recommended
                    FROM interviews i
                    LEFT JOIN analysis_results ar ON i.id = ar.interview_id
                    WHERE i.applicant_id = ? AND i.guild_id = ?
                    ORDER BY i.created_at DESC
                    """,
                    (applicant_id, guild_id),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT i.*, ar.fit_score, ar.recommended
                    FROM interviews i
                    LEFT JOIN analysis_results ar ON i.id = ar.interview_id
                    WHERE i.applicant_id = ?
                    ORDER BY i.created_at DESC
                    """,
                    (applicant_id,),
                )
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_stats(self, guild_id: int) -> dict:
        """Get practice session statistics for a guild."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM interviews WHERE guild_id = ?",
                (guild_id,),
            )
            total = (await cursor.fetchone())[0]

            cursor = await db.execute(
                """
                SELECT AVG(ar.fit_score)
                FROM interviews i
                JOIN analysis_results ar ON i.id = ar.interview_id
                WHERE i.guild_id = ?
                """,
                (guild_id,),
            )
            avg_score = (await cursor.fetchone())[0] or 0

            cursor = await db.execute(
                """
                SELECT COUNT(*)
                FROM interviews i
                JOIN analysis_results ar ON i.id = ar.interview_id
                WHERE i.guild_id = ? AND ar.recommended = 1
                """,
                (guild_id,),
            )
            ready_count = (await cursor.fetchone())[0]

            return {
                "total_sessions": total,
                "avg_readiness_score": avg_score,
                "interview_ready_count": ready_count,
                "readiness_rate": (ready_count / total * 100) if total > 0 else 0,
            }

    async def delete_interview(self, interview_id: int) -> bool:
        """Delete a practice session and its analysis."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM analysis_results WHERE interview_id = ?",
                (interview_id,),
            )
            
            cursor = await db.execute(
                "DELETE FROM interviews WHERE id = ?",
                (interview_id,),
            )
            await db.commit()
            
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted session #{interview_id}")
            return deleted
