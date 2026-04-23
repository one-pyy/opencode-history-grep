from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

JSONMapping = Mapping[str, Any]


def _freeze_mapping(value: Mapping[str, Any]) -> JSONMapping:
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class HistoryPart:
    id: str
    session_id: str
    message_id: str
    kind: str
    time_created: int
    time_updated: int
    data: JSONMapping

    @classmethod
    def from_row_data(
        cls,
        *,
        part_id: str,
        session_id: str,
        message_id: str,
        time_created: int,
        time_updated: int,
        data: Mapping[str, Any],
    ) -> HistoryPart:
        return cls(
            id=part_id,
            session_id=session_id,
            message_id=message_id,
            kind=str(data["type"]),
            time_created=time_created,
            time_updated=time_updated,
            data=_freeze_mapping(data),
        )


@dataclass(frozen=True, slots=True)
class HistoryMessage:
    id: str
    session_id: str
    role: str
    time_created: int
    time_updated: int
    data: JSONMapping
    parts: tuple[HistoryPart, ...]

    @classmethod
    def from_row_data(
        cls,
        *,
        message_id: str,
        session_id: str,
        time_created: int,
        time_updated: int,
        data: Mapping[str, Any],
        parts: tuple[HistoryPart, ...],
    ) -> HistoryMessage:
        return cls(
            id=message_id,
            session_id=session_id,
            role=str(data["role"]),
            time_created=time_created,
            time_updated=time_updated,
            data=_freeze_mapping(data),
            parts=parts,
        )


@dataclass(frozen=True, slots=True)
class HistorySessionSummary:
    id: str
    project_id: str
    workspace_id: str | None
    parent_id: str | None
    slug: str
    directory: str
    title: str
    version: str
    share_url: str | None
    time_created: int
    time_updated: int
    time_archived: int | None
    time_compacting: int | None
    message_count: int
    last_message_created: int | None

    @property
    def effective_time(self) -> int:
        if self.last_message_created is not None:
            return self.last_message_created
        return self.time_updated


@dataclass(frozen=True, slots=True)
class HistorySession:
    id: str
    project_id: str
    workspace_id: str | None
    parent_id: str | None
    slug: str
    directory: str
    title: str
    version: str
    share_url: str | None
    time_created: int
    time_updated: int
    time_archived: int | None
    time_compacting: int | None
    messages: tuple[HistoryMessage, ...]

    @property
    def message_count(self) -> int:
        return len(self.messages)


@dataclass(frozen=True, slots=True)
class HistoryDatabase:
    path: Path
