from __future__ import annotations

from importlib import import_module
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


def _load_reader_api() -> tuple[Any, Any]:
    package_root = str(Path(__file__).resolve().parents[1] / "src")
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    reader_module = import_module("opencode_history_grep.reader")
    return reader_module.HistoryReader, reader_module.open_history_database


HistoryReader, open_history_database = _load_reader_api()


def _create_history_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE session (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                workspace_id TEXT,
                parent_id TEXT,
                slug TEXT NOT NULL,
                directory TEXT NOT NULL,
                title TEXT NOT NULL,
                version TEXT NOT NULL,
                share_url TEXT,
                time_created INTEGER NOT NULL,
                time_updated INTEGER NOT NULL,
                time_archived INTEGER,
                time_compacting INTEGER
            );

            CREATE TABLE message (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                time_created INTEGER NOT NULL,
                time_updated INTEGER NOT NULL,
                data TEXT NOT NULL
            );

            CREATE TABLE part (
                id TEXT PRIMARY KEY,
                message_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                time_created INTEGER NOT NULL,
                time_updated INTEGER NOT NULL,
                data TEXT NOT NULL
            );
            """
        )

        connection.executemany(
            """
            INSERT INTO session (
                id, project_id, workspace_id, parent_id, slug, directory, title, version,
                share_url, time_created, time_updated, time_archived, time_compacting
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "session-1",
                    "project-1",
                    "workspace-1",
                    None,
                    "first-session",
                    "/repo",
                    "First Session",
                    "0.1.0",
                    None,
                    10,
                    20,
                    None,
                    None,
                ),
                (
                    "session-2",
                    "project-1",
                    None,
                    "session-1",
                    "second-session",
                    "/repo",
                    "Second Session",
                    "0.1.0",
                    "https://share.example/session-2",
                    30,
                    40,
                    None,
                    45,
                ),
            ],
        )

        connection.executemany(
            "INSERT INTO message (id, session_id, time_created, time_updated, data) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    "message-1",
                    "session-1",
                    100,
                    101,
                    json.dumps(
                        {
                            "role": "user",
                            "time": {"created": 100},
                            "agent": "atlas",
                            "model": {"providerID": "openai", "modelID": "gpt-5"},
                            "system": "system-prompt",
                        }
                    ),
                ),
                (
                    "message-2",
                    "session-1",
                    110,
                    111,
                    json.dumps(
                        {
                            "role": "assistant",
                            "time": {"created": 110, "completed": 120},
                            "parentID": "message-1",
                            "modelID": "gpt-5",
                            "providerID": "openai",
                            "mode": "chat",
                            "agent": "atlas",
                            "path": {"cwd": "/repo", "root": "/repo"},
                            "cost": 1.25,
                            "tokens": {
                                "input": 10,
                                "output": 12,
                                "reasoning": 0,
                                "cache": {"read": 0, "write": 0},
                            },
                        }
                    ),
                ),
                (
                    "message-3",
                    "session-2",
                    210,
                    211,
                    json.dumps(
                        {
                            "role": "user",
                            "time": {"created": 210},
                            "agent": "atlas",
                            "model": {"providerID": "anthropic", "modelID": "claude-sonnet"},
                        }
                    ),
                ),
            ],
        )

        connection.executemany(
            "INSERT INTO part (id, message_id, session_id, time_created, time_updated, data) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    "part-1",
                    "message-1",
                    "session-1",
                    100,
                    100,
                    json.dumps({"type": "text", "text": "hello", "synthetic": False}),
                ),
                (
                    "part-2",
                    "message-2",
                    "session-1",
                    110,
                    110,
                    json.dumps(
                        {
                            "type": "tool",
                            "callID": "tool-1",
                            "tool": "grep",
                            "state": {
                                "status": "completed",
                                "input": {"pattern": "hello"},
                                "output": "matched",
                                "title": "grep",
                                "metadata": {},
                                "time": {"start": 111, "end": 112},
                            },
                        }
                    ),
                ),
                (
                    "part-3",
                    "message-2",
                    "session-1",
                    113,
                    113,
                    json.dumps({"type": "compaction", "auto": False, "overflow": True}),
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def test_list_sessions_returns_refresh_metadata(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    _create_history_db(database_path)

    reader = HistoryReader(open_history_database(database_path))

    sessions = reader.list_sessions()

    assert [session.id for session in sessions] == ["session-2", "session-1"]
    assert sessions[0].message_count == 1
    assert sessions[0].last_message_created == 210
    assert sessions[0].time_compacting == 45
    assert sessions[1].message_count == 2
    assert sessions[1].last_message_created == 110


def test_load_session_hydrates_ordered_messages_and_parts(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    _create_history_db(database_path)

    reader = HistoryReader(database_path)

    session = reader.load_session("session-1")

    assert session.id == "session-1"
    assert session.message_count == 2
    assert [message.id for message in session.messages] == ["message-1", "message-2"]

    user_message = session.messages[0]
    assert user_message.role == "user"
    assert user_message.data["system"] == "system-prompt"
    assert [part.kind for part in user_message.parts] == ["text"]
    assert user_message.parts[0].data["text"] == "hello"

    assistant_message = session.messages[1]
    assert assistant_message.role == "assistant"
    assert [part.kind for part in assistant_message.parts] == ["tool", "compaction"]
    assert assistant_message.parts[0].data["tool"] == "grep"
    assert assistant_message.parts[1].data["overflow"] is True
