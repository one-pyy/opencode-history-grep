from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from math import ceil
from typing import Any, Literal

from .repository import CompiledRepository, load_repository_manifest, open_compiled_repository
from .reader import SessionFilter

TOOL_RESULT_MATCH_WINDOW_LINES = 5
TOOL_RESULT_MATCH_WINDOW_CHARS = 500
SHOW_CONTEXT_RADIUS = 1
DEFAULT_PAGE_SIZE = 10
DEFAULT_TEXT_MATCH_MAX_CHARS = 500
DEFAULT_TEXT_SHOW_MAX_CHARS = 1200
BLOCK_FILTER_ALIASES = {
    "user": {"user_text"},
    "assistant": {"assistant_text"},
    "ai": {"assistant_text"},
    "tool_call": {"tool_call"},
    "tool": {"tool_call", "tool_result"},
    "tool_result": {"tool_result"},
    "message": {"user_text", "assistant_text"},
}


@dataclass(frozen=True, slots=True)
class SearchAnchor:
    session_id: str
    block_id: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    session_id: str
    block_id: str
    block_type: str
    match_text: str
    anchor: SearchAnchor
    score: int


@dataclass(frozen=True, slots=True)
class SearchPage:
    page: int
    total_pages: int
    total_results: int
    page_size: int
    results: tuple[SearchResult, ...]


@dataclass(frozen=True, slots=True)
class ShowBlock:
    session_id: str
    block_id: str
    block_type: str
    title: str
    display_text: str


@dataclass(frozen=True, slots=True)
class ShowResult:
    anchor: SearchAnchor
    focus_block_id: str
    blocks: tuple[ShowBlock, ...]


def search_compiled_repository(
    repository: CompiledRepository | str | Path,
    queries: tuple[str, ...],
    *,
    query_logic: str = "or",
    session_filter: SessionFilter | None = None,
    use_regex: bool = False,
    block_types: set[str] | None = None,
) -> list[SearchResult]:
    compiled_repository = _coerce_repository(repository)
    manifest = load_repository_manifest(compiled_repository)
    patterns = [_compile_search_pattern(query, use_regex=use_regex) for query in queries]
    results: list[SearchResult] = []

    for session_id, metadata in manifest.sessions.items():
        if session_filter is not None and not session_filter.matches(
            _metadata_to_summary(session_id=session_id, metadata=metadata)
        ):
            continue
        artifact_path = compiled_repository.root / metadata.artifact_relpath
        session_payload = _load_session_payload(artifact_path)
        
        session_hit_patterns: set[int] = set()
        session_results: list[SearchResult] = []

        for block in session_payload["blocks"]:
            search_text = str(block.get("search_text", ""))
            block_type = str(block["block_type"])
            if block_types is not None and block_type not in block_types:
                continue
            
            block_hit_patterns: set[int] = set()
            first_match_text = ""
            
            for i, pattern in enumerate(patterns):
                if pattern.search(search_text):
                    block_hit_patterns.add(i)
                    session_hit_patterns.add(i)
                    if not first_match_text:
                        first_match_text = _build_match_text(block=block, pattern=pattern)

            if not block_hit_patterns:
                continue

            score = _score_block_match(search_text=search_text, queries=queries, patterns=patterns, use_regex=use_regex)
            session_results.append(
                SearchResult(
                    session_id=session_id,
                    block_id=str(block["block_id"]),
                    block_type=block_type,
                    match_text=first_match_text,
                    anchor=SearchAnchor(session_id=session_id, block_id=str(block["block_id"])),
                    score=score,
                )
            )
            
        if query_logic == "and" and len(session_hit_patterns) < len(patterns):
            continue
            
        results.extend(session_results)

    return sorted(
        results,
        key=lambda result: (
            result.score,
            int(manifest.sessions[result.session_id].effective_time),
            result.session_id,
            result.block_id,
        ),
        reverse=True,
    )


