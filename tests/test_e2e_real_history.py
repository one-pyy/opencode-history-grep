from __future__ import annotations

from collections import Counter, defaultdict
from importlib import import_module
import io
import json
import random
import re
import sqlite3
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

REAL_UPSTREAM_DB = Path("/root/.local/share/opencode/opencode.db")
REQUIRED_SEARCH_KINDS: tuple[str, ...] = ("user", "assistant", "tool_call", "tool_result", "compaction", "subtask")
MIN_RANDOM_SAMPLE_SIZE = 50
TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]{4,}")


def _load_e2e_api() -> tuple[Any, Any, Any, Any, Any, Any]:
    package_root = str(Path(__file__).resolve().parents[1] / "src")
    if package_root not in sys.path:
        sys.path.insert(0, package_root)

    cli_module = import_module("opencode_history_grep.cli")
    repository_module = import_module("opencode_history_grep.repository")
    search_module = import_module("opencode_history_grep.search_show")
    return (
        cli_module,
        repository_module.load_repository_manifest,
        repository_module.open_compiled_repository,
        search_module.SearchAnchor,
        search_module.search_compiled_repository,
        search_module.show_compiled_context,
    )


cli, load_repository_manifest, open_compiled_repository, SearchAnchor, search_compiled_repository, show_compiled_context = (
    _load_e2e_api()
)


def _load_pytest() -> Any:
    return import_module("pytest")


pytest = _load_pytest()


def _run_cli(args: list[str]) -> tuple[int, str]:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli.main(args)
    return exit_code, stdout.getvalue()


