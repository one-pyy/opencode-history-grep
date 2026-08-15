---
name: audit-session
description: Reviewer-side protocol for Oracle session mode: reconstruct the final effective contract from role-filtered history, then compare bounded execution evidence and return report-ready findings.
---

# Audit Session

Use this skill only inside an Oracle retrospective `session` review. Oracle remains read-only. It returns a Phase 1 XML reference and Phase 2 report-ready Markdown; the owner writes the report, fills feedback, and decides the final verdict.

## Required inputs

- target `session_id`
- source-start excerpt and source-boundary excerpt, each at least 20 characters or the entire message when shorter, plus the resolved endpoint for each
- execution start and execution boundary
- accepted source artifacts, each with exact path, accepted ref or block, and acceptance evidence
- review focus, allowed semantic changes, affected authoritative sections, protected invariants, direct dependencies, explicit exclusions, and report ID prefix

If these boundaries cannot be established, report the exact gap. Do not silently treat the whole session as a clean independent source.

## Phase 1 — effective contract

Load `history-recall`, then read the bounded visible user and assistant conversation through the source boundary:

```bash
session_id='<provided session_id>'
opencode-history-grep show --session "$session_id" --all --type 'user' --type 'assistant' --from 'text:<exact unique first user requirement>' --to 'text:<exact unique final authorization>' --full-text
```

Both endpoints must resolve uniquely inside the filtered conversation so earlier unrelated tasks stay excluded. Each text excerpt must contain at least 20 characters; if the whole source message is shorter, use that whole message. Use quoted `text:<literal>` endpoints or exact user block ids, and include the excerpt in the Oracle call even when a block id is used. Do not pass a bare message id or a tool-result marker as a message-filtered range endpoint.

Reconstruct the contract active at the final execution authorization:

- requirements and acceptance criteria still in force
- later amendments that replace earlier wording
- explicit non-goals and protected boundaries
- requirements superseded by later user direction
- required verification and delivery evidence

Keep only requirements that can affect the stated review focus. Cite exact user blocks and accepted artifact headings instead of restating the conversation or source documents. Judge the caller's scope before reading broadly: narrow an overbroad range, and add only a concrete dependency or protected invariant that is necessary to evaluate the requested object. A dependency is concrete only when the scoped source directly references it or it lies on the required execution/propagation path; similar names, shared directories/domains, and possible contextual relevance do not qualify. For a narrow review object, each Phase 1 section normally contains one to three bullets and groups related references.

The user view includes ordinary user text and completed `question` decisions with their input and selected answer. Assistant text identifies what the user approved, amended, or rejected; it is not authoritative without explicit acceptance in the bounded conversation. For every accepted source artifact, inspect the exact accepted path/version or block and verify the supplied acceptance evidence. Do not broadly read tool history. Use a targeted write block only when the accepted artifact cannot be recovered from its exact accepted version. Keep ambiguous acceptance unresolved for the owner.

Return exactly one outer XML envelope with readable Markdown inside:

```xml
<oracle_reference mode="session">
## Review object and allowed changes
## Protected invariants and source references
## Direct dependencies
## Material failure modes and Phase 2 evidence
## Exclusions and input gaps
</oracle_reference>
```

List only superseded requirements that would otherwise change the scoped review, and place them under `Exclusions and input gaps`. Do not read general tool calls or tool results. Do not write findings, verdicts, remediation, conversation summaries, or exhaustive contract restatements in Phase 1.

## Phase 2 — execution comparison

Continue the same Oracle session. Read the bounded execution evidence:

```bash
session_id='<provided session_id>'
boundary_marker='<provided boundary_marker>'
opencode-history-grep show --session "$session_id" --all --type 'all' --from 'text:<exact unique execution start>' --to "text:$boundary_marker" --full-text
```

Use `--block` only when a known tool result or raw part needs full recovery. Compare the final execution flow, final workspace state, verification, docs impact, knowledge suggestion, and delivery with the effective contract from Phase 1.

Keep document states separate. Unapproved candidate docs and docs created or changed during execution are Phase 2 evidence. Prefer exact paths and baseline-to-candidate or task diffs; use a targeted write block only when Git evidence is unavailable. For candidate docs, check direct conflict, omitted requirements, invented constraints, implementation-status mismatch, ambiguity, equivalent wording, and superseded content. Every retained docs concern must cite the source basis, exact docs text, difference, impact, and uncertainty.

For each major action, identify its realistic risk or failure mode and the evidence that proves or disproves it. Docs impact must explicitly consider changed behavior, CLI parameters, installation paths, symlink/setup, skill workflow, output format, and other user-visible usage. Recommend a Knowledge DB write only for a durable decision, trap, recurring pattern, or long-lived operational rule; do not write the entry.

Earlier superseded requirements are not acceptance criteria. Inspect earlier actions only when they may have left an unreverted side effect, crossed an unauthorized boundary, damaged user state, or created a verification gap that still affects the final result.

When the execution deletes, replaces, or substantially rewrites existing code, docs, configuration, prompts, or skills, compare the pre-change baseline with the final state for unintended loss of behavior, contracts, constraints, status, references, or maintenance guidance. Classify each material removal as required, equivalently relocated, superseded, a possible regression, or ambiguous; do not presume that removed content must be restored.

Return report-ready Markdown using the caller's Oracle report template. For every retained finding include:

- stable ID and Oracle classification
- explanation and trigger chain
- effective-contract basis
- exact execution evidence or missing evidence
- impact and unresolved uncertainty

Leave `[反馈与备注]（主 Agent填写）` fields and the final report verdict unresolved. Do not write files, mark findings as accepted repairs, or produce a rectification todo list.

## Evidence and scope rules

- Treat the bounded user+assistant conversation and accepted source artifacts as the source-contract layer. The user view already includes answered `question` decisions; assistant text becomes authoritative only through explicit acceptance.
- Start from the caller's bounded review focus. Expand only for a cited dependency, propagation path, or protected invariant, and inspect only the additional evidence needed for that point.
- Treat unaccepted assistant self-reports and general tool history as Phase 2 evidence, not Phase 1 authority.
- Separate final-delivery mismatch from historical process risk.
- Do not flag abandoned or superseded approaches when they left no relevant side effect.
- Classify ambiguity instead of choosing a user meaning.
- Return an empty problem list when no material finding survives the evidence gate; do not declare the review passed.
- If the XML reference or Phase 2 report is incomplete, continue the same Oracle session to correct the missing structure or evidence. Do not start a replacement reviewer or broaden the review object.
