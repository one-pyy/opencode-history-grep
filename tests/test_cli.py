from __future__ import annotations

from importlib import import_module
import io
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


def _load_cli_api() -> Any:
    package_root = str(Path(__file__).resolve().parents[1] / "src")
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    cli_module = import_module("opencode_history_grep.cli")
    return cli_module


cli = _load_cli_api()

LONG_TOOL_OUTPUT = "\n".join(
    [
        "header",
        "line before",
        "needle match line",
        *(f"raw middle line {index}" for index in range(30)),
        "line after",
        "footer",
    ]
)

LONG_QUESTION_ANSWER = "\n".join(
    [
        "custom answer start",
        *(f"custom answer context {index}" for index in range(12)),
        "custom-answer-middle-marker",
        *(f"custom answer detail {index}" for index in range(12)),
        "custom answer end",
    ]
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
                    "session-cli",
                    "project-1",
                    None,
                    None,
                    "cli",
                    "/repo",
                    "CLI Session",
                    "0.1.0",
                    None,
                    10,
                    20,
                    None,
                    None,
                ),
                (
                    "session-other",
                    "project-2",
                    None,
                    None,
                    "other",
                    "/elsewhere",
                    "Other Session",
                    "0.1.0",
                    None,
                    10,
                    200,
                    None,
                    None,
                ),
            ],
        )

        connection.executemany(
            "INSERT INTO message (id, session_id, time_created, time_updated, data) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    "message-user",
                    "session-cli",
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
                    "message-assistant",
                    "session-cli",
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
                (
                    "message-other-user",
                    "session-other",
                    300,
                    301,
                    json.dumps(
                        {
                            "role": "user",
                            "time": {"created": 300},
                            "agent": "atlas",
                            "model": {"providerID": "openai", "modelID": "gpt-5"},
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
                    "session-cli",
                    100,
                    100,
                    json.dumps({"type": "text", "text": "needle in user text", "synthetic": False}),
                ),
                (
                    "part-assistant-text",
                    "message-assistant",
                    "session-cli",
                    110,
                    110,
                    json.dumps({"type": "text", "text": "assistant context", "synthetic": False}),
                ),
                (
                    "part-tool-result",
                    "message-assistant",
                    "session-cli",
                    111,
                    111,
                    json.dumps(
                        {
                                 "type": "tool",
                                 "callID": "tool-1",
                                 "tool": "grep",
                                 "state": {
                                     "status": "completed",
                                     "input": {"pattern": "needle", "path": "src/app.py"},
                                     "output": LONG_TOOL_OUTPUT,
                                     "title": "grep",
                                     "metadata": {},
                                     "time": {"start": 111, "end": 112},
                                 },
                        }
                    ),
                ),
                (
                    "part-question-result",
                    "message-assistant",
                    "session-cli",
                    113,
                    113,
                    json.dumps(
                        {
                            "type": "tool",
                            "callID": "tool-question",
                            "tool": "question",
                            "state": {
                                "status": "completed",
                                "input": {
                                    "questions": [
                                        {
                                            "header": "Review mode",
                                            "question": "Which review mode should be used?",
                                            "options": [
                                                {
                                                    "label": "Strict",
                                                    "description": "Use the strict review path.",
                                                }
                                            ],
                                        },
                                        {
                                            "header": "Custom constraint",
                                            "question": "Describe the custom review constraint.",
                                            "options": [
                                                {
                                                    "label": "Provide custom answer",
                                                    "description": "Enter a custom constraint instead.",
                                                }
                                            ],
                                        }
                                    ]
                                },
                                "output": (
                                    'User has answered your questions: "Which review mode should be used?"="Strict", '
                                    f'"Describe the custom review constraint."="{LONG_QUESTION_ANSWER}".'
                                ),
                                "title": "question",
                                "metadata": {},
                                "time": {"start": 113, "end": 114},
                            },
                        }
                    ),
                ),
                (
                    "part-assistant-follow-up-text",
                    "message-assistant",
                    "session-cli",
                    115,
                    115,
                    json.dumps({"type": "text", "text": "assistant follow-up after tools"}),
                ),
                (
                    "part-other-user-text",
                    "message-other-user",
                    "session-other",
                    300,
                    300,
                    json.dumps({"type": "text", "text": "needle elsewhere", "synthetic": False}),
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def _run_cli(args: list[str]) -> tuple[int, str]:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli.main(args)
    return exit_code, stdout.getvalue()


@pytest.mark.parametrize(
    "args",
    [
        ["grep", "--query", "needle"],
        ["show", "--session", "session-cli", "--all", "--type", "all"],
        ["show", "--session", "session-cli", "--anchor", "message-assistant:0002"],
        ["show", "--session", "session-cli", "--block", "message-assistant:0002"],
    ],
)
def test_history_output_defaults_to_utc8_timestamps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    timestamp_ms = int(datetime(2026, 10, 13, 3, 10, 23, tzinfo=timezone.utc).timestamp() * 1000)
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE message SET time_created = time_created + ?", (timestamp_ms,))
        connection.execute("UPDATE part SET time_created = ? WHERE id = 'part-tool-result'", (timestamp_ms + 1234,))
        connection.execute("UPDATE part SET time_created = ? WHERE id = 'part-question-result'", (timestamp_ms + 2000,))
    monkeypatch.setattr(cli, "DEFAULT_UPSTREAM_DATABASE", str(database_path))

    exit_code, output = _run_cli([*args, "--repository", str(repository_path)])

    assert exit_code == 0
    tool_header = next(line for line in output.splitlines() if "[tool_result]" in line)
    assert tool_header.endswith("time=2026-10-13 11:10:24")
    if "--all" in args or args[0] == "grep":
        user_header = next(line for line in output.splitlines() if "[user_text]" in line)
        assert user_header.endswith("time=2026-10-13 11:10:23")


def test_timestamp_handles_epoch_and_utc8_date_rollover() -> None:
    assert cli._format_timestamp(0) == "1970-01-01 08:00:00"
    timestamp_ms = int(datetime(2026, 10, 12, 16, 0, tzinfo=timezone.utc).timestamp() * 1000)
    assert cli._format_timestamp(timestamp_ms) == "2026-10-13 00:00:00"


def test_compile_command_triggers_full_compile(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    exit_code, output = _run_cli(["compile", "--db", str(database_path), "--repository", str(repository_path)])

    assert exit_code == 0
    assert "Compiled 2 session(s)" in output
    assert "session-cli" in output
    assert "session-other" in output
    assert (repository_path / "manifest.json").exists()


def test_grep_command_prints_block_level_results(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    _run_cli(["compile", "--db", str(database_path), "--repository", str(repository_path)])
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)
    exit_code, output = _run_cli(["grep", "--query", "needle", "--repository", str(repository_path)])

    assert exit_code == 0
    assert "[tool_result] session=session-cli" in output
    assert "match:" in output
    assert "anchor=message-assistant:0002" in output


def test_show_command_highlights_focus_block(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    _run_cli(["compile", "--db", str(database_path), "--repository", str(repository_path)])
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--anchor",
            "message-assistant:0002",
            "--repository",
            str(repository_path),
        ]
    )

    assert exit_code == 0
    assert "session=session-cli anchor=message-assistant:0002" in output
    assert ">>> [tool_result]" in output
    assert "needle match line" in output


def test_show_command_can_refresh_repository_from_db(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)
    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--anchor",
            "message-assistant:0002",
            "--repository",
            str(repository_path),
        ]
    )

    assert exit_code == 0
    assert (repository_path / "manifest.json").exists()
    assert "session=session-cli anchor=message-assistant:0002" in output
    assert "needle match line" in output


def test_compile_command_supports_directory_filter(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    exit_code, output = _run_cli(
        [
            "compile",
            "--db",
            str(database_path),
            "--repository",
            str(repository_path),
            "--directory",
            "/repo",
        ]
    )

    assert exit_code == 0
    assert "Compiled 1 session(s)" in output
    assert "session-cli" in output
    assert "session-other" not in output


def test_directory_help_describes_root_and_child_prefix_matching() -> None:
    parser = cli.build_parser()

    compile_help = parser._subparsers._group_actions[0].choices["compile"].format_help()
    grep_help = parser._subparsers._group_actions[0].choices["grep"].format_help()

    assert "workspace directory" in compile_help
    assert "child directory" in compile_help
    assert "same path prefix" in compile_help
    assert "this workspace" in grep_help
    assert "directory or any child directory" in grep_help
    assert "child directory" in grep_help
    assert "same path" in grep_help
    assert "prefix" in grep_help


def test_show_help_describes_unique_text_range_endpoints() -> None:
    parser = cli.build_parser()

    show_help = parser._subparsers._group_actions[0].choices["show"].format_help()

    assert "quoted text:<literal>" in show_help
    assert "uniquely matches one filtered block" in show_help


def test_grep_command_supports_directory_and_time_filters(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    _run_cli(["compile", "--db", str(database_path), "--repository", str(repository_path)])
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "grep",
            "--query",
            "needle",
            "--repository",
            str(repository_path),
            "--directory",
            "/repo",
            "--until",
            "1970-01-01",
        ]
    )

    assert exit_code == 0
    assert "session=session-cli" in output
    assert "session=session-other" not in output


def test_grep_command_prints_text_match_hints_when_no_results(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)
    exit_code, output = _run_cli(["grep", "--repository", str(repository_path), "--query", "missing-keyword"])

    assert exit_code == 0
    assert "No matches found" in output
    assert "search hints:" in output
    assert "try nearby wording or common synonyms" in output
    assert "try both Chinese and English keywords" in output
    assert "try --regex for tighter phrase or multi-line matching" in output


def test_grep_command_can_refresh_repository_from_db(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)
    exit_code, output = _run_cli(
        [
            "grep",
            "--repository",
            str(repository_path),
            "--query",
            "needle",
            "--directory",
            "/repo",
        ]
    )

    assert exit_code == 0
    assert (repository_path / "manifest.json").exists()
    assert "session=session-cli" in output
    assert "session=session-other" not in output


def test_grep_command_supports_regex_query(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)
    exit_code, output = _run_cli(
        [
            "grep",
            "--repository",
            str(repository_path),
            "--query",
            "line before\\nneedle match",
            "--regex",
        ]
    )

    assert exit_code == 0
    assert "[tool_result] session=session-cli" in output


def test_grep_command_paginates_and_prints_page_header(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)
    exit_code, output = _run_cli(["grep", "--repository", str(repository_path), "--query", "needle", "--page-size", "1"])

    assert exit_code == 0
    assert "page 1/3 · total 3" in output
    assert "narrowing hints:" in output
    assert "try --type assistant" in output
    assert "try --since/--until" in output


def test_grep_command_supports_multiple_queries_with_and_logic(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)
    exit_code, output = _run_cli(
        [
            "grep",
            "--repository",
            str(repository_path),
            "--query",
            "elsewhere",
            "--query",
            "grep",
            "--logic",
            "and",
        ]
    )

    assert exit_code == 0
    assert "session=session-cli" not in output
    assert "session=session-other" not in output
    
def test_grep_command_supports_multiple_queries_with_or_logic(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)
    exit_code, output = _run_cli(
        [
            "grep",
            "--repository",
            str(repository_path),
            "--query",
            "elsewhere",
            "--query",
            "grep",
            "--logic",
            "or",
        ]
    )

    assert exit_code == 0
    assert "session=session-cli" in output
    assert "session=session-other" in output

def test_grep_command_supports_message_alias(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)

    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)
    exit_code, output = _run_cli(
        [
            "grep",
            "--repository",
            str(repository_path),
            "--query",
            "needle",
            "--type",
            "message",
        ]
    )

    assert exit_code == 0
    assert "[user_text]" in output
    assert "[tool_result]" not in output


def test_show_command_supports_all_and_full_text(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    _run_cli(["compile", "--db", str(database_path), "--repository", str(repository_path)])

    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)
    exit_code, output = _run_cli(["show", "--session", "session-cli", "--repository", str(repository_path), "--all", "--type", "all", "--full-text"])

    assert exit_code == 0
    assert "[user_text]" in output
    assert "[tool_result]" in output


def test_show_command_defaults_all_view_to_message_blocks(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(["show", "--session", "session-cli", "--repository", str(repository_path), "--all"])

    assert exit_code == 0
    assert "[user_text]" in output
    assert "[user_decision]" in output
    assert "[assistant_text]" in output
    assert "[tool_result]" not in output


def test_show_command_user_type_includes_completed_question_decisions(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--repository",
            str(repository_path),
            "--all",
            "--type",
            "user",
            "--full-text",
        ]
    )

    assert exit_code == 0
    assert "[user_text]" in output
    assert "[user_decision]" in output
    assert "Which review mode should be used?" in output
    assert "Use the strict review path." in output
    assert '"Strict"' in output
    assert "custom-answer-middle-marker" in output
    assert "[assistant_text]" not in output
    assert "[tool_result]" not in output


def test_show_command_combines_user_and_assistant_types_in_conversation_order(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--repository",
            str(repository_path),
            "--all",
            "--type",
            "user",
            "--type",
            "assistant",
            "--full-text",
        ]
    )

    assert exit_code == 0
    assert output.index("[user_text]") < output.index("[assistant_text]") < output.index("[user_decision]")
    assert "[tool_result]" not in output


