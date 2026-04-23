from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Literal

from .models import HistoryMessage, HistoryPart, HistorySession

BlockType = Literal[
    "user_text",
    "assistant_text",
    "tool_call",
    "tool_result",
    "compaction",
    "subtask",
]

BlockRole = Literal["user", "assistant", "tool"]

TOOL_RESULT_SUMMARY_MAX_LINES = 8
TOOL_RESULT_SUMMARY_MAX_CHARS = 500


@dataclass(frozen=True, slots=True)
class CompiledAnchor:
    session_id: str
    message_id: str
    part_id: str | None
    block_id: str
    ordinal: int


@dataclass(frozen=True, slots=True)
class CompiledBlock:
    session_id: str
    message_id: str
    part_id: str | None
    block_id: str
    role: BlockRole
    block_type: BlockType
    title: str
    summary: str
    search_text: str
    display_text: str
    anchors: tuple[CompiledAnchor, ...]
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CompiledSessionView:
    session_id: str
    blocks: tuple[CompiledBlock, ...]


def compile_session_full_view(session: HistorySession) -> CompiledSessionView:
    blocks: list[CompiledBlock] = []
    ordinal = 0

    for message in session.messages:
        message_text = _collect_message_text(message)
        if message_text:
            blocks.append(
                _build_text_block(
                    session_id=session.id,
                    message=message,
                    ordinal=ordinal,
                    text=message_text,
                )
            )
            ordinal += 1

        ordered_parts = sorted(message.parts, key=lambda part: (part.time_created, part.id))
        for part in ordered_parts:
            block = _compile_part(session_id=session.id, message=message, part=part, ordinal=ordinal)
            if block is None:
                continue
            blocks.append(block)
            ordinal += 1

    return CompiledSessionView(session_id=session.id, blocks=tuple(blocks))


def _compile_part(*, session_id: str, message: HistoryMessage, part: HistoryPart, ordinal: int) -> CompiledBlock | None:
    if part.kind == "text":
        return None
    if part.kind == "reasoning":
        return None
    if part.kind == "system":
        return None
    if part.kind == "tool":
        return _build_tool_blocks(session_id=session_id, message=message, part=part, ordinal=ordinal)
    if part.kind == "compaction":
        return _build_compaction_block(session_id=session_id, message=message, part=part, ordinal=ordinal)
    if part.kind == "subtask":
        return _build_subtask_block(session_id=session_id, message=message, part=part, ordinal=ordinal)
    return None


def _build_text_block(*, session_id: str, message: HistoryMessage, ordinal: int, text: str) -> CompiledBlock:
    block_type: BlockType = "user_text" if message.role == "user" else "assistant_text"
    title = "User text" if message.role == "user" else "Assistant text"
    summary = _first_line(text)
    return _make_block(
        session_id=session_id,
        message_id=message.id,
        part_id=None,
        ordinal=ordinal,
        role=message.role if message.role in ("user", "assistant") else "assistant",
        block_type=block_type,
        title=title,
        summary=summary,
        search_text=text,
        display_text=text,
        metadata={"message_role": message.role},
    )


def _build_tool_blocks(*, session_id: str, message: HistoryMessage, part: HistoryPart, ordinal: int) -> CompiledBlock:
    tool_name = str(part.data.get("tool", "unknown"))
    state = part.data.get("state")
    if not isinstance(state, Mapping):
        state = {}

    status = str(state.get("status", "unknown"))
    tool_input = state.get("input")
    rendered_input = _render_mapping(tool_input) if isinstance(tool_input, Mapping) else ""
    output_summary = _summarize_tool_result(state)

    if status in {"completed", "error"}:
        block_type: BlockType = "tool_result"
        title = f"Tool result · {tool_name}"
        summary = _first_line(output_summary) or f"{tool_name} {status}"
        search_text = "\n".join(part for part in [tool_name, rendered_input, output_summary] if part)
        display_lines = [f"tool: {tool_name}", f"status: {status}"]
        if output_summary:
            display_lines.extend(["", output_summary])
        display_text = "\n".join(display_lines)
    else:
        block_type = "tool_call"
        title = f"Tool call · {tool_name}"
        summary = f"{tool_name} call"
        search_text = "\n".join(part for part in [tool_name, rendered_input] if part)
        display_lines = [f"tool: {tool_name}"]
        if rendered_input:
            display_lines.extend(["", rendered_input])
        display_text = "\n".join(display_lines)

    return _make_block(
        session_id=session_id,
        message_id=message.id,
        part_id=part.id,
        ordinal=ordinal,
        role="tool",
        block_type=block_type,
        title=title,
        summary=summary,
        search_text=search_text,
        display_text=display_text,
        metadata={
            "message_role": message.role,
            "tool_name": tool_name,
            "tool_status": status,
            "tool_input": _freeze_mapping(tool_input) if isinstance(tool_input, Mapping) else MappingProxyType({}),
        },
    )


def _build_compaction_block(*, session_id: str, message: HistoryMessage, part: HistoryPart, ordinal: int) -> CompiledBlock:
    auto = bool(part.data.get("auto", False))
    overflow = bool(part.data.get("overflow", False))
    flags = ["auto" if auto else "manual"]
    if overflow:
        flags.append("overflow")
    body = ", ".join(flags)
    return _make_block(
        session_id=session_id,
        message_id=message.id,
        part_id=part.id,
        ordinal=ordinal,
        role="assistant",
        block_type="compaction",
        title="Compaction",
        summary=f"Compaction · {body}",
        search_text=f"compaction {body}",
        display_text=f"compaction: {body}",
        metadata={"message_role": message.role, "auto": auto, "overflow": overflow},
    )


