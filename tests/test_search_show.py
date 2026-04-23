from __future__ import annotations

from importlib import import_module
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


def _load_search_api() -> tuple[Any, Any, Any, Any, Any, Any, Any, Any]:
    package_root = str(Path(__file__).resolve().parents[1] / "src")
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    reader_module = import_module("opencode_history_grep.reader")
    repository_module = import_module("opencode_history_grep.repository")
    search_module = import_module("opencode_history_grep.search_show")
    return (
        reader_module.HistoryReader,
        repository_module.compile_all_sessions,
        search_module.normalize_block_type_filters,
        search_module.paginate_search_results,
        search_module.SearchAnchor,
        search_module.search_compiled_repository,
        search_module.show_session_compiled_view,
        search_module.show_compiled_context,
    )


(
    HistoryReader,
    compile_all_sessions,
    normalize_block_type_filters,
    paginate_search_results,
    SearchAnchor,
    search_compiled_repository,
    show_session_compiled_view,
    show_compiled_context,
) = _load_search_api()


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
                    json.dumps({"type": "text", "text": "alpha needle and another needle", "synthetic": False}),
                ),
                (
                    "part-b1",
                    "message-b1",
                    "session-b",
                    200,
                    200,
                    json.dumps({"type": "text", "text": "beta assistant response", "synthetic": False}),
                ),
                (
                    "part-b2",
                    "message-b1",
                    "session-b",
                    201,
                    201,
                    json.dumps(
                        {
                            "type": "tool",
                            "callID": "tool-1",
                            "tool": "grep",
                            "state": {
                                "status": "completed",
                                "input": {"pattern": "needle", "path": "src/app.py"},
                                "output": "header\nline before\nneedle match line\nline after\nfooter",
                                "title": "grep",
                                "metadata": {},
                                "time": {"start": 201, "end": 202},
                            },
                        }
                    ),
                ),
                (
                    "part-b3",
                    "message-b1",
                    "session-b",
                    202,
                    202,
                    json.dumps({"type": "system", "text": "system noise"}),
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def test_search_compiled_repository_returns_block_results_across_sessions(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    reader = HistoryReader(database_path)
    compile_all_sessions(reader, repository_path)

    results = search_compiled_repository(repository_path, ("needle",))

    assert len(results) == 2
    assert {(result.session_id, result.block_type) for result in results} == {
        ("session-a", "user_text"),
        ("session-b", "tool_result"),
    }
    assert all(result.anchor.block_id == result.block_id for result in results)
    assert results[0].score >= results[1].score


def test_search_compiled_repository_de_noises_same_block_hits_and_windows_tool_results(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    reader = HistoryReader(database_path)
    compile_all_sessions(reader, repository_path)

    results = search_compiled_repository(repository_path, ("needle",))

    user_result = next(result for result in results if result.block_type == "user_text")
    tool_result = next(result for result in results if result.block_type == "tool_result")

    assert user_result.match_text == "alpha needle and another needle"
    assert "needle match line" in tool_result.match_text
    assert "header" in tool_result.match_text
    assert "system noise" not in tool_result.match_text


def test_show_compiled_context_resolves_anchor_from_search_result(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    reader = HistoryReader(database_path)
    compile_all_sessions(reader, repository_path)
    results = search_compiled_repository(repository_path, ("needle",))
    tool_result = next(result for result in results if result.block_type == "tool_result")

    shown = show_compiled_context(repository_path, SearchAnchor(tool_result.session_id, tool_result.block_id))

    assert shown.focus_block_id == tool_result.block_id
    assert any(block.block_id == tool_result.block_id for block in shown.blocks)
    assert all(block.block_type != "system" for block in shown.blocks)
    assert any("needle match line" in block.display_text for block in shown.blocks)


def test_search_compiled_repository_supports_regex_and_cross_line_matches(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    reader = HistoryReader(database_path)
    compile_all_sessions(reader, repository_path)

    results = search_compiled_repository(repository_path, (r"line before\nneedle match",), use_regex=True)

    assert len(results) == 1
    assert results[0].block_type == "tool_result"
    assert "needle match line" in results[0].match_text


def test_search_compiled_repository_supports_block_type_filters(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    reader = HistoryReader(database_path)
    compile_all_sessions(reader, repository_path)

    results = search_compiled_repository(
        repository_path,
        ("needle",),
        block_types=normalize_block_type_filters(["user", "tool"]),
    )

    assert {(result.session_id, result.block_type) for result in results} == {
        ("session-a", "user_text"),
        ("session-b", "tool_result"),
    }


def test_normalize_block_type_filters_supports_message_and_tool_aliases() -> None:
    assert normalize_block_type_filters(["message"]) == {"user_text", "assistant_text"}
    assert normalize_block_type_filters(["tool"]) == {"tool_call", "tool_result"}


def test_paginate_search_results_defaults_to_ten_per_page(tmp_path: Path) -> None:
    results = [
        type("R", (), {"session_id": "s", "block_id": str(i), "block_type": "user_text", "match_text": str(i), "anchor": None})()
        for i in range(23)
    ]

    page = paginate_search_results(results, page=2)

    assert page.page == 2
    assert page.total_pages == 3
    assert page.total_results == 23
    assert len(page.results) == 10


def test_show_session_compiled_view_can_return_full_session(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    reader = HistoryReader(database_path)
    compile_all_sessions(reader, repository_path)

    shown = show_session_compiled_view(repository_path, "session-b")

    assert len(shown.blocks) >= 2
    assert shown.anchor.session_id == "session-b"