def test_show_command_assistant_type_combines_visible_text_parts_and_excludes_tools(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--repository",
            str(repository_path),
            "--all",
            "--type",
            "assistant",
            "--full-text",
        ]
    )

    assert exit_code == 0
    assert output.index("assistant context") < output.index("assistant follow-up after tools")
    assert output.count(">>> [assistant_text]") == 1
    assert "[tool_result]" not in output
    assert "[user_decision]" not in output


def test_grep_tool_result_type_keeps_completed_question_decisions(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "grep",
            "--repository",
            str(repository_path),
            "--query",
            "Which review mode should be used?",
            "--type",
            "tool_result",
        ]
    )

    assert exit_code == 0
    assert "[user_decision]" in output


def test_show_command_supports_all_type_and_full_text(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--repository",
            str(repository_path),
            "--all",
            "--type",
            "all",
            "--full-text",
        ]
    )

    assert exit_code == 0
    assert "[user_text]" in output
    assert "[tool_result]" in output


def test_show_command_supports_block_id_range_for_all_view(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--repository",
            str(repository_path),
            "--all",
            "--type",
            "all",
            "--from",
            "message-assistant:0001",
            "--to",
            "message-assistant:0002",
        ]
    )

    assert exit_code == 0
    assert "[user_text]" not in output
    assert "[assistant_text]" in output
    assert "[tool_result]" in output


