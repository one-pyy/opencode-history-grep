# Orchestrate Session Audit

---
name: orchestrate-session-audit
description: Orchestrate a full session-audit loop by discovering the target session_id, delegating audit-session to a reviewer, resuming interrupted reviewer work, reading the audit artifact, and deciding whether rectification can begin.
---

## Skill Definition

Activate this skill when you need to orchestrate a full session-audit loop: discover the target `session_id`, delegate the audit to a child reviewer, continue the same child session if it gets interrupted, read the produced audit artifact, and decide whether rectification can begin.

## Core Purpose

This is the **caller-side companion skill** for `audit-session`.

- `audit-session` defines how the delegated reviewer performs the audit.
- `orchestrate-session-audit` defines how the caller finds the session, launches the reviewer, resumes an interrupted reviewer, reads the audit artifact, and decides whether the artifact is usable.
- Audit artifacts live under `.sisyphus/tmp/audit/` and must be run-scoped, not session-scoped singleton files.
- The review flow uses `show --type message` first to reconstruct requirements and write the audit template, then `show --type all --full-text` to verify whether tool execution matched those requirements.

---

## Workflow

### 1. Discover the target session id

If the target `session_id` is not already known, discover it by grepping a distinctive long quote from that session.

- Recommended command:
  ```bash
  opencode-history-grep grep --query "<a distinctive exact user quote from the target session>" --type user --page-size 5
  ```
- If you are auditing your own current session, first choose a unique sentence from the user's request that triggered the audit, then run the recommended `grep --type user` command. Do not start with session-listing tools.
- If you do not know the `session_id` yet, run that exact-quote history grep first, then pass the discovered id into the audit workflow.
- If you already know the `session_id`, for example from a child agent task result, pass it directly and do not run a discovery grep first.
- This applies to auditing your own current session and to auditing another agent's session.
- Choose a quote long enough to avoid accidental matches. Prefer user wording over assistant wording because user text is the requirement anchor.
- Do not use `session_list`, `session_info`, or project/date listing to find the current session. Reason: project paths and date filters can miss the active session, while an exact user quote searches the same compiled history source used by the audit workflow.

### 2. Delegate the session audit

Once the `session_id` is known, delegate the actual audit to a review-capable child agent.

- Preferred child: `sisyphus-junior` with category `unspecified-high`. Reason: session auditing requires strict adherence to physical execution steps: fetching message-only history, fetching full tool history, building templates, then checking boxes. `sisyphus-junior` is better suited to disciplined execution than critique-only agents.
- Required skills for the child: `audit-session`, `history-recall`.
- Required prompt content: tell the child to execute the `audit-session` workflow for the target `session_id`; do not restate a conflicting audit procedure in the caller prompt.
- Preferred call shape:
  ```typescript
  task(
    category="unspecified-high",
    load_skills=["audit-session", "history-recall"],
    description="Audit session",
    prompt="Execute the audit-session workflow for session_id: [XXX]. Follow audit-session as the reviewer-side source of truth.",
    run_in_background=false
  )
  ```
- If `sisyphus-junior` cannot satisfy the needed tool contract in the current runtime, choose another disciplined executor that can read history and write/edit files.

### 3. If the child audit is interrupted, continue the same child session

If the delegated audit session aborts or stops mid-run, you MUST use the `continue-child-agent` workflow.

- Reuse the old child `session_id` directly.
- Do **not** spawn a fresh child if direct continuation is still possible.
- Preferred continuation shape:
  ```typescript
  task(
    session_id="<old child session id>",
    load_skills=["audit-session", "history-recall"],
    prompt="Continue the existing session-audit run and finish the workflow. Preserve the existing run-scoped audit artifact as the working artifact."
  )
  ```

Reason: continuing the same child preserves full local context and avoids forcing a new child to reconstruct partially completed audit work.

### 4. Read the produced audit file

The delegated child must return only the audit markdown file path. Read that file first.

- Expect a run-scoped artifact such as `.sisyphus/tmp/audit/audit_{session_id}.{run_id}.md`.
- Do not assume there is only one audit file per session.
- The audited agent must read this markdown artifact before attempting rectification. The path alone is not enough; rectification starts only after the audited agent has read the file contents and understood the abnormal annotations.
- If the audit file contains abnormal markers, each marker must include a concrete reason. If any marker is a bare `[异常]` without a cause, treat the reviewer output as incomplete and send the same child reviewer back to fix the artifact.

### 5. Inspect the child reviewer session only on artifact/process anomalies

After reading the audit result, do not routinely inspect the child reviewer session. The normal path is: accept a well-formed audit artifact as the handoff contract and move to rectification.

Inspect the child reviewer session only when there is a concrete anomaly, for example:

- the child did not return a run-scoped audit file path
- the returned file is missing or cannot be read
- the audit file contains bare `[异常]` markers without reasons
- the audit file has checked boxes in the initial template without evidence of second-pass verification
- the audit findings contradict the caller's known facts or omit an explicit audit focus
- the child was interrupted and continuation behavior needs verification

If such an anomaly exists, inspect the child reviewer session with this history-based discipline:

- Use the same history-based review discipline:
  - first load `history-recall` if it is not already loaded
  - if the child `session_id` is already known, start with `opencode-history-grep show --session <child-session-id> --all --type message`
  - then analyze the child reviewer's stated intent, phase boundaries, and whether it wrote the run-scoped audit template before judging tools
  - then run `opencode-history-grep show --session <child-session-id> --all --type all --full-text` before making any judgment
  - if the child `session_id` is not known, first use `opencode-history-grep grep` to locate it, then inspect it with the same message → template/intent → full-text sequence
  - if you only need to inspect operations after a known block, use `show --session <child-session-id> --all --type all --from <block-id-or-index> --full-text`; use `--to <block-id-or-index>` when the review window has a known endpoint
  - if a specific tool result or raw part may still be summarized, use `show --session <child-session-id> --block <block-id>,<block-id-or-index>` to read complete raw content from upstream SQLite through compiled block location
  - inspect whether it followed `audit-session`, especially whether it used the message-only pass for requirement/phase reconstruction, wrote the initial audit template before tool judgment, and used the full-text all-block pass for execution judgment
  - check whether it skipped deep dives, faked verification, guessed collapsed content, judged tools from message-only output, or drifted from the path-only output contract
- Do not insert a truncated `show --session <child-session-id> --all --type all` overview between the message pass and full-text pass. Reason: reviewer-process judgment should follow the same current audit discipline: preserve message-level intent first, then judge from full-text evidence.
- If the child session was interrupted and later continued, audit the continued session chain as one logical reviewer run.
- Treat the child's execution history as anomaly evidence, not as a mandatory second audit layer. Reason: routine self-auditing of every reviewer run creates recursive overhead and distracts from rectifying the audited session.

### 5.1 Compression boundary after audit-artifact acceptance

After the audit artifact has been read and accepted as usable, compression is allowed only if all durable handoff facts already exist outside the soon-to-be-compressed history:

- the produced audit file path has been read and stated or written into the current working context
- the rectification goals are available from the audit file or a durable note
- the artifact quality verdict has been stated clearly, or the anomaly that forced child-session inspection has been stated clearly
- the bridge record that points to the audit file and explains its role will remain visible

Do not compress before reading the produced audit markdown. Do not compress away the bridge record. Reason: the audited agent must be able to resume from the audit artifact and rectification goals without rediscovering audit handoff context.

### 6. Iterate only on real holes

If the child review process exposed real workflow flaws, fix the relevant skill or caller protocol and run the loop again.

Do **not** iterate just to restate the same conclusion. Iterate only when there is a concrete missed requirement, routing defect, tool-usage gap, or verification hole.

---

## Rules

- **MUST**: Treat `audit-session` as the reviewer-side source of truth.
- **MUST**: Treat `continue-child-agent` as the source of truth for interrupted-child recovery.
- **MUST**: Read the produced audit file before judging the child session quality.
- **MUST**: Require the audited agent to read the produced markdown file before doing rectification work.
- **MUST**: Treat bare `[异常]` markers as incomplete reviewer output; abnormal annotations must state the reason so the audited agent can fix the issue from the markdown alone.
- **MUST**: Treat the returned audit artifact path as run-scoped. Different audit runs for the same session may legitimately produce different files under `.sisyphus/tmp/audit/`.
- **MUST**: Inspect the child reviewer session only when the audit artifact or child handoff has a concrete anomaly.
- **MUST**: When anomaly-reviewing the child reviewer process, use `history-recall` plus `opencode-history-grep show/grep` as the primary workflow.
- **MUST**: If anomaly review is needed and the child `session_id` is already known, skip discovery grep and start directly from `show --session <child-session-id> --all --type message`, then inspect whether it wrote the audit template before running `--type all --full-text` for judgment.
- **MUST**: Preserve or state the audit artifact path and rectification goals before compressing any reviewer-process history.
- **MUST**: If the target `session_id` is unknown, locate it with `opencode-history-grep grep --query "<exact user quote>" --type user --page-size 5` before delegating.
- **NEVER**: Spawn a fresh reviewer child when direct continuation of the interrupted child is still possible. Reason: that discards context and makes the audit chain harder to verify.
- **NEVER**: Use native `session_read` / `session_info` as the primary evidence path for reviewing the child execution process. Reason: this workflow is specifically validating history-based audit behavior, so the child's actual execution trace should be inspected through the same grep/show history pipeline.
- **NEVER**: Use `session_list`, date listing, or project-path listing to discover the current session. Reason: those listings can miss active or differently rooted sessions; exact user-quote grep is the reliable discovery path for this workflow.
- **NEVER**: Use discovery grep when the child `session_id` is already known. Reason: that needlessly downgrades an inspection problem into a search problem and makes it easier to miss parts of the reviewer run.
- **NEVER**: Routinely audit the reviewer session when the returned audit artifact is readable, well-formed, and evidence-backed. Reason: reviewer self-audit should be an exception path, not recursive default overhead.
- **NEVER**: If anomaly review is required, judge the reviewer process only from its final answer. Reason: the path-only output intentionally hides the process; anomaly review must inspect the reviewer session itself.
- **NEVER**: Judge tool compliance from `--type message` output. Reason: message-only output intentionally hides tool calls and tool results.
- **NEVER**: Insert a truncated `--type all` overview as a required reviewer-process audit step. Reason: current audit flow intentionally goes from message-level intent analysis to full-text execution evidence.
- **NEVER**: Compress away the only bridge from the conversation to the audit file. Reason: without that bridge, later rectification may lose which artifact is authoritative.

## Output

Unless the caller explicitly asks for prose, the end state of this orchestration is:

1. a completed audit file for the target session
2. a decision that the audit artifact is usable, or a concrete anomaly report if it is not
3. a decision on whether rectification can begin or another reviewer iteration is necessary
