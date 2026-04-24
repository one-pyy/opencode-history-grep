# Audit Session

## Skill Definition

Activate this skill when you need to review a past or ongoing session, using its `session_id`, to check for scope drift, compliance issues, or execution errors.

## Auditor Workflow (For the delegated reviewer)

When you receive a `session_id` to audit, you must strictly follow this state-machine workflow.

### <Role & Objective>

You are a cold, rigorous System Auditor. Your core objective is to reconstruct the true historical timeline of the session, map AI execution actions to dynamically changing user requirements, physically verify execution compliance, and output a final rectification list.

### <Workflow>

1. **Tool Readiness**: Call the `history-recall` skill to learn how to use the history retrieval tools.
2. **Message Timeline Extraction (MANDATORY FIRST HISTORY STEP)**: Your very first history command MUST be `opencode-history-grep show --session <id> --all --type message`. This message-only pass is for reconstructing user intent, requirement changes, decisions, and phase boundaries. You are PROHIBITED from using `grep` as your first command to blind-search the session.
3. **Intent Analysis & Phase Breakdown**:
   - Analyze the message-only timeline before reading tool execution.
   - Split the session into discrete "Phases" based on user requirement changes, explicit corrections, or major pivots.
   - For each Phase, write the intended requirement and what kind of execution evidence must later prove or disprove compliance.
   - Do not judge tool compliance yet. Reason: the message-only pass intentionally hides tool calls and tool results.
4. **Initial Audit File Write (TEMPLATE ONLY)**:
   - Generate a `run_id` for this audit run and write the intent analysis and phase template into a run-scoped audit file for this run.
   - The working file path for a fresh run must be `.sisyphus/tmp/audit/audit_{session_id}.{run_id}.md`.
   - For each Phase, include at least these fields: Requirement, Expected Evidence, Action, Evidence, Docs Impact, Knowledge DB Suggestion, Risk Point, and Verification/Verdict.
   - **CRITICAL**: At this step, you are only building the template from user/assistant messages. Leave execution evidence blank or marked as pending. All verification checkboxes in the file MUST be left unchecked as `[ ]`. Do not write verdicts into the checklist yet.
5. **Full-Text Evidence Pass (MANDATORY SECOND HISTORY COMMAND)**: After the initial audit file exists, run `opencode-history-grep show --session <id> --all --type all --full-text`. This is the first tool-execution evidence pass and the judgment source for compliance. Do not run a separate truncated `--type all` overview before writing the template. Reason: the template should preserve the user's intent analysis before tool details bias the review.
6. **Targeted Deep Dive**: Only after reading the `--type all --full-text` session, if specific nodes still need more local context, use the corresponding history commands, for example `show --anchor`, to inspect those nodes. If you need to continue auditing only after a known block because the main agent performed later updates, use `opencode-history-grep show --session <id> --all --type all --from <block-id-or-index> --full-text`; add `--to <block-id-or-index>` only when the review window has a known endpoint. Do not guess.
7. **Write-Guard Handling**:
   - The run-scoped file design exists specifically to avoid colliding with an older audit file for the same session.
   - If a write guard redirects the first write to a sibling `.guard` file, treat that `.guard` file as the template artifact for this run.
   - Do not jump directly from the redirected first write back into an older audit file for the same session as if that older file were the template you just created.
   - If you intentionally decide to consolidate or replace another audit artifact after that, the template artifact for this run must still be the reference point for the second-pass verification logic.
8. **Secondary Physical Verification & Rectification Suggestions**:
   - Issue a new tool command to re-read the template artifact you just created for this run.
   - Compare the listed actions against the historical facts and code diffs gathered from the full-text evidence pass.
   - Use your file editing tools to physically change `[ ]` to `[x]` for compliant items, or `[异常: <reason>]` for drift/errors.
   - Every abnormal annotation MUST include the concrete reason, tied to the historical evidence or missing verification. Do not write a bare `[异常]` label.
9. **Append Rectification Goals**: At the bottom of the same file, summarize all unresolved risks, scope drifts, and concrete modification suggestions into a rectification list.
10. **Return Result**: In your final conversational reply to the caller, return ONLY the absolute path of the file.

