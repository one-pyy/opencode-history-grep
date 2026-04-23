"""opencode-history-grep package."""

from .compiler import CompiledAnchor, CompiledBlock, CompiledSessionView, compile_session_full_view
from .models import HistoryDatabase, HistoryMessage, HistoryPart, HistorySession, HistorySessionSummary
from .repository import (
    CompiledRepository,
    FullCompileResult,
    RepositoryManifest,
    SessionArtifactMetadata,
    SessionCompileFingerprint,
    compile_all_sessions,
    load_repository_manifest,
    open_compiled_repository,
    select_sessions_for_recompile,
    write_compiled_session,
)
from .reader import HistoryReader, SessionNotFoundError, open_history_database
from .search_show import SearchAnchor, SearchResult, ShowBlock, ShowResult, search_compiled_repository, show_compiled_context

__all__ = [
    "CompiledAnchor",
    "CompiledBlock",
    "CompiledRepository",
    "CompiledSessionView",
    "FullCompileResult",
    "HistoryDatabase",
    "HistoryMessage",
    "HistoryPart",
    "HistoryReader",
    "HistorySession",
    "HistorySessionSummary",
    "RepositoryManifest",
    "SearchAnchor",
    "SearchResult",
    "SessionNotFoundError",
    "SessionArtifactMetadata",
    "SessionCompileFingerprint",
    "ShowBlock",
    "ShowResult",
    "compile_all_sessions",
    "compile_session_full_view",
    "load_repository_manifest",
    "open_compiled_repository",
    "open_history_database",
    "search_compiled_repository",
    "select_sessions_for_recompile",
    "show_compiled_context",
    "write_compiled_session",
]