def _iter_real_units(database_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    connection = sqlite3.connect(database_path)
    try:
        message_rows = connection.execute("SELECT id, session_id, data FROM message").fetchall()
        part_rows = connection.execute("SELECT id, message_id, session_id, data FROM part").fetchall()
    finally:
        connection.close()

    units: list[dict[str, Any]] = []
    system_texts: list[str] = []

    for message_id, session_id, raw_data in message_rows:
        data = _load_json_object(raw_data)
        role = data.get("role")
        if role in {"user", "assistant"}:
            units.append(
                {
                    "kind": str(role),
                    "session_id": session_id,
                    "message_id": message_id,
                    "record_id": message_id,
                }
            )

        system_text = data.get("system")
        if isinstance(system_text, str) and system_text.strip():
            system_texts.append(system_text.strip())

    for part_id, message_id, session_id, raw_data in part_rows:
        data = _load_json_object(raw_data)
        part_type = data.get("type")
        kind: str | None = None
        if part_type == "tool":
            state = data.get("state")
            status = state.get("status") if isinstance(state, dict) else None
            if status in {"pending", "running"}:
                kind = "tool_call"
            elif status in {"completed", "error"}:
                kind = "tool_result"
        elif part_type in {"compaction", "subtask"}:
            kind = str(part_type)

        if kind is None:
            continue

        units.append(
            {
                "kind": kind,
                "session_id": session_id,
                "message_id": message_id,
                "record_id": part_id,
            }
        )

    return units, system_texts


def _build_sample_report(database_path: Path) -> dict[str, Any]:
    units, system_texts = _iter_real_units(database_path)
    assert len(units) >= MIN_RANDOM_SAMPLE_SIZE, "Real upstream history does not contain enough units for the 50-sample E2E path."

    random_sample = random.Random(0).sample(units, MIN_RANDOM_SAMPLE_SIZE)
    available_by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in units:
        available_by_kind[str(unit["kind"])].append(unit)

    random_kinds = {str(unit["kind"]) for unit in random_sample}
    supplemented: list[dict[str, Any]] = []
    for kind in REQUIRED_SEARCH_KINDS:
        if kind not in random_kinds and available_by_kind[kind]:
            supplemented.append(available_by_kind[kind][0])

    covered_after_supplement = sorted(random_kinds | {str(unit["kind"]) for unit in supplemented})
    unavailable_kinds = sorted(kind for kind in REQUIRED_SEARCH_KINDS if not available_by_kind[kind])

    return {
        "database_path": str(database_path),
        "random_sample_size": len(random_sample),
        "available_counts": {kind: len(available_by_kind[kind]) for kind in REQUIRED_SEARCH_KINDS},
        "random_sample_kinds": sorted(random_kinds),
        "supplemented_kinds": sorted({str(unit["kind"]) for unit in supplemented}),
        "covered_after_supplement": covered_after_supplement,
        "missing_after_supplement": sorted(set(REQUIRED_SEARCH_KINDS) - set(covered_after_supplement)),
        "system_sample_count": len(system_texts),
    }


def _iter_compiled_blocks(repository_path: Path) -> list[dict[str, Any]]:
    repository = open_compiled_repository(repository_path)
    manifest = load_repository_manifest(repository)
    compiled_blocks: list[dict[str, Any]] = []
    for session_id, metadata in manifest.sessions.items():
        artifact_path = repository.root / metadata.artifact_relpath
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        for block in payload["blocks"]:
            compiled_blocks.append({"session_id": session_id, **block})
    return compiled_blocks


def _choose_cross_session_query(compiled_blocks: list[dict[str, Any]]) -> str:
    token_sessions: dict[str, set[str]] = defaultdict(set)
    for block in compiled_blocks:
        for token in TOKEN_RE.findall(str(block.get("search_text", ""))):
            normalized = token.lower()
            if normalized.isdigit() or len(normalized) < 5:
                continue
            token_sessions[normalized].add(str(block["session_id"]))

    candidates = [token for token, sessions in token_sessions.items() if len(sessions) >= 2]
    assert candidates, "No cross-session search token found in compiled real history."
    return sorted(candidates, key=lambda token: (len(token_sessions[token]), len(token)))[0]


def _choose_tool_call_query(compiled_blocks: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    for block in compiled_blocks:
        if block.get("block_type") != "tool_call":
            continue
        lines = [line.strip() for line in str(block.get("display_text", "")).splitlines() if line.strip()]
        for line in lines[1:]:
            for token in TOKEN_RE.findall(line):
                if token.lower() not in {"tool", "status", "true", "false", "null"}:
                    return block, token
    raise AssertionError("No real-history tool_call block with searchable parameters was found.")


def _choose_tool_result_query(compiled_blocks: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    tool_blocks = [block for block in compiled_blocks if block.get("block_type") == "tool_result"]
    tool_blocks.sort(key=lambda block: len(str(block.get("display_text", ""))), reverse=True)
    for block in tool_blocks:
        lines = [line.strip() for line in str(block.get("display_text", "")).splitlines() if line.strip()]
        content_lines = [line for line in lines if not line.startswith("tool:") and not line.startswith("status:")]
        for line in content_lines:
            for token in TOKEN_RE.findall(line):
                if token.lower() not in {"completed", "error", "tool", "status"}:
                    return block, token
    raise AssertionError("No real-history tool_result block with searchable output was found.")


def _choose_system_exclusion_query(system_texts: list[str], repository_path: Path) -> str:
    for system_text in system_texts[:200]:
        for line in system_text.splitlines():
            candidate = line.strip()
            if len(candidate) < 12:
                continue
            results = search_compiled_repository(repository_path, candidate)
            if not results:
                return candidate
        for token in TOKEN_RE.findall(system_text):
            if len(token) < 8:
                continue
            results = search_compiled_repository(repository_path, token)
            if not results:
                return token
    raise AssertionError("Unable to find a system-only query for exclusion verification.")


def _load_json_object(raw_data: str) -> dict[str, Any]:
    data = json.loads(raw_data)
    if not isinstance(data, dict):
        raise AssertionError("Expected upstream SQLite JSON payloads to be objects.")
    return data


def test_real_history_end_to_end_flow(tmp_path: Path) -> None:
    if not REAL_UPSTREAM_DB.exists():
        pytest.skip(f"Real upstream SQLite database not found at {REAL_UPSTREAM_DB}.")

    repository_path = tmp_path / "compiled_repo"
    sample_report = _build_sample_report(REAL_UPSTREAM_DB)
    report_path = tmp_path / "real_history_e2e_report.json"
    report_path.write_text(json.dumps(sample_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert sample_report["random_sample_size"] == MIN_RANDOM_SAMPLE_SIZE
    required_kinds = set(REQUIRED_SEARCH_KINDS)
    missing_kinds = set(str(kind) for kind in sample_report["missing_after_supplement"])
    assert set(sample_report["covered_after_supplement"]) == required_kinds - missing_kinds
    assert set(sample_report["missing_after_supplement"]) == {
        kind for kind, count in sample_report["available_counts"].items() if count == 0
    }
    assert sample_report["system_sample_count"] > 0

    compile_exit_code, compile_output = _run_cli(
        ["compile", "--db", str(REAL_UPSTREAM_DB), "--repository", str(repository_path)]
    )
    assert compile_exit_code == 0
    assert "Compiled" in compile_output

    compiled_blocks = _iter_compiled_blocks(repository_path)
    assert compiled_blocks
    assert all(block["block_type"] != "system" for block in compiled_blocks)

    cross_session_query = _choose_cross_session_query(compiled_blocks)
    cross_session_results = search_compiled_repository(repository_path, cross_session_query)
    assert len({result.session_id for result in cross_session_results}) >= 2
    assert len({(result.session_id, result.block_id) for result in cross_session_results}) == len(cross_session_results)
    assert all(result.summary for result in cross_session_results)
    assert all(result.anchor.block_id == result.block_id for result in cross_session_results)

    tool_call_block, tool_call_query = _choose_tool_call_query(compiled_blocks)
    tool_call_results = search_compiled_repository(repository_path, tool_call_query)
    matched_tool_call = next(
        result
        for result in tool_call_results
        if result.session_id == tool_call_block["session_id"] and result.block_id == tool_call_block["block_id"]
    )
    assert matched_tool_call.block_type == "tool_call"
    assert tool_call_query.lower() in matched_tool_call.match_text.lower()

    tool_result_block, tool_result_query = _choose_tool_result_query(compiled_blocks)
    grep_exit_code, grep_output = _run_cli(
        ["grep", "--query", tool_result_query, "--repository", str(repository_path)]
    )
    assert grep_exit_code == 0
    assert "summary:" in grep_output
    assert "match:" in grep_output

    tool_result_results = search_compiled_repository(repository_path, tool_result_query)
    matched_tool_result = next(
        result
        for result in tool_result_results
        if result.session_id == tool_result_block["session_id"] and result.block_id == tool_result_block["block_id"]
    )
    assert matched_tool_result.block_type == "tool_result"
    assert tool_result_query.lower() in matched_tool_result.match_text.lower()
    assert len(matched_tool_result.match_text) < len(str(tool_result_block["display_text"]))
    assert f"[{matched_tool_result.block_type}] session={matched_tool_result.session_id}" in grep_output
    assert f"anchor={matched_tool_result.block_id}" in grep_output

    system_texts = _iter_real_units(REAL_UPSTREAM_DB)[1]
    system_query = _choose_system_exclusion_query(system_texts, repository_path)
    assert search_compiled_repository(repository_path, system_query) == []

    shown = show_compiled_context(
        repository_path,
        SearchAnchor(session_id=matched_tool_result.session_id, block_id=matched_tool_result.block_id),
    )
    assert shown.focus_block_id == matched_tool_result.block_id
    assert all(block.block_type != "system" for block in shown.blocks)
    assert any(block.block_id == matched_tool_result.block_id for block in shown.blocks)

    show_exit_code, show_output = _run_cli(
        [
            "show",
            "--session",
            matched_tool_result.session_id,
            "--anchor",
            matched_tool_result.block_id,
            "--repository",
            str(repository_path),
        ]
    )
    assert show_exit_code == 0
    assert f"session={matched_tool_result.session_id} anchor={matched_tool_result.block_id}" in show_output
    assert f">>> [{matched_tool_result.block_type}]" in show_output
