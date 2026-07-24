---
name: history-recall
description: MUST USE when reviewing a current or historical OpenCode session by session_id, including Oracle independent review and session-audit workflows; also use it when the user explicitly asks to search OpenCode history or refers to prior local/OpenCode work that current docs / knowledge_database do not answer.
---

# history-recall

Use `opencode-history-grep` to query `opencode` history.

## When to use

Use this skill only in these local-history cases:

1. The user refers to prior local/OpenCode work, but the current `docs/` and `knowledge_database/` do not contain enough information.
2. The user explicitly asks to search OpenCode history.
3. A reviewer receives a target `session_id`, session boundary, or audit task and needs session evidence.

Generic search wording such as “检索”, “搜索”, or “查找资料” should route to web/external search unless the user clearly points to prior local work.

Before searching history, first check the relevant `docs/` and `knowledge_database/` indexes and linked entries. Use `opencode-history-grep` only when those maintained documents do not answer the question or the user specifically needs original historical context.

`system` is not part of the history search domain.

## Remember these defaults

- Daily recall usually starts with `grep`.
- `grep` and `show` automatically compile / refresh history, so manual `compile` is usually unnecessary.
- Default upstream SQLite: `/root/.local/share/opencode/opencode.db`
- Default compiled repository: `/root/.local/share/opencode-history-grep`
- Default results are paginated: 10 per page, with `page a/b`
- Result lists are meant to be judged by `match`, not by a generated summary.
- Current `grep` is text matching, not semantic retrieval.

## Parameter quick reference

### `grep`

- `--query`: the search expression; repeatable
- `--regex`: interpret `--query` as regex; supports cross-line matching
- `--logic`: how multiple `--query` parameters combine (`and` or `or`, default is `or`)
- `--type`: filter by block type; repeatable
- `--directory`: filter by session working directory; it matches the directory itself or any child directory with that path as a prefix
- `--since` / `--until`: filter by time window
- `--page`: switch pages
- `--page-size`: change page size

### `show`

- automatically compiles / refreshes history before reading compiled sessions
- `--session`: session id
- `--anchor`: anchor from a grep hit
- `--before` / `--after`: how many blocks to show around an anchor
- `--all`: show a whole compiled session
- `--block`: show complete raw content for one or more compiled block ids or zero-based block indexes; comma-separated values are allowed. This uses compiled history for location, then reads upstream SQLite so long tool output is not limited by compile-time summaries.
- `--full-text`: do not truncate long text or tool output
- `--from` / `--to`: when combined with `--all`, restrict the view to inclusive block ids, zero-based block indexes, or quoted `text:<literal>` endpoints that uniquely match one block after `--type` filtering

## Session review contract

When this skill is loaded for Oracle review or session audit, `opencode-history-grep` is the evidence path. If the target session id is already known, start with `show`; do not rediscover it through broad listing or search.

The caller may provide:

- a source boundary: the accepted requirement, plan, docs, or boundary block that defines what the reviewer may use for an independent reference
- an execution boundary: the last task-execution block that may be inspected during candidate comparison
- a unique marker or exact excerpt that can be passed directly as a quoted `text:<literal>` endpoint

`current_session_id` returns a caller-local `session_id`, bare `message_id`, and unique `boundary_marker`. Use the provided values directly:

```bash
session_id='<provided session_id>'
boundary_marker='<provided boundary_marker>'
opencode-history-grep show --session "$session_id" --all --type 'all' --to "text:$boundary_marker" --full-text
```

`text:` matching is case-sensitive, literal, and runs after `--type` filtering. It succeeds only when exactly one filtered block contains the literal; zero or multiple matches fail explicitly. The marker lives in a tool-result block, so use it only with `--type 'all'` or another filter that retains tool results. For a user-only source window, use quoted `text:` excerpts from the target user blocks. If an excerpt is not unique, use `grep` to inspect candidates and pass the selected full block id instead.

For Oracle Session Phase 1, each source-start/source-boundary excerpt must contain at least 20 characters, or the entire source input when it is shorter. Use the bounded union of `--type user --type assistant`: user includes ordinary user text and completed `question` decisions, while assistant text supplies approval context but becomes authoritative only through explicit user acceptance. Accepted source artifacts are provided separately by exact path, accepted ref or block, and acceptance evidence. Do not broadly admit tool history; use a targeted write block only when an accepted artifact cannot be recovered from its exact accepted version.

For a two-phase `candidate` review:

1. Phase 1 reads only through the source boundary and returns an independent reference before candidate comparison.
2. Phase 2 continues the same reviewer session, reads the bounded execution range and candidate artifacts supplied by the caller, then compares them.

