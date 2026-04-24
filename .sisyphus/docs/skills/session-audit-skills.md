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

`orchestrate-session-audit` 是 caller 侧规程：它负责发现目标 `session_id`、委派 reviewer、在中断时续同一 reviewer 会话、读取审查文件，并审查 reviewer 自己的执行过程是否符合 `audit-session`。

## 审查读取顺序

session 审查使用三段式读取顺序：

1. `opencode-history-grep show --session <id> --all --type message`
   - 用于需求、判断、方案和阶段边界重建。
2. `opencode-history-grep show --session <id> --all --type all`
   - 用于把工具调用和工具输出映射回 message 层需求。
3. `opencode-history-grep show --session <id> --all --type all --full-text`
   - 用于最终判断，不允许只靠截断输出下结论。

`--type message` 只显示用户与 assistant 对话块；`--type all` 显示工具调用和工具结果。审查工具执行是否相符时必须使用 `all`，不能从 `message` 输出推断工具行为。

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
