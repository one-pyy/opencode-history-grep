from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

from .compiler import CompiledBlock, CompiledSessionView, compile_session_full_view
from .models import HistorySessionSummary
from .reader import HistoryReader, SessionFilter

REPOSITORY_MANIFEST_VERSION = 1


@dataclass(frozen=True, slots=True)
class SessionCompileFingerprint:
    session_id: str
    session_time_updated: int
    message_count: int
    last_message_created: int | None


@dataclass(frozen=True, slots=True)
class SessionArtifactMetadata:
    session_id: str
    fingerprint: SessionCompileFingerprint
    block_count: int
    artifact_relpath: str
    directory: str
    effective_time: int


@dataclass(frozen=True, slots=True)
class RepositoryManifest:
    version: int
    sessions: dict[str, SessionArtifactMetadata]


@dataclass(frozen=True, slots=True)
class FullCompileResult:
    repository_path: Path
    compiled_session_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompiledRepository:
    root: Path

    @property
    def sessions_dir(self) -> Path:
        return self.root / "sessions"

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"


def open_compiled_repository(path: str | Path) -> CompiledRepository:
    return CompiledRepository(root=Path(path).expanduser().resolve())


def compile_all_sessions(
    reader: HistoryReader,
    repository: CompiledRepository | str | Path,
    *,
    session_filter: SessionFilter | None = None,
) -> FullCompileResult:
    compiled_repository = _coerce_repository(repository)
    _ensure_repository_dirs(compiled_repository)

    manifest = load_repository_manifest(compiled_repository)
    summaries = reader.list_sessions(session_filter)
    compiled_session_ids: list[str] = []
    filtered_session_ids = {summary.id for summary in summaries}
    next_sessions: dict[str, SessionArtifactMetadata] = {
        session_id: metadata
        for session_id, metadata in manifest.sessions.items()
        if session_id in filtered_session_ids
    }

    for summary in summaries:
        fingerprint = SessionCompileFingerprint(
            session_id=summary.id,
            session_time_updated=summary.time_updated,
            message_count=summary.message_count,
            last_message_created=summary.last_message_created,
        )
        existing = manifest.sessions.get(summary.id)
        if existing is not None and existing.fingerprint == fingerprint:
            next_sessions[summary.id] = existing
            continue

        session = reader.load_session(summary.id)
        compiled_view = compile_session_full_view(session)
        artifact_metadata = write_compiled_session(compiled_repository, compiled_view, summary)
        next_sessions[summary.id] = artifact_metadata
        compiled_session_ids.append(summary.id)

    next_manifest = RepositoryManifest(version=REPOSITORY_MANIFEST_VERSION, sessions=next_sessions)
    _write_json_atomically(compiled_repository.manifest_path, _manifest_to_json(next_manifest))
    return FullCompileResult(repository_path=compiled_repository.root, compiled_session_ids=tuple(compiled_session_ids))


def write_compiled_session(
    repository: CompiledRepository | str | Path,
    compiled_view: CompiledSessionView,
    session_summary: HistorySessionSummary,
) -> SessionArtifactMetadata:
    compiled_repository = _coerce_repository(repository)
    _ensure_repository_dirs(compiled_repository)

    session_dir = compiled_repository.sessions_dir / compiled_view.session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = session_dir / "full_view.json"

    payload = {
        "session_id": compiled_view.session_id,
        "blocks": [_block_to_json(block) for block in compiled_view.blocks],
    }
    _write_json_atomically(artifact_path, payload)

    fingerprint = SessionCompileFingerprint(
        session_id=compiled_view.session_id,
        session_time_updated=session_summary.time_updated,
        message_count=session_summary.message_count,
        last_message_created=session_summary.last_message_created,
    )
    return SessionArtifactMetadata(
        session_id=compiled_view.session_id,
        fingerprint=fingerprint,
        block_count=len(compiled_view.blocks),
        artifact_relpath=str(artifact_path.relative_to(compiled_repository.root)),
        directory=session_summary.directory,
        effective_time=session_summary.effective_time,
    )


