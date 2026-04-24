# Orchestrate Session Audit

## Skill Definition

Activate this skill when you need to orchestrate a full session-audit loop: discover the target `session_id`, delegate the audit to a child reviewer, continue the same child session if it gets interrupted, then review the child reviewer session itself for process holes or missed findings.

## Core Purpose

This is the **caller-side companion skill** for `audit-session`.

- `audit-session` defines how the delegated reviewer performs the audit.
- `orchestrate-session-audit` defines how the caller finds the session, launches the reviewer, resumes an interrupted reviewer, and audits the reviewer process itself.
- Audit artifacts live under `.sisyphus/tmp/audit/` and must be run-scoped, not session-scoped singleton files.
- The review flow uses `show --type message` first to reconstruct requirements, then `show --type all` / `--full-text` to verify whether tool execution matched those requirements.

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

### 5. Audit the child reviewer session itself

After reading the audit result, inspect the child reviewer session to check whether the reviewer process itself had holes.

- Use the same history-based review discipline:
  - first load `history-recall` if it is not already loaded
  - if the child `session_id` is already known, start with `opencode-history-grep show --session <child-session-id> --all --type message`
  - then run `opencode-history-grep show --session <child-session-id> --all --type all`
  - then run `opencode-history-grep show --session <child-session-id> --all --type all --full-text` before making any judgment
  - if the child `session_id` is not known, first use `opencode-history-grep grep` to locate it, then inspect it with the same message → all → all full-text sequence
  - if you only need to inspect operations after a known block, use `show --session <child-session-id> --all --type all --from <block-id-or-index> --full-text`; use `--to <block-id-or-index>` when the review window has a known endpoint
  - inspect whether it followed `audit-session`, especially whether it used the message-only pass for requirement/phase reconstruction and the full-text all-block pass for execution judgment
  - check whether it skipped deep dives, faked verification, guessed collapsed content, judged tools from message-only output, or drifted from the path-only output contract
- If the child session was interrupted and later continued, audit the continued session chain as one logical reviewer run.
- Treat the child's execution history as the primary evidence source. The goal here is to review the child's actual steps, not just its final conclusion.

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
- **MUST**: When reviewing the child reviewer process, use `history-recall` plus `opencode-history-grep show/grep` as the primary workflow.
- **MUST**: If the child `session_id` is already known, skip discovery grep and start directly from `show --session <child-session-id> --all --type message`, followed by `--type all`, then `--type all --full-text` before making any judgment.
- **MUST**: If the target `session_id` is unknown, locate it with `opencode-history-grep grep --query "<exact user quote>" --type user --page-size 5` before delegating.
- **NEVER**: Spawn a fresh reviewer child when direct continuation of the interrupted child is still possible. Reason: that discards context and makes the audit chain harder to verify.
- **NEVER**: Use native `session_read` / `session_info` as the primary evidence path for reviewing the child execution process. Reason: this workflow is specifically validating history-based audit behavior, so the child's actual execution trace should be inspected through the same grep/show history pipeline.
- **NEVER**: Use `session_list`, date listing, or project-path listing to discover the current session. Reason: those listings can miss active or differently rooted sessions; exact user-quote grep is the reliable discovery path for this workflow.
- **NEVER**: Use discovery grep when the child `session_id` is already known. Reason: that needlessly downgrades an inspection problem into a search problem and makes it easier to miss parts of the reviewer run.
- **NEVER**: Judge the reviewer process only from its final answer. Reason: the path-only output intentionally hides the process; you must inspect the reviewer session itself.
- **NEVER**: Judge tool compliance from `--type message` output. Reason: message-only output intentionally hides tool calls and tool results.

## Output

Unless the caller explicitly asks for prose, the end state of this orchestration is:

1. a completed audit file for the target session
2. a reviewed child-auditor session
3. a decision on whether another iteration is necessary
