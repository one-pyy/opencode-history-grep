from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .reader import HistoryReader, SessionFilter
from .repository import compile_all_sessions, open_compiled_repository
from .search_show import (
    SearchAnchor,
    normalize_block_type_filters,
    paginate_search_results,
    search_compiled_repository,
    show_compiled_context,
    show_session_compiled_view,
)

DEFAULT_REPOSITORY_DIRNAME = "/root/.local/share/opencode-history-grep"
DEFAULT_UPSTREAM_DATABASE = "/root/.local/share/opencode/opencode.db"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opencode-history-grep",
        description="Compiled grep CLI for opencode upstream history.",
    )
    subparsers = parser.add_subparsers(dest="command")

    compile_parser = subparsers.add_parser("compile", help="Compile session history into block views.")
    _ = compile_parser.add_argument(
        "--db",
        dest="database_path",
        default=DEFAULT_UPSTREAM_DATABASE,
        help=f"Path to upstream SQLite database. Default: {DEFAULT_UPSTREAM_DATABASE}",
    )
    _ = compile_parser.add_argument(
        "--repository",
        dest="repository_path",
        default=DEFAULT_REPOSITORY_DIRNAME,
        help="Path to the local compiled repository.",
    )
    _ = compile_parser.add_argument(
        "--directory",
        dest="directory",
        help="Restrict sessions to this workspace directory or any child directory with the same path prefix.",
    )
    _ = compile_parser.add_argument("--since", dest="since", help="Restrict sessions to updated/effective time on or after this ISO date/time.")
    _ = compile_parser.add_argument("--until", dest="until", help="Restrict sessions to updated/effective time on or before this ISO date/time.")

    grep_parser = subparsers.add_parser("grep", help="Search compiled history blocks.")
    _ = grep_parser.add_argument("--query", dest="queries", action="append", required=True, help="Search query. Repeatable.")
    _ = grep_parser.add_argument("--regex", action="store_true", help="Interpret --query as a regular expression, with cross-line matching enabled.")
    _ = grep_parser.add_argument("--logic", choices=["and", "or"], default="or", help="How multiple --query values combine. Default: or")
    _ = grep_parser.add_argument("--type", dest="block_types", action="append", help="Filter block types. Repeatable: user, assistant|ai, tool_call, tool|tool_result.")
    _ = grep_parser.add_argument("--page", dest="page", type=int, default=1, help="Result page number. Default: 1")
    _ = grep_parser.add_argument("--page-size", dest="page_size", type=int, default=10, help="Results per page. Default: 10")
    _ = grep_parser.add_argument(
        "--repository",
        dest="repository_path",
        default=DEFAULT_REPOSITORY_DIRNAME,
        help="Path to the local compiled repository.",
    )
    _ = grep_parser.add_argument(
        "--directory",
        dest="directory",
        help="Restrict search to sessions in this workspace directory or any child directory with the same path prefix.",
    )
    _ = grep_parser.add_argument("--since", dest="since", help="Restrict search to sessions on or after this ISO date/time.")
    _ = grep_parser.add_argument("--until", dest="until", help="Restrict search to sessions on or before this ISO date/time.")

    show_parser = subparsers.add_parser("show", help="Show full context for a compiled anchor.")
    _ = show_parser.add_argument("--session", dest="session_id", required=True, help="Session ID.")
    _ = show_parser.add_argument("--anchor", help="Compiled anchor identifier.")
    _ = show_parser.add_argument("--block", dest="block_ids", action="append", help="Show complete raw content for block id(s) or zero-based block index(es). Comma-separated values are allowed.")
    _ = show_parser.add_argument("--before", dest="before", type=int, default=1, help="Blocks to show before the focus anchor. Default: 1")
    _ = show_parser.add_argument("--after", dest="after", type=int, default=1, help="Blocks to show after the focus anchor. Default: 1")
    _ = show_parser.add_argument("--all", dest="show_all", action="store_true", help="Show the full compiled session view.")
    _ = show_parser.add_argument("--full-text", dest="full_text", action="store_true", help="Do not truncate long block display text.")
    _ = show_parser.add_argument("--type", dest="block_types", action="append", help="Filter full-session view block types. Repeatable: message, all, user, assistant|ai, tool_call, tool|tool_result.")
    _ = show_parser.add_argument("--from", dest="from_block", help="When used with --all, start at this block id or zero-based block index.")
    _ = show_parser.add_argument("--to", dest="to_block", help="When used with --all, end at this block id or zero-based block index.")
    _ = show_parser.add_argument(
        "--repository",
        dest="repository_path",
        default=DEFAULT_REPOSITORY_DIRNAME,
        help="Path to the local compiled repository.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = getattr(args, "command", None)

    if not isinstance(command, str):
        parser.print_help()
        return 0

    if command == "compile":
        return _run_compile(
            database_path=args.database_path,
            repository_path=args.repository_path,
            session_filter=_build_session_filter(directory=args.directory, since=args.since, until=args.until),
        )
    if command == "grep":
        return _run_grep(
            queries=tuple(args.queries),
            query_logic=str(args.logic),
            use_regex=bool(args.regex),
            block_types=normalize_block_type_filters(args.block_types),
            page=max(1, int(args.page)),
            page_size=max(1, int(args.page_size)),
            repository_path=args.repository_path,
            session_filter=_build_session_filter(directory=args.directory, since=args.since, until=args.until),
        )
    if command == "show":
        return _run_show(
            session_id=args.session_id,
            anchor_id=args.anchor,
            block_ids=args.block_ids,
            before=max(0, int(args.before)),
            after=max(0, int(args.after)),
            show_all=bool(args.show_all),
            full_text=bool(args.full_text),
            block_types=normalize_block_type_filters(args.block_types),
            from_block=args.from_block,
            to_block=args.to_block,
            repository_path=args.repository_path,
        )

    parser.error(f"Unknown command: {command}")
    return 2


def _run_compile(*, database_path: str, repository_path: str, session_filter: SessionFilter | None) -> int:
    reader = HistoryReader(database_path)
    repository = open_compiled_repository(repository_path)
    result = compile_all_sessions(reader, repository, session_filter=session_filter)

    print(f"Compiled {len(result.compiled_session_ids)} session(s) into {result.repository_path}")
    for session_id in result.compiled_session_ids:
        print(f"- {session_id}")
    return 0


def _run_grep(
    *,
    queries: tuple[str, ...],
    query_logic: str,
    use_regex: bool,
    block_types: set[str] | None,
    page: int,
    page_size: int,
    repository_path: str,
    session_filter: SessionFilter | None,
) -> int:
    reader = HistoryReader(DEFAULT_UPSTREAM_DATABASE)
    repository = open_compiled_repository(repository_path)
    compile_all_sessions(reader, repository, session_filter=session_filter)
    repository = open_compiled_repository(repository_path)
    results = search_compiled_repository(
        repository,
        queries,
        query_logic=query_logic,
        session_filter=session_filter,
        use_regex=use_regex,
        block_types=block_types,
    )
    if not results:
        print(f'No matches found for {queries!r}.')
        _print_no_match_hints(use_regex=use_regex)
        return 0

    page_result = paginate_search_results(results, page=page, page_size=page_size)
    print(f"page {page_result.page}/{page_result.total_pages} · total {page_result.total_results}")
    _print_result_hints(
        total_results=page_result.total_results,
        page_size=page_result.page_size,
        queries=queries,
        query_logic=query_logic,
        use_regex=use_regex,
        block_types=block_types,
        session_filter=session_filter,
    )
    print()
    for result in page_result.results:
        print(f"[{result.block_type}] session={result.session_id} anchor={result.anchor.block_id}")
        print(f'match: "{result.match_text}"')
        print()
    return 0


def _run_show(
    *,
    session_id: str,
    anchor_id: str | None,
    block_ids: list[str] | None,
    before: int,
    after: int,
    show_all: bool,
    full_text: bool,
    block_types: set[str] | None,
    from_block: str | None,
    to_block: str | None,
    repository_path: str,
) -> int:
    reader = HistoryReader(DEFAULT_UPSTREAM_DATABASE)
    repository = open_compiled_repository(repository_path)
    compile_all_sessions(reader, repository, session_filter=None)
    repository = open_compiled_repository(repository_path)
    if block_ids:
        if show_all or anchor_id is not None or block_types is not None or from_block is not None or to_block is not None:
            raise SystemExit("show --block cannot be combined with --all, --anchor, --type, --from, or --to.")
        shown = show_session_compiled_view(
            repository,
            session_id,
            full_text=True,
            block_types=normalize_block_type_filters(["all"]),
        )
        selected_blocks = _resolve_selected_blocks(shown.blocks, _parse_block_ids(block_ids))
        session = reader.load_session(session_id)
        raw_messages = {message.id: message for message in session.messages}
        for block in selected_blocks:
            print(f"[{block.block_type}] {block.title} ({block.block_id})")
            print(_raw_block_text(block=block, raw_messages=raw_messages))
            print()
        return 0
    if show_all:
        shown = show_session_compiled_view(
            repository,
            session_id,
            full_text=full_text,
            block_types=block_types or normalize_block_type_filters(["message"]),
            from_block=from_block,
            to_block=to_block,
        )
    else:
        if block_types is not None or from_block is not None or to_block is not None:
            raise SystemExit("show --type/--from/--to require --all.")
        if not isinstance(anchor_id, str):
            raise SystemExit("show requires --anchor unless --all is set.")
        shown = show_compiled_context(
            repository,
            SearchAnchor(session_id=session_id, block_id=anchor_id),
            before=before,
            after=after,
            full_text=full_text,
        )

    print(f"session={shown.anchor.session_id} anchor={shown.anchor.block_id}")
    for block in shown.blocks:
        marker = ">>>" if block.block_id == shown.focus_block_id else "   "
        print(f"{marker} [{block.block_type}] {block.title} ({block.block_id})")
        print(block.display_text)
        print()
    return 0


def _parse_block_ids(values: list[str]) -> list[str]:
    block_ids: list[str] = []
    for value in values:
        block_ids.extend(part.strip() for part in value.split(",") if part.strip())
    if not block_ids:
        raise SystemExit("show --block requires at least one block id or index.")
    return block_ids


def _resolve_selected_blocks(blocks: tuple[Any, ...], block_ids: list[str]) -> list[Any]:
    selected: list[Any] = []
    missing: list[str] = []
    for block_id in block_ids:
        block = _find_block(blocks, block_id)
        if block is None:
            missing.append(block_id)
        else:
            selected.append(block)
    if missing:
        raise SystemExit(f"Unknown block id(s): {', '.join(missing)}")
    return selected


def _find_block(blocks: tuple[Any, ...], block_id: str) -> Any | None:
    if block_id.isdigit():
        index = int(block_id)
        if 0 <= index < len(blocks):
            return blocks[index]
        return None
    return next((block for block in blocks if block.block_id == block_id), None)


def _raw_block_text(*, block: Any, raw_messages: Mapping[str, Any]) -> str:
    message = raw_messages.get(block.message_id)
    if message is None:
        raise SystemExit(f"Cannot find raw message for block {block.block_id}.")
    if block.part_id is None:
        text_chunks = [str(part.data.get("text", "")).strip() for part in message.parts if part.kind == "text"]
        return "\n\n".join(chunk for chunk in text_chunks if chunk)

    part = next((candidate for candidate in message.parts if candidate.id == block.part_id), None)
    if part is None:
        raise SystemExit(f"Cannot find raw part for block {block.block_id}.")
    if part.kind != "tool":
        return _format_json_value(part.data)

    tool_name = str(part.data.get("tool", "unknown"))
    state = part.data.get("state")
    if not isinstance(state, Mapping):
        return f"tool: {tool_name}\n\n{_format_json_value(part.data)}"

    lines = [f"tool: {tool_name}", f"status: {state.get('status', 'unknown')}"]
    if "input" in state:
        lines.extend(["", "input:", _format_json_value(state["input"])])
    if "output" in state:
        lines.extend(["", "output:", _format_json_value(state["output"])])
    if "error" in state:
        lines.extend(["", "error:", _format_json_value(state["error"])])
    return "\n".join(lines)


def _format_json_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _build_session_filter(*, directory: str | None, since: str | None, until: str | None) -> SessionFilter | None:
    directory_prefix = Path(directory).expanduser().resolve() if isinstance(directory, str) else None
    since_ts = _parse_time_filter(since) if since is not None else None
    until_ts = _parse_time_filter(until, end_of_day=True) if until is not None else None
    if directory_prefix is None and since_ts is None and until_ts is None:
        return None
    return SessionFilter(directory_prefix=directory_prefix, since=since_ts, until=until_ts)


def _parse_time_filter(value: str, *, end_of_day: bool = False) -> int:
    normalized = value.strip()
    if "T" not in normalized and len(normalized) == 10:
        normalized = f"{normalized}T23:59:59" if end_of_day else f"{normalized}T00:00:00"
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as error:
        raise SystemExit(f"Invalid time filter: {value}. Use ISO 8601 date or datetime.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def _print_result_hints(
    *,
    total_results: int,
    page_size: int,
    queries: tuple[str, ...],
    query_logic: str,
    use_regex: bool,
    block_types: set[str] | None,
    session_filter: SessionFilter | None,
) -> None:
    if total_results <= page_size:
        return

    hints: list[str] = []
    if block_types is None:
        hints.append("try --type assistant")
    if session_filter is None or (session_filter.since is None and session_filter.until is None):
        hints.append("try --since/--until")
    if len(queries) > 1 and query_logic == "or":
        hints.append("try --logic and")
    if not use_regex:
        hints.append("try --regex")

    if not hints:
        return

    print("narrowing hints:")
    for hint in hints:
        print(f"- {hint}")


def _print_no_match_hints(*, use_regex: bool) -> None:
    print("search hints:")
    print("- try nearby wording or common synonyms")
    print("- if earlier work may have mixed Chinese and English, try both Chinese and English keywords")
    if not use_regex:
        print("- try --regex for tighter phrase or multi-line matching")


if __name__ == "__main__":
    raise SystemExit(main())