def select_sessions_for_recompile(
    reader: HistoryReader,
    repository: CompiledRepository | str | Path,
    *,
    session_filter: SessionFilter | None = None,
) -> list[SessionCompileFingerprint]:
    compiled_repository = _coerce_repository(repository)
    manifest = load_repository_manifest(compiled_repository)
    candidates: list[SessionCompileFingerprint] = []

    for summary in reader.list_sessions(session_filter):
        fingerprint = SessionCompileFingerprint(
            session_id=summary.id,
            session_time_updated=summary.time_updated,
            message_count=summary.message_count,
            last_message_created=summary.last_message_created,
        )
        existing = manifest.sessions.get(summary.id)
        if existing is None:
            candidates.append(fingerprint)
            continue
        if existing.fingerprint != fingerprint:
            candidates.append(fingerprint)

    return candidates


def load_repository_manifest(repository: CompiledRepository | str | Path) -> RepositoryManifest:
    compiled_repository = _coerce_repository(repository)
    if not compiled_repository.manifest_path.exists():
        return RepositoryManifest(version=REPOSITORY_MANIFEST_VERSION, sessions={})

    raw_manifest = json.loads(compiled_repository.manifest_path.read_text(encoding="utf-8"))
    sessions: dict[str, SessionArtifactMetadata] = {}
    for session_id, payload in raw_manifest.get("sessions", {}).items():
        fingerprint_payload = payload["fingerprint"]
        sessions[session_id] = SessionArtifactMetadata(
            session_id=payload["session_id"],
            fingerprint=SessionCompileFingerprint(
                session_id=fingerprint_payload["session_id"],
                session_time_updated=fingerprint_payload["session_time_updated"],
                message_count=fingerprint_payload["message_count"],
                last_message_created=fingerprint_payload["last_message_created"],
            ),
            block_count=payload["block_count"],
            artifact_relpath=payload["artifact_relpath"],
            directory=payload.get("directory", ""),
            effective_time=payload.get("effective_time", fingerprint_payload["session_time_updated"]),
        )
    return RepositoryManifest(version=raw_manifest.get("version", REPOSITORY_MANIFEST_VERSION), sessions=sessions)


def _coerce_repository(repository: CompiledRepository | str | Path) -> CompiledRepository:
    if isinstance(repository, CompiledRepository):
        return repository
    return open_compiled_repository(repository)


def _ensure_repository_dirs(repository: CompiledRepository) -> None:
    repository.root.mkdir(parents=True, exist_ok=True)
    repository.sessions_dir.mkdir(parents=True, exist_ok=True)


def _manifest_to_json(manifest: RepositoryManifest) -> dict[str, Any]:
    return {
        "version": manifest.version,
        "sessions": {
            session_id: {
                "session_id": metadata.session_id,
                "fingerprint": asdict(metadata.fingerprint),
                "block_count": metadata.block_count,
                "artifact_relpath": metadata.artifact_relpath,
                "directory": metadata.directory,
                "effective_time": metadata.effective_time,
            }
            for session_id, metadata in sorted(manifest.sessions.items())
        },
    }


def _block_to_json(block: CompiledBlock) -> dict[str, Any]:
    return {
        "session_id": block.session_id,
        "message_id": block.message_id,
        "part_id": block.part_id,
        "block_id": block.block_id,
        "role": block.role,
        "block_type": block.block_type,
        "title": block.title,
        "summary": block.summary,
        "search_text": block.search_text,
        "display_text": block.display_text,
        "anchors": [asdict(anchor) for anchor in block.anchors],
        "metadata": _jsonify_value(dict(block.metadata)),
    }


def _write_json_atomically(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _jsonify_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonify_value(nested) for key, nested in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonify_value(item) for item in value]
    return value