def test_show_command_supports_open_ended_block_index_range_for_all_view(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--repository",
            str(repository_path),
            "--all",
            "--type",
            "all",
            "--from",
            "1",
        ]
    )

    assert exit_code == 0
    assert "[user_text]" not in output
    assert "[assistant_text]" in output
    assert "[tool_result]" in output


def test_show_command_supports_unique_text_range_for_all_view(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--repository",
            str(repository_path),
            "--all",
            "--type",
            "all",
            "--from",
            "text:assistant context",
            "--to",
            "text:needle match line",
        ]
    )

    assert exit_code == 0
    assert "[user_text]" not in output
    assert "[assistant_text]" in output
    assert "[tool_result]" in output


def test_show_command_resolves_text_range_after_type_filtering(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--repository",
            str(repository_path),
            "--all",
            "--type",
            "user",
            "--from",
            "text:needle",
            "--to",
            "text:needle",
        ]
    )

    assert exit_code == 0
    assert "[user_text]" in output
    assert "[tool_result]" not in output


def test_show_command_rejects_text_range_without_a_match(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    with pytest.raises(SystemExit, match="matched no blocks"):
        _run_cli(
            [
                "show",
                "--session",
                "session-cli",
                "--repository",
                str(repository_path),
                "--all",
                "--type",
                "all",
                "--from",
                "text:missing boundary",
            ]
        )


def test_show_command_rejects_text_range_with_multiple_matches(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    with pytest.raises(SystemExit, match="matched multiple blocks"):
        _run_cli(
            [
                "show",
                "--session",
                "session-cli",
                "--repository",
                str(repository_path),
                "--all",
                "--type",
                "all",
                "--from",
                "text:needle",
            ]
        )


def test_show_command_block_reads_complete_raw_tool_output_by_block_id(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--repository",
            str(repository_path),
            "--block",
            "message-assistant:0002",
        ]
    )

    assert exit_code == 0
    assert "[tool_result]" in output
    assert "raw middle line 15" in output
    assert "lines omitted" not in output


def test_show_command_block_reads_question_input_and_selected_answer(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--repository",
            str(repository_path),
            "--block",
            "message-assistant:0003",
        ]
    )

    assert exit_code == 0
    assert '"question": "Which review mode should be used?"' in output
    assert '"description": "Use the strict review path."' in output
    assert '"Which review mode should be used?"="Strict"' in output
    assert "custom-answer-middle-marker" in output


