# VCC Baseline Vendor Notes

## Purpose

This directory vendors the **minimum VCC baseline** needed for `opencode-history-grep` to treat VCC as a concrete upstream reference rather than an abstract inspiration.

The goal is **not** to run VCC in place.
The goal is to preserve the exact upstream baseline files we intend to study, compare against, and selectively adapt.

## Source

Vendored from local clone:

- `/root/_/opencode/VCC/README.md`
- `/root/_/opencode/VCC/INSTALL.md`
- `/root/_/opencode/VCC/skills/conversation-compiler/SKILL.md`
- `/root/_/opencode/VCC/skills/conversation-compiler/scripts/VCC.py`

These files are copied here as a baseline snapshot for this project.

## Why these files

We intentionally vendor only the smallest currently relevant subset:

- `README.md`
  - defines VCC's product goal, view types, and user-visible search behavior
- `INSTALL.md`
  - preserves the original host/runtime assumptions so we can explicitly contrast them with our own
- `skills/conversation-compiler/SKILL.md`
  - captures VCC's compile/search workflow and output contracts
- `skills/conversation-compiler/scripts/VCC.py`
  - captures the real compiler baseline, including parse/clean/lower/emit behavior

We do **not** vendor the rest of the repo yet because the current project decisions only require the compiler baseline, not the full Claude-specific skill package.

## What this baseline is for

This baseline is used for:

1. comparing our compiler design against VCC's actual implementation
2. identifying which behaviors we preserve
3. identifying which layers we must rewrite for opencode upstream
4. making code review concrete when we later say "this behavior comes from VCC baseline"

## What stays baseline-only

The following assumptions remain **upstream baseline behavior**, not project behavior:

- Claude JSONL input
- `.claude/skills` hosting model
- Claude-specific `/readchat`, `/searchchat`, `/recall` command semantics

These are preserved here to document the upstream shape, but they are **not** our target runtime model.

## What our project will change

The current planned adaptation points are:

1. input layer: Claude JSONL → opencode upstream SQLite
2. host layer: Claude skills → Python core library + CLI shell
3. block rules: no standalone reasoning block
4. tool result display: keep call params by default, truncate result output by default
5. repository layer: per-file immediate outputs → full-session compiled repository

## Modification rule

Default rule:

- Keep these vendored files as an upstream baseline snapshot.
- Do **not** edit them casually.

If we later need to adapt code derived from `VCC.py`, prefer one of these approaches:

1. copy the needed logic into project-owned modules under `src/opencode_history_grep/`
2. document the derivation in project docs

Avoid silently mutating the vendored baseline in place unless we explicitly decide to maintain a forked copy here.
