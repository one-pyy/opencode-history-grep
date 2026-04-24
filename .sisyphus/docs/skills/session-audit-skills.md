# opencode-history-grep — session audit skills

状态：**已实现**

## 目标

本项目维护两个 session 审查 skill：

- `skills/audit-session/SKILL.md`
- `skills/orchestrate-session-audit/SKILL.md`

它们的 canonical 版本在本仓库内。外部 OpenCode skill 路径应是软连接：

```text
/root/_/opencode/config/skills/audit-session -> /root/_/opencode/my_plugins/opencode-history-grep/skills/audit-session
/root/_/opencode/config/skills/orchestrate-session-audit -> /root/_/opencode/my_plugins/opencode-history-grep/skills/orchestrate-session-audit
```

## 职责分工

`audit-session` 是 reviewer 侧规程：给定 `session_id` 后，它负责读取历史、拆阶段、写 run-scoped 审查文件、二次验证并输出审查文件路径。

`orchestrate-session-audit` 是 caller 侧规程：它负责发现目标 `session_id`、委派 reviewer、在中断时续同一 reviewer 会话、读取审查文件，并判断审查产物是否可用于整改。

## 审查读取与落盘顺序

session 审查使用“先固定意图，再看执行证据”的顺序：

1. `opencode-history-grep show --session <id> --all --type message`
   - 用于重建用户意图、需求变化、判断、方案和阶段边界。
2. 写入 run-scoped 审查模板。
   - 模板必须先记录 message 层意图分析和 Phase 边界。
   - 此时不能判断工具执行是否合规，核验项必须保持未勾选。
3. `opencode-history-grep show --session <id> --all --type all --full-text`
   - 用作工具执行合规判断的 full-text 证据源。
   - 不再要求先跑单独的截断版 `--type all` overview。
4. 回读同一个审查文件并回填结论。
   - 将未勾选项改成 `[x]` 或带原因的 `[异常: ...]`。
   - 在文件末尾追加具体整改目标和修改建议。

`--type message` 只显示用户与 assistant 对话块，适合固定需求和意图；`--type all --full-text` 显示工具调用和工具结果，适合最终判断执行是否相符。不能从 `message` 输出推断工具行为，也不能在写初始模板前让截断工具流影响意图分析。

## Caller 侧产物验收与压缩边界

`orchestrate-session-audit` 在拿到 reviewer 返回的审查文件路径后，必须先读取该 markdown。只拿到路径不等于已经理解整改目标。

默认不复核 reviewer 会话本身。caller 只需要验收审查产物是否可用：路径是否是 run-scoped、文件是否可读、异常标注是否写明原因、整改目标是否具体、是否覆盖调用时指定的 audit focus。

只有出现具体异常时才回看 reviewer 会话，例如：没有返回审查文件路径、文件缺失、裸 `[异常]`、初始模板疑似直接打勾、审查结果和已知事实冲突、漏掉明确 audit focus、或 child 中断续跑行为需要确认。

需要异常复核 reviewer 会话时，如果 child `session_id` 已知，应按当前审查纪律读取：

1. `opencode-history-grep show --session <child-session-id> --all --type message`
2. 分析 reviewer 是否先重建意图、写初始审查模板，再判断工具执行
3. `opencode-history-grep show --session <child-session-id> --all --type all --full-text`

不应在 message pass 和 full-text pass 之间强制插入截断版 `--type all` overview。原因是 reviewer-process 异常复核也应先固定 message 层意图，再从 full-text 工具证据判断执行是否合规。

验收审查产物后可以压缩过程记录，但必须先确保以下事实已经保存在当前上下文或持久文件里：审查文件路径、整改目标、产物可用性结论，以及指向审查文件的桥接记录。不能压掉唯一说明“哪个审查文件是权威整改来源”的记录。

## 会话定位规则

如果目标 `session_id` 未知，`orchestrate-session-audit` 应使用目标会话中的唯一用户原话定位：

```bash
opencode-history-grep grep --query "<a distinctive exact user quote from the target session>" --type user --page-size 5
```

不要用 `session_list`、日期列表或项目路径列表定位当前会话。原因是这些列表可能漏掉活跃会话或不同 root 的会话；唯一用户原话直接查询审查工作流使用的 compiled history，更可靠。

## 范围续审

如果主 agent 在一次审查后继续修改，审查员可以从已知 block 边界继续读取新操作：

```bash
opencode-history-grep show --session <id> --all --type all --from <block-id-or-index> --full-text
```

`--from` / `--to` 接受 block id，例如 `msg_dbfb10314001i6KZwkoOJzLYTC:0198`，也接受零基 block 序号。任一侧不传表示开放边界。

## 产物规则

审查报告写入 run-scoped 路径：

```text
.sisyphus/tmp/audit/audit_{session_id}.{run_id}.md
```

同一个 session 可以有多次审查运行，因此不能把审查文件设计成 session-scoped 单例。

被审查者必须读取这份 markdown 后再整改；只拿到路径不等于已经理解问题。审查者标注异常时必须写清原因，例如 `[异常: skipped full-text evidence pass before judging tool output]`，不能只写裸 `[异常]`。这样被审查者可以只靠审查文件定位问题和整改目标。

审查报告每个相关 Phase 至少检查：需求符合度、范围控制、验证证据、docs 影响、Knowledge DB 建议、工作区状态。docs 影响覆盖 README、docs、skill 文本、CLI help 或其他用户可见说明是否需要同步；Knowledge DB 建议只判断是否应写入，不由审查员自动写入。

## 维护规则

修改这两个 skill 时，应只改仓库内 canonical 文件，再通过软连接暴露到 `/root/_/opencode/config/skills/`。不要在外部路径维护第二份内容，避免规则漂移。
