---
name: orchestrate-session-audit
description: Orchestrate Oracle session mode by fixing source and execution boundaries, running both phases in one Oracle session, adjudicating findings, and persisting a report only for confirmed problems.
---

# Orchestrate Session Audit

This is the caller-side entry for an explicitly requested retrospective session review. It does not create a separate audit reviewer system; it invokes Oracle in `session` mode and uses the shared Oracle report and owner adjudication gate.

派发前读取 `/root/_/opencode/config/skills/review-work/SKILL.md` 的 `Caller authority`（调用方权限）、`Oracle workflow`（两阶段与只读边界）、`Conditional Oracle report artifact`（报告模板）和 `Finding admission gate`（问题准入）章节；完整、未变的内容已可见时直接复用。本技能沿用其中的只读限制、报告格式、发现准入和复查要求；会话边界和执行顺序按下文安排，不额外启动候选审查。

## Establish the review object

Determine:

- target `session_id`
- source start and source boundary: excerpts of at least 20 characters, or each entire message when shorter, plus their resolved endpoints
- accepted source artifacts: exact path, accepted ref or block, and acceptance evidence
- execution start and execution boundary
- review focus, allowed semantic changes, affected authoritative sections, protected invariants, direct dependencies, explicit exclusions, and task title

If the current session id is needed, use `current_session_id`. Its bare `message_id` identifies the caller message but is not a `show --from/--to` endpoint. Use the returned values directly:

```bash
session_id='<provided session_id>'
boundary_marker='<provided boundary_marker>'
opencode-history-grep show --session "$session_id" --all --type 'all' --to "text:$boundary_marker" --full-text
```

Pass `text:<boundary_marker>` as the all-block execution boundary. For the role-filtered Phase 1 source window, pass quoted `text:` excerpts of at least 20 characters from the first requirement and final authorization; if either whole message is shorter, pass the whole message. Text endpoints resolve after type filtering and must match exactly one block. If an excerpt is not unique, use `grep --type 'user'` to select the full user block id, but still include the original excerpt in the Oracle call. This excludes unrelated tasks earlier in the same session.

Phase 1 uses the bounded union of `--type 'user' --type 'assistant'`. User blocks include ordinary user text and completed `question` decisions; assistant text supplies approval context but becomes contract only through explicit user acceptance. Do not add general tool-result blocks. For each accepted source artifact, pass the exact path, accepted ref or block, and acceptance evidence; use a targeted write block only when the accepted artifact cannot be recovered from its exact accepted version.

If a historical session id is unknown, the same exact-user-quote grep locates it. Do not use broad session listings when an exact quote is available.

The effective contract is cumulative, not merely the last sentence: retain requirements still in force, apply later amendments, include explicitly accepted assistant artifacts, and mark earlier requirements superseded by later user direction.

## Phase 1 — Oracle reference

Invoke Oracle with `audit-session` and `history-recall` loaded. Provide only the session id, source excerpts and resolved endpoints, accepted source-artifact records, review focus, allowed semantic changes, affected authoritative sections, protected invariants, direct dependencies, exclusions, and report prefix. Do not provide execution-time docs, final execution evidence, candidate files, or owner findings. Require Oracle to narrow an overbroad scope and expand only for a concrete cited dependency or protected invariant.

Require the `<oracle_reference mode="session">` output defined by `audit-session`. Continue the same Oracle session as soon as the reference returns.

## Phase 2 — bounded execution review

Continue the same Oracle session and provide the execution start, execution boundary, and exact repository evidence needed to verify final state. Classify unapproved candidate docs and execution-time docs as Phase 2 evidence, normally through exact paths and diffs. Require report-ready Markdown following the shared Oracle report template.

If the Oracle session is interrupted, use `continue-child-agent`. Recover the original Phase 1 reference before exposing Phase 2 evidence; do not reconstruct a replacement reference after reading the execution.

## Adjudicate, then conditionally persist

The owner adjudicates every finding before writing a file. If no finding is a factually confirmed, contract-backed, in-scope candidate defect or necessary direct consequence admitted to repair, state the passing outcome and do not create a report.

When at least one finding passes that gate, create or update:

```text
.sisyphus/tmp/oracle-reviews/YYYY-MM-DD_<task-title>.md
```

Append `-02` only for another review run with the same title. Persist the retained problem list, evidence, trigger chains, classifications, and owner adjudication. Fill each retained finding's fact status, contract relationship, task relationship, impact, proposal quality, disposition, evidence, and next action.

The owner sets the final verdict: `通过`, `有阻塞问题`, `等待用户裁决`, or `证据不足`. Oracle output is review evidence, not repair authorization. Only a factually confirmed, contract-backed, in-scope finding with disposition `采纳修复` may enter repair.

If Phase 1 XML or Phase 2 report content is malformed, incomplete, lacks evidence, or omits the requested focus, continue the same Oracle session to repair that exact output. Iterate only on a concrete missing requirement, evidence gap, routing defect, or verification hole.

Before compressing reviewer-process history for a review that created a report, preserve the report path, review mode and boundaries, current verdict or anomaly, and any rectification goals in the conversation or another durable handoff. Do not compress away the only bridge that identifies the report and its role. For a review with no admitted finding and no report, the user-facing passing result is sufficient unless other work remains active.

## Acceptance

- Phase 1 used the bounded user+assistant conversation and did not inspect general execution evidence.
- The source window started at the target task's first user requirement and excluded earlier unrelated tasks.
- Source excerpts met the 20-character-or-entire-message rule, and the call retained the excerpts even when endpoints used block ids.
- Phase 1 automatically included answered `question` decisions and bounded assistant context; only explicitly accepted assistant content and source artifacts became authoritative.
- Accepted source artifacts carried exact path, accepted ref or block, and acceptance evidence; ambiguous acceptance remained unresolved.
- The caller explicitly passed allowed semantic changes, affected authoritative sections, protected invariants, direct dependencies, and exclusions to the reviewer.
- Phase 1 returned a concise reference to the requirements and boundaries that affect the requested focus rather than restating the full conversation or source artifacts.
- Phase 2 used the same Oracle session and bounded full execution evidence.
- Superseded requirements were not treated as final acceptance criteria.
- Historical actions were retained only when unreverted side effects, authority breaches, or verification gaps still mattered.
- The owner decided whether any finding passed the report gate; when one did, the owner rather than Oracle wrote the report and decided its verdict.

Return the report path and whether rectification can begin when an artifact was created; otherwise state that no report was needed. Do not launch an additional candidate Oracle for the same retrospective review object.
