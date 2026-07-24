# opencode-history-grep — Oracle Session Review Skills

状态：**已实现**

## 目标

本项目维护 Oracle 回顾性 `session` 模式的两层 skill：

- `opencode-history-grep/skills/audit-session/SKILL.md`
- `opencode-history-grep/skills/orchestrate-session-audit/SKILL.md`

`audit-session` 是 Oracle reviewer 侧证据规程；`orchestrate-session-audit` 是 Owner caller 侧入口。两者共用 Oracle finding 报告和 Owner 裁决门槛，不维护另一套 reviewer、整改文件或自动勾选流程。

canonical 文件位于 `opencode-history-grep/skills/`；`/root/_/opencode/config/skills/` 与 `/root/.config/opencode/skills/` 通过同一 inode 暴露当前内容，不维护第二份文本。

## 审查对象

Session 审查比较的是：最后一次执行授权时的有效契约，与最终执行流程、最终状态、验证和交付是否一致。

有效契约是累积结果：保留仍有效的要求，应用后续修订，包含用户明确接受的 assistant 计划/docs、最终授权所回答的 assistant 上下文和通过 `question` 工具形成的用户决策，并标记被后续用户方向取代的要求。bounded user+assistant view 负责还原批准对象；assistant 内容只有被明确接受后才成为契约。它不是最后一条用户消息的字面副本。

早期废弃方案不再按旧要求验收；只有未回滚副作用、越权动作、用户状态损害或仍影响最终结果的验证缺口进入最终报告。

## Phase 1 — 角色过滤的有效契约

Oracle 先读取严格限制在目标任务内的 user+assistant 可见消息：

```bash
session_id='<provided session_id>'
opencode-history-grep show --session "$session_id" --all --type 'user' --type 'assistant' --from 'text:<exact unique first user requirement>' --to 'text:<exact unique final authorization>' --full-text
```

source start/to 的原文摘录各至少 20 个字符；输入不足 20 个字符时使用整条输入。歧义时可改用完整 user block id，但调用包仍保留原文。user view 自动保留 ordinary user text 和 completed `question` 的 input/选项/答案；assistant view 用来识别用户批准、修订或拒绝的对象，未被接受的 assistant 自述不属于 source contract。已接受 docs 必须提供精确 path、accepted ref/block 和接受证据；Phase 1 不宽泛读取 tool，仅在精确版本无法恢复时读取对应写入 block。

Oracle 返回 `<oracle_reference mode="session">` XML 外层，内部包含有效契约、已取代要求、检查单元、预期证据、保护边界与输入缺口。此阶段不读取工具证据，不输出 finding、verdict 或修复建议。

## Phase 2 — 有边界的执行证据

Owner 续用同一 Oracle session，Oracle 再读取：

```bash
session_id='<provided session_id>'
boundary_marker='<provided boundary_marker>'
opencode-history-grep show --session "$session_id" --all --type 'all' --from 'text:<exact unique execution start>' --to "text:$boundary_marker" --full-text
```

已知长工具结果仍不完整时才用 `--block` 回源。Oracle 对照 Phase 1 检查最终执行、状态、验证、docs 影响、Knowledge DB 建议和交付，并返回 report-ready Markdown。

Oracle 只生成问题部分：ID、分类、说明、触发链、契约依据、执行证据、影响和不确定性。`[反馈与备注]（主 Agent填写）` 和最终 verdict 由 Owner 填写；Oracle 不写文件，也不把 finding 自动转成整改 Todo。

## Caller 工作流

`orchestrate-session-audit` 负责：

1. 确定 target session；未知时使用唯一用户原话配合 `grep --type user` 定位。
2. 固定目标任务的 source start/source boundary 原文与 endpoint、accepted source artifacts、execution start/boundary 和 review focus。
3. 调用 Oracle，并加载 `audit-session` 与 `history-recall` 完成 Phase 1。
4. 续用同一 Oracle session 完成 Phase 2；中断时使用 `continue-child-agent` 恢复原 Phase 1 参照。
5. Owner 将 Oracle 内容写入 `.sisyphus/tmp/oracle-reviews/YYYY-MM-DD_<任务标题>.md`，填写反馈和最终 verdict。

同一个 review object 不再叠加 candidate Oracle。无法恢复干净 Phase 1 时必须标记为 candidate-exposed retrospective review。

`current_session_id` 的 bare `message_id` 只作来源识别；调用方把返回的 `session_id` 传给带引号的 `--session`，并把唯一 marker 直接作为带引号的 `text:<literal>` all-block execution boundary。Phase 1 的 role-filtered 起止点使用目标任务首条要求和最终授权的唯一文本；文本在类型过滤后只能命中一个 block，零命中或多命中时再用 `grep --type 'user'` 选择完整 block id。

Phase 2 对每个主要动作记录风险/失败模式，并明确检查最终 workspace state、行为/CLI/安装路径/symlink/skill workflow/output format 等 docs 影响，以及是否产生值得长期记录的 decision、trap、pattern 或 operational rule。Oracle 输出不完整时续用同一 session 修正；压缩前保留报告路径、审查边界、当前 verdict/异常和后续目标。

## 成功标准

- Phase 1 使用 bounded user+assistant 历史；user view 自动包含 answered `question` decisions，assistant 内容只有明确接受后成为契约。
- 已接受 source artifacts 具备 path、accepted ref/block 和接受证据；candidate/execution-time docs 留在 Phase 2。
- source start/source boundary 准确限制在目标任务，不包含同 session 更早任务。
- Phase 2 使用同一 Oracle session 和 bounded full-text execution evidence。
- superseded requirement 不被当成最终验收标准。
- Owner 独立核验事实、契约、范围、影响和建议比例性。
- 报告可独立支持整改或等待用户裁决，不依赖 reviewer 自述。