def paginate_search_results(
    results: list[SearchResult],
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> SearchPage:
    normalized_page_size = max(1, page_size)
    total_results = len(results)
    total_pages = max(1, ceil(total_results / normalized_page_size))
    normalized_page = min(max(1, page), total_pages)
    start = (normalized_page - 1) * normalized_page_size
    end = start + normalized_page_size
    return SearchPage(
        page=normalized_page,
        total_pages=total_pages,
        total_results=total_results,
        page_size=normalized_page_size,
        results=tuple(results[start:end]),
    )


def show_compiled_context(
    repository: CompiledRepository | str | Path,
    anchor: SearchAnchor,
    *,
    before: int = SHOW_CONTEXT_RADIUS,
    after: int = SHOW_CONTEXT_RADIUS,
    full_text: bool = False,
) -> ShowResult:
    compiled_repository = _coerce_repository(repository)
    manifest = load_repository_manifest(compiled_repository)
    metadata = manifest.sessions.get(anchor.session_id)
    if metadata is None:
        raise KeyError(anchor.session_id)

    artifact_path = compiled_repository.root / metadata.artifact_relpath
    session_payload = _load_session_payload(artifact_path)
    blocks = session_payload["blocks"]

    focus_index = next((index for index, block in enumerate(blocks) if block["block_id"] == anchor.block_id), None)
    if focus_index is None:
        raise KeyError(anchor.block_id)

    start = max(0, focus_index - max(0, before))
    end = min(len(blocks), focus_index + max(0, after) + 1)
    context_blocks = tuple(
        ShowBlock(
            session_id=anchor.session_id,
            block_id=str(block["block_id"]),
            block_type=str(block["block_type"]),
            title=str(block["title"]),
            display_text=_show_display_text(block=block, full_text=full_text),
        )
        for block in blocks[start:end]
    )

    return ShowResult(anchor=anchor, focus_block_id=anchor.block_id, blocks=context_blocks)


def show_session_compiled_view(
    repository: CompiledRepository | str | Path,
    session_id: str,
    *,
    full_text: bool = False,
) -> ShowResult:
    compiled_repository = _coerce_repository(repository)
    manifest = load_repository_manifest(compiled_repository)
    metadata = manifest.sessions.get(session_id)
    if metadata is None:
        raise KeyError(session_id)

    artifact_path = compiled_repository.root / metadata.artifact_relpath
    session_payload = _load_session_payload(artifact_path)
    blocks = tuple(
        ShowBlock(
            session_id=session_id,
            block_id=str(block["block_id"]),
            block_type=str(block["block_type"]),
            title=str(block["title"]),
            display_text=_show_display_text(block=block, full_text=full_text),
        )
        for block in session_payload["blocks"]
    )
    focus_block_id = str(blocks[0].block_id) if blocks else ""
    return ShowResult(anchor=SearchAnchor(session_id=session_id, block_id=focus_block_id), focus_block_id=focus_block_id, blocks=blocks)


def _build_match_text(*, block: dict[str, Any], pattern: re.Pattern[str]) -> str:
    block_type = str(block["block_type"])
    if block_type == "tool_result":
        return _tool_result_window(str(block.get("display_text", "")), pattern=pattern)
    if block_type == "tool_call":
        return _tool_call_window(str(block.get("display_text", "")), pattern=pattern)
    return _text_match_window(str(block.get("display_text", "")), pattern)


def _tool_result_window(text: str, *, pattern: re.Pattern[str]) -> str:
    lines = text.splitlines()
    matching_indexes = [index for index, line in enumerate(lines) if pattern.search(line)]
    if not matching_indexes:
        return _limit_chars(text, TOOL_RESULT_MATCH_WINDOW_CHARS)

    line_index = matching_indexes[0]
    line_start = max(0, line_index - TOOL_RESULT_MATCH_WINDOW_LINES)
    line_end = min(len(lines), line_index + TOOL_RESULT_MATCH_WINDOW_LINES + 1)
    line_window = "\n".join(lines[line_start:line_end])

    absolute_match = pattern.search(text)
    if absolute_match is None:
        return line_window

    char_start = max(0, absolute_match.start() - TOOL_RESULT_MATCH_WINDOW_CHARS)
    char_end = min(len(text), absolute_match.end() + TOOL_RESULT_MATCH_WINDOW_CHARS)
    char_window = text[char_start:char_end]

    if len(char_window) < len(line_window):
        return char_window.strip()
    return line_window.strip()


def _tool_call_window(text: str, *, pattern: re.Pattern[str]) -> str:
    match = pattern.search(text)
    if match is None:
        return _limit_chars(text, DEFAULT_TEXT_MATCH_MAX_CHARS)
    return _char_window(text, match.start(), match.end(), DEFAULT_TEXT_MATCH_MAX_CHARS)


def _text_match_window(text: str, pattern: re.Pattern[str]) -> str:
    match = pattern.search(text)
    if match is None:
        return _limit_chars(text, DEFAULT_TEXT_MATCH_MAX_CHARS)
    return _char_window(text, match.start(), match.end(), DEFAULT_TEXT_MATCH_MAX_CHARS)


def _first_matching_line(text: str, pattern: re.Pattern[str]) -> str:
    for line in text.splitlines():
        if pattern.search(line):
            return line.strip()
    return text.strip().splitlines()[0] if text.strip() else ""


def _limit_chars(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text.strip()
    return text[: max_chars - 1].rstrip() + "…"


def _char_window(text: str, start: int, end: int, max_chars: int) -> str:
    window_start = max(0, start - max_chars)
    window_end = min(len(text), end + max_chars)
    return text[window_start:window_end].strip()


def _load_session_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_repository(repository: CompiledRepository | str | Path) -> CompiledRepository:
    if isinstance(repository, CompiledRepository):
        return repository
    return open_compiled_repository(repository)


def normalize_block_type_filters(values: list[str] | tuple[str, ...] | None) -> set[str] | None:
    if not values:
        return None
    normalized: set[str] = set()
    for value in values:
        alias = value.strip().lower()
        if alias in BLOCK_FILTER_ALIASES:
            normalized.update(BLOCK_FILTER_ALIASES[alias])
            continue
        normalized.add(alias)
    return normalized


def _show_display_text(*, block: dict[str, Any], full_text: bool) -> str:
    display_text = str(block.get("display_text", ""))
    if full_text:
        return display_text
    return _limit_chars(display_text, DEFAULT_TEXT_SHOW_MAX_CHARS)


def _compile_search_pattern(query: str, *, use_regex: bool) -> re.Pattern[str]:
    flags = re.IGNORECASE | re.DOTALL
    if use_regex:
        return re.compile(query, flags)
    return re.compile(re.escape(query), flags)


def _score_block_match(*, search_text: str, queries: tuple[str, ...], patterns: list[re.Pattern[str]], use_regex: bool) -> int:
    score = 0
    if use_regex:
        for pattern in patterns:
            if pattern.search(search_text):
                score += 1
        return score

    lowered = search_text.lower()
    
    for query in queries:
        lowered_query = query.lower().strip()
        if lowered_query and lowered_query in lowered:
            score += 4

        terms = [term for term in re.split(r"\s+", lowered_query) if term]
        if len(terms) > 1:
            score += sum(1 for term in set(terms) if term in lowered)
        else:
            score += 1
    return score


def _metadata_to_summary(*, session_id: str, metadata: Any) -> Any:
    from .models import HistorySessionSummary

    return HistorySessionSummary(
        id=session_id,
        project_id="",
        workspace_id=None,
        parent_id=None,
        slug="",
        directory=str(metadata.directory),
        title="",
        version="",
        share_url=None,
        time_created=metadata.effective_time,
        time_updated=metadata.fingerprint.session_time_updated,
        time_archived=None,
        time_compacting=None,
        message_count=metadata.fingerprint.message_count,
        last_message_created=metadata.fingerprint.last_message_created,
    )