If the source boundary is a normal user or assistant message block, a message-only bounded view is appropriate. If the boundary is a tool-result marker, use an all-block bounded view so the endpoint remains present. Do not guess an endpoint that cannot be located.

For Oracle `session` mode, reconstruct the effective contract before reading execution evidence:

1. Read the target task's bounded user+assistant window:
   ```bash
   session_id='<provided session_id>'
   opencode-history-grep show --session "$session_id" --all --type 'user' --type 'assistant' --from 'text:<exact unique first user requirement>' --to 'text:<exact unique final authorization>' --full-text
   ```
2. Use the bounded assistant messages to identify what the user approved, amended, or rejected; do not treat unaccepted assistant content as authority. Answered `question` decisions are already present in the user view.
3. Read accepted source artifacts from their exact path and accepted ref/block, verify the supplied acceptance evidence, and build the effective contract from still-active requirements, later amendments, accepted artifacts, non-goals, and superseded requirements.
4. In the same Oracle session, read Phase 2 execution evidence:
   ```bash
   session_id='<provided session_id>'
   boundary_marker='<provided boundary_marker>'
   opencode-history-grep show --session "$session_id" --all --type 'all' --from 'text:<exact unique execution start>' --to "text:$boundary_marker" --full-text
   ```
5. Use `--block` only for exact raw recovery after the bounded full-text pass.

`--type user` returns ordinary user text plus completed `question` decisions. `--type assistant` returns the visible text from each assistant message, combining that message's text parts in creation order into one block; reasoning, system parts, tool calls, and tool results remain excluded. The combined block does not preserve interleaving between text and tools. In Session Phase 1, unaccepted assistant self-reports and conclusions remain context, not source authority.

For retrospective review without a pre-recorded marker, use a distinctive existing message excerpt or caller-provided block id. If no clean pre-candidate boundary exists, state that the review is candidate-exposed instead of claiming blind independence.

## How type filters work

`--type` is repeatable.

- `user`
- `assistant` or `ai`
- `tool_call`
- `tool_result`
- `tool` = `tool_call + tool_result`
- `message` = `user + assistant`

`user` includes completed `question` decisions. `message` includes those decisions through `user`; `tool_result` and `tool` also retain them for tool-oriented review.

Task-oriented interpretation:

- original requirements → `--type user`
- explanations / conclusions → `--type assistant`
- commands / arguments used before → `--type tool_call`
- tool output / errors → `--type tool_result`

Recommended defaults:

- prefer `--type user`
- prefer `--type assistant`

Only use tool-related filters when the user is clearly asking about command arguments, tool output, or errors.

## How parameter combinations work

Different filter dimensions should be read as **AND**:

- `--directory` + `--since/--until` means the same session must satisfy both directory and time constraints.
- `--type` + `--query` means returned results must both belong to the allowed type range and match the query.

## Directory filtering guidance

- Use `--directory` when the project path is clear and you want sessions from that project tree.
- `--directory /a/b` matches sessions whose working directory is exactly `/a/b` or is under `/a/b/...`.
- If the project path is unclear, do **not** guess a directory filter. Reason: a wrong `--directory` can hide the relevant history completely.

## Query wording guidance

- `grep` is text matching, so wording matters.
- If the first search misses, try nearby phrasings, common synonyms, and alternative keyword combinations instead of only changing filters.
- If the user is clearly communicating in English, search English first.
- If there are signs the earlier work may have used Chinese, also try Chinese and English variants.
- If results are too broad, then narrow with `--type`, `--since/--until`, `--directory`, or a tighter `--regex`.

### Multiple `--query` parameters

You can provide multiple `--query` parameters. How they combine depends on `--logic`:

- `--logic or` (default): results are sorted by how many queries they match.
- `--logic and`: only keeps results from sessions that match **all** provided queries somewhere in the session.

Do **not** split query words with spaces if you want an AND search across the session. Instead, pass multiple `--query` flags:

```bash
# Correct session-level AND
opencode-history-grep grep --query "sqlite" --query "history" --logic and
```

### Multiple `--type` parameters

- `--type user --type tool`

means both `user` and `tool` results are allowed into the result set.

If matches from these types appear in the same session, they can appear separately in the results. This does **not** mean one block must be both `user` and `tool` at the same time.

## Scenario examples

### Scenario 1: find earlier explanations or conclusions in a project

Use when the user asks things like “why did we do this before?” or “did we discuss this plan last time?”

Only add `--directory` if the project path is actually known.

