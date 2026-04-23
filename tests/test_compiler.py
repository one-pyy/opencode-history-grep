from __future__ import annotations

from importlib import import_module
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


def _load_history_api() -> tuple[Any, Any, Any]:
    package_root = str(Path(__file__).resolve().parents[1] / "src")
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    reader_module = import_module("opencode_history_grep.reader")
    compiler_module = import_module("opencode_history_grep.compiler")
    return reader_module.HistoryReader, reader_module.open_history_database, compiler_module.compile_session_full_view


HistoryReader, open_history_database, compile_session_full_view = _load_history_api()


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

        connection.execute(
            """
            INSERT INTO session (
                id, project_id, workspace_id, parent_id, slug, directory, title, version,
                share_url, time_created, time_updated, time_archived, time_compacting
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "session-compiler",
                "project-1",
                None,
                None,
                "compiler-session",
                "/repo",
                "Compiler Session",
                "0.1.0",
                None,
                10,
                20,
                None,
                None,
            ),
        )

        connection.executemany(
            "INSERT INTO message (id, session_id, time_created, time_updated, data) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    "message-user",
                    "session-compiler",
                    100,
                    101,
                    json.dumps(
                        {
                            "role": "user",
                            "time": {"created": 100},
                            "agent": "atlas",
                            "model": {"providerID": "openai", "modelID": "gpt-5"},
                            "system": "hidden system prompt",
                        }
                    ),
                ),
                (
                    "message-assistant",
                    "session-compiler",
                    110,
                    111,
                    json.dumps(
                        {
                            "role": "assistant",
                            "time": {"created": 110, "completed": 120},
                            "parentID": "message-user",
                            "modelID": "gpt-5",
                            "providerID": "openai",
                            "mode": "chat",
                            "agent": "atlas",
                            "path": {"cwd": "/repo", "root": "/repo"},
                            "cost": 1.25,
                            "tokens": {
                                "input": 10,
                                "output": 12,
                                "reasoning": 4,
                                "cache": {"read": 0, "write": 0},
                            },
                        }
                    ),
                ),
            ],
        )

        connection.executemany(
            "INSERT INTO part (id, message_id, session_id, time_created, time_updated, data) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    "part-user-text",
                    "message-user",
                    "session-compiler",
                    100,
                    100,
                    json.dumps({"type": "text", "text": "hello from user", "synthetic": False}),
                ),
                (
                    "part-user-system",
                    "message-user",
                    "session-compiler",
                    101,
                    101,
                    json.dumps({"type": "system", "text": "do not compile this"}),
                ),
                (
                    "part-assistant-reasoning",
                    "message-assistant",
                    "session-compiler",
                    110,
                    110,
                    json.dumps({"type": "reasoning", "text": "private reasoning", "time": {"start": 110}}),
                ),
                (
                    "part-assistant-text",
                    "message-assistant",
                    "session-compiler",
                    111,
                    111,
                    json.dumps({"type": "text", "text": "assistant reply", "synthetic": False}),
                ),
                (
                    "part-tool-running",
                    "message-assistant",
                    "session-compiler",
                    112,
                    112,
                    json.dumps(
                        {
                            "type": "tool",
                            "callID": "tool-1",
                            "tool": "grep",
                            "state": {
                                "status": "running",
                                "input": {"pattern": "needle", "path": "src/app.py"},
                                "metadata": {},
                                "time": {"start": 112},
                            },
                        }
                    ),
                ),
                (
                    "part-tool-completed",
                    "message-assistant",
                    "session-compiler",
                    113,
                    113,
                    json.dumps(
                        {
                            "type": "tool",
                            "callID": "tool-1",
                            "tool": "grep",
                            "state": {
                                "status": "completed",
                                "input": {"pattern": "needle", "path": "src/app.py"},
                                "output": "match line 1\nmatch line 2\nmatch line 3",
                                "title": "grep",
                                "metadata": {},
                                "time": {"start": 112, "end": 114},
                            },
                        }
                    ),
                ),
                (
                    "part-subtask",
                    "message-assistant",
                    "session-compiler",
                    114,
                    114,
                    json.dumps(
                        {
                            "type": "subtask",
                            "agent": "explore",
                            "description": "Inspect compiler behavior",
                            "prompt": "Search for tool handling",
                        }
                    ),
                ),
                (
                    "part-compaction",
                    "message-assistant",
                    "session-compiler",
                    115,
                    115,
                    json.dumps({"type": "compaction", "auto": False, "overflow": True}),
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def test_compile_session_full_view_creates_deterministic_block_sequence(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    _create_history_db(database_path)

    reader = HistoryReader(open_history_database(database_path))
    session = reader.load_session("session-compiler")

    view = compile_session_full_view(session)

    assert [block.block_type for block in view.blocks] == [
        "user_text",
        "assistant_text",
        "tool_call",
        "tool_result",
        "subtask",
        "compaction",
    ]
    assert [block.block_id for block in view.blocks] == [
        "message-user:0000",
        "message-assistant:0001",
        "message-assistant:0002",
        "message-assistant:0003",
        "message-assistant:0004",
        "message-assistant:0005",
    ]


def test_compile_session_excludes_system_and_reasoning_content(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    _create_history_db(database_path)

    reader = HistoryReader(database_path)
    session = reader.load_session("session-compiler")

    view = compile_session_full_view(session)
    combined_display = "\n".join(block.display_text for block in view.blocks)
    combined_search = "\n".join(block.search_text for block in view.blocks)

    assert "hidden system prompt" not in combined_display
    assert "do not compile this" not in combined_display
    assert "private reasoning" not in combined_display
    assert all(block.block_type != "reasoning" for block in view.blocks)
    assert "hidden system prompt" not in combined_search


def test_compile_session_keeps_tool_call_parameters_and_summarizes_tool_result(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    _create_history_db(database_path)

    reader = HistoryReader(database_path)
    session = reader.load_session("session-compiler")

    view = compile_session_full_view(session)
    tool_call = next(block for block in view.blocks if block.block_type == "tool_call")
    tool_result = next(block for block in view.blocks if block.block_type == "tool_result")

    assert tool_call.role == "tool"
    assert "pattern: needle" in tool_call.display_text
    assert "path: src/app.py" in tool_call.search_text
    assert tool_call.metadata["tool_status"] == "running"

    assert tool_result.role == "tool"
    assert "status: completed" in tool_result.display_text
    assert "match line 1" in tool_result.display_text
    assert tool_result.metadata["tool_name"] == "grep"
    assert tool_result.summary == "match line 1"