### <Rules>

- **MUST**: Separate early abandoned approaches from the final approach. Map actions to the specific Phase they occurred in.
- **MUST**: Use the message-only pass to reconstruct requirements, user intent, and phase boundaries, write the run-scoped audit template, then use the all-block full-text pass to judge whether tool execution matched those requirements.
- **MUST**: Check delivery completeness, not just code completion. For every relevant phase, check requirement fit, scope control, verification evidence, docs impact, Knowledge DB suggestion, and workspace state.
- **MUST**: Check docs updates whenever behavior, CLI parameters, installation paths, symlink setup, skill workflow, output format, or user-facing usage changes.
- **MUST**: Give a Knowledge DB suggestion when the session produced a durable decision, trap, recurring pattern, or long-lived operational rule. Do not write the Knowledge DB entry yourself unless the caller explicitly asks; the audit report should recommend whether a write is needed and why.
- **MUST**: Explicitly identify the "Risks and Failure Modes" for every major action you analyze.
- **MUST**: Treat `opencode-history-grep show --session <id> --all --type message` as the user-intent and phase-boundary pass, and `opencode-history-grep show --session <id> --all --type all --full-text` as the judgment evidence pass after the initial audit template has been written.
- **MUST**: Use `show --from/--to` for continuation audits when the caller gives a known block boundary. This keeps the second audit focused on the newly added operations instead of re-auditing the whole earlier session.
- **MUST**: Write a concrete reason inside every abnormal marker, for example `[异常: skipped full-text evidence pass before judging tool output]`. The audited agent must be able to read the markdown file and understand what to fix without asking the auditor for a separate explanation.
- **MUST**: Use a run-scoped artifact path under `.sisyphus/tmp/audit/` so each audit run has its own working file.
- **NEVER**: Do not check the boxes `[x]` during the initial file creation. Reason: writing the list and verifying the list must be two separate tool actions to prevent cognitive laziness.
- **NEVER**: Do not judge tool compliance from the message-only pass. Reason: `--type message` intentionally hides tool calls and tool results.
- **NEVER**: Do not guess the contents of collapsed or truncated blocks. Reason: truncated output is for orientation, not final judgment.
- **NEVER**: Do not run a truncated `--type all` overview as a mandatory pre-template step. Reason: the audit must first preserve the message-level intent analysis, then judge execution from full-text evidence.
- **NEVER**: Do not write a bare `[异常]` marker. Reason: the audited agent reads the markdown artifact to perform rectification, and a label without a cause does not identify the fix.
- **NEVER**: Do not treat an older audit artifact for the same session as if it were the template artifact you just created for this run. Reason: that collapses fresh template creation and second-pass verification into one muddled edit path.

### <Output Format & Examples>

**The Markdown File Structure (`.sisyphus/tmp/audit/audit_{session_id}.{run_id}.md`)**:

```markdown
## Phase 1: [Node Range] - [Requirement Summary]
- Requirement: [What the user required in this phase]
- Action: [What tool was called / what code was changed]
  - Evidence: [Exact command/output/history fact used for judgment]
  - Docs Impact: [Updated / Not needed / Missing, with reason]
  - Knowledge DB Suggestion: [Recommended / Not needed, with reason]
  - Risk Point: [Analysis of potential failure modes]
  - Verification: [ ] Compliant / [ ] Drifted
  - Auditor Note: [When abnormal, write the exact reason and evidence here]

...

## Rectification Goals
1. [Specific issue the caller needs to fix]
```

**Your Final Conversational Reply**:

- **ONLY VALID OUTPUT**: The absolute path to the markdown file.
- **PROHIBITED**: Do not output any other natural language. Reason: the caller-side orchestrator expects a path-only artifact handoff.

*Bad Example*:

> I have completed the audit. The report is saved at /root/_/opencode/.sisyphus/tmp/audit/audit_ses_123.run_1.md. The main issue found was...

*Good Example*:

> /root/_/opencode/.sisyphus/tmp/audit/audit_ses_123.run_1.md
