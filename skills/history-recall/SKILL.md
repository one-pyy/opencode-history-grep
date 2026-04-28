---
name: history-recall
description: Use this skill when a user refers to something done in the past, the current docs / knowledge database do not already answer it, or the user explicitly asks to search history.
---

# history-recall

Use `opencode-history-grep` to query `opencode` history.

## When to use

Use this skill only in these cases:

1. The user refers to something done in the past, but the current `docs/` and `knowledge_database/` do not contain enough information.
2. The user explicitly asks to search history.

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

## How type filters work

`--type` is repeatable.

- `user`
- `assistant` or `ai`
- `tool_call`
- `tool_result`
- `tool` = `tool_call + tool_result`
- `message` = `user + assistant`

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
opencode-history-grep show --session <session-id> --anchor <block-id> --before 5 --after 5
```

### Scenario 10: read a whole session (recommended first)

Use when you already know the session id and want the whole compiled session, but do **not** want to immediately expand every long text or tool output.

```bash
opencode-history-grep show --session <session-id> --all
```

### Scenario 10b: read complete raw content for selected blocks

Use this when `show --all --type all --full-text` still shows a summarized tool result and you need the full raw tool output for a known block.

```bash
opencode-history-grep show --session <session-id> --block <block-id>,<block-id-or-index>
```

### Scenario 11: read a whole session with full text (use carefully)

Use this only when the default truncated view is not enough and you explicitly need long raw block content.

```bash
opencode-history-grep show --session <session-id> --all --full-text
```

Warning: `--full-text` can expand very long text and tool output, making results much longer and harder to skim. Prefer not to use it unless necessary.

### Scenario 12: audit AI behavior

Use when you want to review another AI's execution process. You can pass the `session-id` and have another AI review its steps, logic, and tool usage to see if it made any errors.

```bash
opencode-history-grep show --session <session-id> --all --full-text
```

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
