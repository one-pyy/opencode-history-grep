from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import HistoryDatabase, HistoryMessage, HistoryPart, HistorySession, HistorySessionSummary


class SessionNotFoundError(KeyError):
    def __init__(self, session_id: str) -> None:
        super().__init__(session_id)
        self.session_id = session_id


@dataclass(frozen=True, slots=True)
class SessionFilter:
    directory_prefix: Path | None = None
    since: int | None = None
    until: int | None = None

    def matches(self, summary: HistorySessionSummary) -> bool:
        if self.directory_prefix is not None:
            summary_dir = Path(summary.directory).expanduser().resolve()
            try:
                summary_dir.relative_to(self.directory_prefix)
            except ValueError:
                return False
        effective_time = summary.effective_time
        if self.since is not None and effective_time < self.since:
            return False
        if self.until is not None and effective_time > self.until:
            return False
        return True


def open_history_database(path: str | Path) -> HistoryDatabase:
    return HistoryDatabase(path=Path(path).expanduser().resolve())


class HistoryReader:
    def __init__(self, database: HistoryDatabase | str | Path) -> None:
        if isinstance(database, HistoryDatabase):
            self._database = database
        else:
            self._database = open_history_database(database)

    @property
    def database_path(self) -> Path:
        return self._database.path

    def list_sessions(self, session_filter: SessionFilter | None = None) -> list[HistorySessionSummary]:
        query = """
            SELECT
                session.id,
                session.project_id,
                session.workspace_id,
                session.parent_id,
                session.slug,
                session.directory,
                session.title,
                session.version,
                session.share_url,
                session.time_created,
                session.time_updated,
                session.time_archived,
                session.time_compacting,
                COUNT(message.id) AS message_count,
                MAX(message.time_created) AS last_message_created
            FROM session
            LEFT JOIN message ON message.session_id = session.id
            GROUP BY session.id
            ORDER BY COALESCE(MAX(message.time_created), session.time_updated, session.time_created) DESC, session.id DESC
        """
        with self._connect() as connection:
            rows = connection.execute(query).fetchall()
        summaries = [
            HistorySessionSummary(
                id=row["id"],
                project_id=row["project_id"],
                workspace_id=row["workspace_id"],
                parent_id=row["parent_id"],
                slug=row["slug"],
                directory=row["directory"],
                title=row["title"],
                version=row["version"],
                share_url=row["share_url"],
                time_created=row["time_created"],
                time_updated=row["time_updated"],
                time_archived=row["time_archived"],
                time_compacting=row["time_compacting"],
                message_count=int(row["message_count"]),
                last_message_created=row["last_message_created"],
            )
            for row in rows
        ]
        if session_filter is None:
            return summaries
        return [summary for summary in summaries if session_filter.matches(summary)]

    def load_session(self, session_id: str) -> HistorySession:
        with self._connect() as connection:
            session_row = connection.execute(
                """
                SELECT
                    id,
                    project_id,
                    workspace_id,
                    parent_id,
                    slug,
                    directory,
                    title,
                    version,
                    share_url,
                    time_created,
                    time_updated,
                    time_archived,
                    time_compacting
                FROM session
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
            if session_row is None:
                raise SessionNotFoundError(session_id)

            message_rows = connection.execute(
                """
                SELECT id, session_id, time_created, time_updated, data
                FROM message
                WHERE session_id = ?
                ORDER BY time_created ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
            part_rows = connection.execute(
                """
                SELECT id, message_id, session_id, time_created, time_updated, data
                FROM part
                WHERE session_id = ?
                ORDER BY message_id ASC, id ASC
                """,
                (session_id,),
            ).fetchall()

        parts_by_message: dict[str, list[HistoryPart]] = defaultdict(list)
        for row in part_rows:
            data = _decode_json_object(row["data"], kind="part", record_id=row["id"])
            parts_by_message[row["message_id"]].append(
                HistoryPart.from_row_data(
                    part_id=row["id"],
                    session_id=row["session_id"],
                    message_id=row["message_id"],
                    time_created=row["time_created"],
                    time_updated=row["time_updated"],
                    data=data,
                )
            )

        messages = tuple(
            HistoryMessage.from_row_data(
                message_id=row["id"],
                session_id=row["session_id"],
                time_created=row["time_created"],
                time_updated=row["time_updated"],
                data=_decode_json_object(row["data"], kind="message", record_id=row["id"]),
                parts=tuple(parts_by_message.get(row["id"], ())),
            )
            for row in message_rows
        )

        return HistorySession(
            id=session_row["id"],
            project_id=session_row["project_id"],
            workspace_id=session_row["workspace_id"],
            parent_id=session_row["parent_id"],
            slug=session_row["slug"],
            directory=session_row["directory"],
            title=session_row["title"],
            version=session_row["version"],
            share_url=session_row["share_url"],
            time_created=session_row["time_created"],
            time_updated=session_row["time_updated"],
            time_archived=session_row["time_archived"],
            time_compacting=session_row["time_compacting"],
            messages=messages,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


def _decode_json_object(raw_value: str, *, kind: str, record_id: str) -> dict[str, Any]:
    data = json.loads(raw_value)
    if not isinstance(data, dict):
        raise ValueError(f"Expected {kind} {record_id} to contain a JSON object.")
    return data