def test_show_user_decision_preserves_long_custom_answer_for_text_endpoint(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--repository",
            str(repository_path),
            "--all",
            "--type",
            "user",
            "--from",
            "text:custom-answer-middle-marker",
            "--to",
            "text:custom-answer-middle-marker",
            "--full-text",
        ]
    )

    assert exit_code == 0
    assert "[user_decision]" in output
    assert "custom-answer-middle-marker" in output


def test_show_command_block_supports_comma_separated_ids_and_indexes(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--repository",
            str(repository_path),
            "--block",
            "0,message-assistant:0002",
        ]
    )

    assert exit_code == 0
    assert "[user_text]" in output
    assert "needle in user text" in output
    assert "[tool_result]" in output
    assert "raw middle line 15" in output


def test_show_command_supports_custom_before_after(tmp_path: Path) -> None:
    database_path = tmp_path / "history.db"
    repository_path = tmp_path / "compiled_repo"
    _create_history_db(database_path)
    _run_cli(["compile", "--db", str(database_path), "--repository", str(repository_path)])
    cli.DEFAULT_UPSTREAM_DATABASE = str(database_path)

    exit_code, output = _run_cli(
        [
            "show",
            "--session",
            "session-cli",
            "--anchor",
            "message-assistant:0002",
            "--repository",
            str(repository_path),
            "--before",
            "2",
            "--after",
            "0",
        ]
    )

    assert exit_code == 0
    assert ">>> [tool_result]" in output


def test_module_entrypoint_reports_invalid_time_filter(tmp_path: Path) -> None:
    env = dict(os.environ)
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else f"{src_path}:{existing_pythonpath}"

    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "opencode_history_grep.cli",
            "grep",
            "--repository",
            str(tmp_path / "repo"),
            "--query",
            "needle",
            "--since",
            "not-a-date",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert process.returncode != 0
    assert "Invalid time filter: not-a-date. Use ISO 8601 date or datetime." in process.stderr
