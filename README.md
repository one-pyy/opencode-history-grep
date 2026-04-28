# opencode-history-grep

Compiled history recall for `opencode` upstream SQLite sessions.

中文说明见下半部分。[English](#english) 在前。

---

## English

### What this is

`opencode-history-grep` is a Python CLI that turns `opencode`'s upstream SQLite history into compiled block views, then lets you search and reopen those views with higher signal than raw text grep.

It is designed for history recall tasks such as:

- “What did we decide last time?”
- “How did we implement this before?”
- “Where did that error show up?”
- “What exact command or tool output did we see?”
- **AI Behavior Audit**: Pass a `session-id` to another AI so it can review the execution process, check for mistakes, and evaluate tool usage.

### Inspiration

This project was inspired by **VCC (View-oriented Conversation Compiler)**:

- Repository: https://github.com/lllyasviel/VCC/

The main idea borrowed from VCC is: **compile conversation history into better reading/search views first, then search those views**. This project adapts that idea to `opencode`'s SQLite-based history instead of Claude JSONL logs.

### Current behavior

- Default upstream SQLite: `/root/.local/share/opencode/opencode.db`
- Default compiled repository: `/root/.local/share/opencode-history-grep`
- `grep` automatically refreshes the compiled repository before searching
- `show` automatically refreshes the compiled repository before reading a session or anchor
- unchanged sessions are skipped during refresh
- default search output is paginated (`10` results per page)
- search results emphasize `match`, not a fragile first-line summary
- `system` content is excluded from the search domain

### Install globally

Recommended install:

```bash
uv tool install --editable "/root/_/opencode/my_plugins/opencode-history-grep"
```

If the tool was already installed and you changed CLI behavior, options, defaults, or output format, refresh the global command:

```bash
uv tool uninstall opencode-history-grep
uv tool install --editable "/root/_/opencode/my_plugins/opencode-history-grep"
```

### Basic usage

Daily use usually starts with `grep`:

```bash
opencode-history-grep grep --query "history recall"
```

Regex and multi-line matching:

```bash
opencode-history-grep grep --regex --query "line before\nneedle match"
```

Filter by directory and type:

```bash
opencode-history-grep grep --regex --directory /root/_/opencode --type assistant --query "sqlite.*history|history.*sqlite"
```

Filter by time window:

```bash
opencode-history-grep grep --regex --since 2026-04-01 --until 2026-04-23 --query "migration|knowledge[_ -]?database"
```

View full context around a hit:

```bash
opencode-history-grep show --session <session-id> --anchor <block-id> --before 5 --after 5
```

Read a whole compiled session:

```bash
opencode-history-grep show --session <session-id> --all
```

Read complete raw content for specific compiled blocks:

```bash
opencode-history-grep show --session <session-id> --block <block-id>,<block-id-or-index>
```

`--block` uses the compiled view only for block-to-message/part location, then reads the upstream SQLite record so long tool outputs are not limited by compile-time summaries.

Only use `--full-text` when you really need long raw block content:

```bash
opencode-history-grep show --session <session-id> --all --full-text
```

### Type filters

- `user`: original user wording
- `assistant` / `ai`: explanations and conclusions
- `tool_call`: command/tool parameters and calls
- `tool_result`: tool output and errors
- `tool`: `tool_call + tool_result`
- `message`: `user + assistant`

Recommended defaults for recall:

- use `--type user` when looking for original requirements
- use `--type assistant` when looking for explanations or conclusions

### Skill

This repository includes a reusable skill at:

- `skills/history-recall/SKILL.md`

The skill is intended for cases where a user refers to something done in the past, but the current docs / knowledge database do not already answer it, or the user explicitly asks to search history.

---

## 中文

### 这是什么

`opencode-history-grep` 是一个 Python CLI，用来把 `opencode` 的 upstream SQLite 历史编译成 block 视图，然后在这些视图上做高信号检索与上下文回看。

它适合处理这类“历史回忆”问题：

- “我们上次怎么决定的？”
- “这个功能以前怎么做过？”
- “那个报错之前出现在哪？”
- “当时跑过什么命令，工具输出是什么？”
- **AI 运行审查**：传入 `session-id`，让另一个 AI 审查之前的运行过程，检查是否有出错或不合理的工具调用。

### 灵感来源

这个项目受 **VCC (View-oriented Conversation Compiler)** 启发：

- 仓库地址：https://github.com/lllyasviel/VCC/

借用的核心思想是：**先把历史编译成更适合阅读和搜索的视图，再在这些视图上检索**。不同的是，这里适配的是 `opencode` 的 SQLite 历史，而不是 Claude JSONL 日志。

### 当前行为

- 默认 upstream SQLite：`/root/.local/share/opencode/opencode.db`
- 默认 compiled repository：`/root/.local/share/opencode-history-grep`
- `grep` 会在搜索前自动 refresh compiled repository
- `show` 会在读取 session 或 anchor 前自动 refresh compiled repository
- 未变化的 session 会在 refresh 时跳过
- 默认每页 10 条结果
- 结果页主看 `match`，不依赖脆弱的一行摘要
- `system` 不进入搜索域

### 全局安装

推荐安装方式：

```bash
uv tool install --editable "/root/_/opencode/my_plugins/opencode-history-grep"
```

如果之前装过，而你又改了 CLI 行为、参数、默认值或输出格式，应刷新全局命令：

```bash
uv tool uninstall opencode-history-grep
uv tool install --editable "/root/_/opencode/my_plugins/opencode-history-grep"
```

### 基本用法

日常使用一般直接从 `grep` 开始：

```bash
opencode-history-grep grep --query "history recall"
```

regex 与跨行匹配：

```bash
opencode-history-grep grep --regex --query "line before\nneedle match"
```

按目录与类型筛选：

```bash
opencode-history-grep grep --regex --directory /root/_/opencode --type assistant --query "sqlite.*history|history.*sqlite"
```

按时间窗口筛选：

```bash
opencode-history-grep grep --regex --since 2026-04-01 --until 2026-04-23 --query "migration|knowledge[_ -]?database"
```

回看命中的上下文：

```bash
opencode-history-grep show --session <session-id> --anchor <block-id> --before 5 --after 5
```

直接看整会话：

```bash
opencode-history-grep show --session <session-id> --all
```

读取指定 compiled block 的完整原始内容：

```bash
opencode-history-grep show --session <session-id> --block <block-id>,<block-id-or-index>
```

`--block` 只用 compiled view 做 block 到 message/part 的定位，然后回源 SQLite 读取原始记录，所以长工具输出不会受 compile 阶段摘要截断影响。

只有确实需要长文本或长工具输出时，再用 `--full-text`：

```bash
opencode-history-grep show --session <session-id> --all --full-text
```

### 类型筛选

- `user`：需求原话
- `assistant` / `ai`：解释和结论
- `tool_call`：命令参数和工具调用
- `tool_result`：工具输出和错误
- `tool`：`tool_call + tool_result`
- `message`：`user + assistant`

默认推荐：

- 找原始要求时优先 `--type user`
- 找解释 / 结论时优先 `--type assistant`

### Skill

仓库内附带一个可复用 skill：

- `skills/history-recall/SKILL.md`

这个 skill 适用于：用户提到过去做过某件事，但当前 docs / knowledge database 还不足以回答，或者用户明确要求查找历史记录。
