from __future__ import annotations

from importlib import import_module
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


def _load_repository_api() -> tuple[Any, Any, Any, Any, Any]:
    package_root = str(Path(__file__).resolve().parents[1] / "src")
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    reader_module = import_module("opencode_history_grep.reader")
    repository_module = import_module("opencode_history_grep.repository")
    return (
        reader_module.HistoryReader,
        reader_module.open_history_database,
        repository_module.compile_all_sessions,
        repository_module.load_repository_manifest,
        repository_module.select_sessions_for_recompile,
    )


HistoryReader, open_history_database, compile_all_sessions, load_repository_manifest, select_sessions_for_recompile = (
    _load_repository_api()
)


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
                    "session-a",
                    "project-1",
                    None,
                    None,
                    "alpha",
                    "/repo",
                    "Alpha",
                    "0.1.0",
                    None,
                    10,
                    20,
                    None,
                    None,
                ),
                (
                    "session-b",
                    "project-1",
                    None,
                    None,
                    "beta",
                    "/repo",
                    "Beta",
                    "0.1.0",
                    None,
                    30,
                    40,
                    None,
                    None,
                ),
            ],
        )

        connection.executemany(
            "INSERT INTO message (id, session_id, time_created, time_updated, data) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    "message-a1",
                    "session-a",
                    100,
                    101,
                    json.dumps(
                        {
                            "role": "user",
                            "time": {"created": 100},
                            "agent": "atlas",
                            "model": {"providerID": "openai", "modelID": "gpt-5"},
                        }
                    ),
                ),
                (
                    "message-b1",
                    "session-b",
                    200,
                    201,
                    json.dumps(
                        {
                            "role": "assistant",
                            "time": {"created": 200, "completed": 202},
                            "parentID": "message-a1",
                            "modelID": "gpt-5",
                            "providerID": "openai",
                            "mode": "chat",
                            "agent": "atlas",
                            "path": {"cwd": "/repo", "root": "/repo"},
                            "cost": 0.5,
                            "tokens": {
                                "input": 3,
                                "output": 4,
                                "reasoning": 0,
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
                    "part-a1",
                    "message-a1",
                    "session-a",
                    100,
                    100,
                    json.dumps({"type": "text", "text": "hello alpha", "synthetic": False}),
                ),
                (
                    "part-b1",
                    "message-b1",
                    "session-b",
                    200,
                    200,
                    json.dumps({"type": "text", "text": "hello beta", "synthetic": False}),
                ),
                (
                    "part-b2",
                    "message-b1",
                    "session-b",
                    201,
                    201,
                    json.dumps({"type": "compaction", "auto": True, "overflow": False}),
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def test_compile_all_sessions_writes_repository_layout_and_manifest(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    reader = HistoryReader(open_history_database(database_path))

    result = compile_all_sessions(reader, repository_path)

    assert result.repository_path == repository_path.resolve()
    assert result.compiled_session_ids == ("session-b", "session-a")
    assert (repository_path / "manifest.json").exists()
    assert (repository_path / "sessions" / "session-a" / "full_view.json").exists()
    assert (repository_path / "sessions" / "session-b" / "full_view.json").exists()

    session_a_artifact = json.loads((repository_path / "sessions" / "session-a" / "full_view.json").read_text())
    assert session_a_artifact["session_id"] == "session-a"
    assert [block["block_type"] for block in session_a_artifact["blocks"]] == ["user_text"]

    manifest = load_repository_manifest(repository_path)
    assert manifest.version == 1
    assert sorted(manifest.sessions) == ["session-a", "session-b"]
    assert manifest.sessions["session-b"].artifact_relpath == "sessions/session-b/full_view.json"


def test_select_sessions_for_recompile_returns_all_before_first_compile(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    reader = HistoryReader(database_path)

    pending = select_sessions_for_recompile(reader, repository_path)

    assert [fingerprint.session_id for fingerprint in pending] == ["session-b", "session-a"]


def test_select_sessions_for_recompile_identifies_only_changed_sessions(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    reader = HistoryReader(database_path)
    compile_all_sessions(reader, repository_path)

    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "UPDATE session SET time_updated = ? WHERE id = ?",
            (99, "session-a"),
        )
        connection.commit()
    finally:
        connection.close()

    refreshed_reader = HistoryReader(database_path)
    pending = select_sessions_for_recompile(refreshed_reader, repository_path)

    assert [fingerprint.session_id for fingerprint in pending] == ["session-a"]
    assert pending[0].session_time_updated == 99


def test_compile_all_sessions_skips_unchanged_sessions(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    reader = HistoryReader(database_path)
    first = compile_all_sessions(reader, repository_path)
    second = compile_all_sessions(reader, repository_path)

    assert first.compiled_session_ids == ("session-b", "session-a")
    assert second.compiled_session_ids == ()