def _build_subtask_block(*, session_id: str, message: HistoryMessage, part: HistoryPart, ordinal: int) -> CompiledBlock:
    agent = str(part.data.get("agent", "unknown"))
    description = str(part.data.get("description", "")).strip()
    prompt = str(part.data.get("prompt", "")).strip()
    summary = description or prompt or f"Subtask via {agent}"
    display_lines = [f"agent: {agent}"]
    if description:
        display_lines.extend(["", f"description: {description}"])
    if prompt:
        display_lines.extend(["", prompt])
    search_text = "\n".join(part for part in [agent, description, prompt] if part)
    return _make_block(
        session_id=session_id,
        message_id=message.id,
        part_id=part.id,
        ordinal=ordinal,
        role="assistant",
        block_type="subtask",
        title=f"Subtask · {agent}",
        summary=summary,
        search_text=search_text,
        display_text="\n".join(display_lines),
        metadata={"message_role": message.role, "agent": agent},
    )


def _make_block(
    *,
    session_id: str,
    message_id: str,
    part_id: str | None,
    ordinal: int,
    role: BlockRole,
    block_type: BlockType,
    title: str,
    summary: str,
    search_text: str,
    display_text: str,
    metadata: Mapping[str, Any],
) -> CompiledBlock:
    block_id = f"{message_id}:{ordinal:04d}"
    anchor = CompiledAnchor(
        session_id=session_id,
        message_id=message_id,
        part_id=part_id,
        block_id=block_id,
        ordinal=ordinal,
    )
    return CompiledBlock(
        session_id=session_id,
        message_id=message_id,
        part_id=part_id,
        block_id=block_id,
        role=role,
        block_type=block_type,
        title=title,
        summary=summary,
        search_text=search_text,
        display_text=display_text,
        anchors=(anchor,),
        metadata=_freeze_mapping(metadata),
    )


def _collect_message_text(message: HistoryMessage) -> str:
    chunks: list[str] = []
    for part in message.parts:
        if part.kind != "text":
            continue
        if bool(part.data.get("ignored", False)):
            continue
        text = str(part.data.get("text", "")).strip()
        if text:
            chunks.append(_sanitize_text(text))
    return "\n\n".join(chunks)


def _summarize_tool_result(state: Mapping[str, Any]) -> str:
    if "error" in state and isinstance(state.get("error"), str):
        return _sanitize_text(str(state["error"]))

    output = state.get("output")
    if isinstance(output, str):
        return _limit_text(_sanitize_text(output))
    if isinstance(output, Mapping):
        return _limit_text(_render_mapping(output))
    if isinstance(output, list):
        pieces = [_sanitize_text(str(item)) for item in output if str(item).strip()]
        return _limit_text("\n".join(pieces))
    return ""


def _render_mapping(mapping: Mapping[str, Any]) -> str:
    lines: list[str] = []
    for key, value in mapping.items():
        lines.extend(_render_mapping_item(key=key, value=value, indent=0))
    return "\n".join(lines)


def _render_mapping_item(*, key: str, value: Any, indent: int) -> list[str]:
    prefix = " " * indent
    if isinstance(value, Mapping):
        lines = [f"{prefix}{key}:"]
        for nested_key, nested_value in value.items():
            lines.extend(_render_mapping_item(key=str(nested_key), value=nested_value, indent=indent + 2))
        return lines
    if isinstance(value, list):
        lines = [f"{prefix}{key}:"]
        for item in value:
            if isinstance(item, Mapping):
                lines.append(f"{prefix}  -")
                for nested_key, nested_value in item.items():
                    lines.extend(_render_mapping_item(key=str(nested_key), value=nested_value, indent=indent + 4))
            else:
                lines.append(f"{prefix}  - {item}")
        return lines

    text = str(value)
    if "\n" in text:
        lines = [f"{prefix}{key}: |"]
        for line in text.splitlines():
            lines.append(f"{' ' * (indent + 2)}{line}")
        return lines
    return [f"{prefix}{key}: {text}"]


def _limit_text(text: str) -> str:
    lines = text.splitlines()
    
    if len(lines) <= 10:
        if len(text) <= 1000:
            return text
        
        omitted_chars = len(text) - 1000
        return text[:500].rstrip() + f"\n... ({omitted_chars} chars omitted) ...\n" + text[-500:].lstrip()

    head_lines = lines[:5]
    head_text = "\n".join(head_lines)
    if len(head_text) > 500:
        head_text = head_text[:499].rstrip() + "…"

    tail_lines = lines[-5:]
    tail_text = "\n".join(tail_lines)
    if len(tail_text) > 500:
        tail_text = "…" + tail_text[-499:].lstrip()

    omitted_lines = len(lines) - 10
    return f"{head_text}\n... ({omitted_lines} lines omitted) ...\n{tail_text}"


def _sanitize_text(text: str) -> str:
    return text.replace("\r", "").replace("\x00", "").strip()


def _first_line(text: str) -> str:
    for line in text.splitlines():
        candidate = line.strip()
        if candidate:
            return candidate
    return ""


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))