```bash
opencode-history-grep grep --regex --directory /root/_/opencode --type assistant --query "sqlite.*history|history.*sqlite"
```

### Scenario 2: find original requirement wording

Use when the user wants the exact earlier phrasing of a request.

```bash
opencode-history-grep grep --regex --type user --query "dark\s+mode|theme\s+toggle"
```

### Scenario 3: find history in a time window

Use when the user says “last week”, “early April”, or another bounded time range.

```bash
opencode-history-grep grep --regex --since 2026-04-01 --until 2026-04-23 --type assistant --query "migration|knowledge[_ -]?database"
```

### Scenario 4: find earlier commands or argument usage

Use when the user asks “did we run this before?” or “what flag did we use last time?”

```bash
opencode-history-grep grep --regex --type tool_call --query "uv\s+tool\s+install|--editable|--page-size"
```

### Scenario 5: find tool output or an error

Use when the user is explicitly looking for an error, tool output, or a multi-line trace.

```bash
opencode-history-grep grep --regex --type tool_result --query "line before\nneedle match|ModuleNotFoundError|Invalid time filter"
```

### Scenario 6: combine filters to narrow a wide search

Use when the first search returns too much and you need to constrain both “who said it” and “what kind of action it was”.

```bash
opencode-history-grep grep --type message --type tool_call --query "history grep" --query "show" --logic or
```

Here `message` and `tool_call` form the allowed type range together. Any matching block from those types can appear if it also satisfies the other filters.

### Scenario 7: require multiple terms in the same session

Use when you want to find a session discussing two specific concepts, even if they appear in different blocks.

```bash
opencode-history-grep grep --query "sqlite" --query "compilation" --logic and
```

### Scenario 8: move to the next page

Use when the result set is broad and you need the next page.

```bash
opencode-history-grep grep --regex --query "history|grep" --page 2
```

### Scenario 9: reopen context around a hit

Use when you already have a hit with `session` and `anchor`.

```bash
session_id='<provided session_id>'
opencode-history-grep show --session "$session_id" --anchor '<block-id>' --before 5 --after 5
```

### Scenario 10: read a whole session (recommended first)

Use when you already know the session id and want the whole compiled session, but do **not** want to immediately expand every long text or tool output.

```bash
session_id='<provided session_id>'
opencode-history-grep show --session "$session_id" --all
```

### Scenario 10b: read complete raw content for selected blocks

Use this when `show --all --type all --full-text` still shows a summarized tool result and you need the full raw tool output for a known block.

```bash
session_id='<provided session_id>'
opencode-history-grep show --session "$session_id" --block '<block-id>,<block-id-or-index>'
```

### Scenario 11: read a whole session with full text (use carefully)

Use this only when the default truncated view is not enough and you explicitly need long raw block content.

```bash
session_id='<provided session_id>'
opencode-history-grep show --session "$session_id" --all --full-text
```

Warning: `--full-text` can expand very long text and tool output, making results much longer and harder to skim. Prefer not to use it unless necessary.

### Scenario 12: audit AI behavior

Use when you want to review another AI's execution process. You can pass the `session-id` and have another AI review its steps, logic, and tool usage to see if it made any errors.

```bash
session_id='<provided session_id>'
opencode-history-grep show --session "$session_id" --all --full-text
```

For an Oracle session review, follow the separately loaded `audit-session` mode protocol and its role-filtered source boundary. For an Oracle candidate review, use the source and execution boundaries supplied by the caller rather than opening the whole session before Phase 1 concludes.

## How to narrow wide results

Prefer these moves first:

- add `--type assistant`
- or switch to `--type user`
- add `--since/--until`
- add `--directory` only when the project path is clear
- write a tighter regex
- try nearby wording, synonyms, and Chinese / English variants when the first query misses

Do not immediately open many `show` commands.

## How to read results

`grep` returns block-level hits:

- `session=<...>`: the matched session
- `anchor=<...>`: reusable with `show`
- `match:`: the matched snippet

For `tool_result`, `match` is a local window, not the full raw output.

## Never do these

- Do not fall back to plain text grep. Reason: it does not know block boundaries and cannot jump back by anchor.
- Do not treat `show` as a search command. Reason: it needs either a known `session` / `anchor` or a whole-session view.
- Do not interpret directory filtering as file-content filtering. Reason: it filters session working directories.
- Do not interpret time filtering as single-message trimming. Reason: it filters session scope.
- Do not substitute a formatted session summary for the `opencode-history-grep` evidence path when this skill was loaded for review. Reason: bounded block views and raw block recovery are part of the review contract.
