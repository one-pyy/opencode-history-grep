# opencode-history-grep — history recall skill 设计

状态：**已设计，待实现对齐**

## 目标

这份文档描述一个给模型使用的 skill：让模型学会如何调用 `opencode-history-grep` 的 CLI 来查询历史记录，而不是直接重扫原始 SQLite，也不是退回普通文本 grep。

固定默认路径：

- upstream DB：`/root/.local/share/opencode/opencode.db`
- compiled repository：`/root/.local/share/opencode-history-grep`

对外话术应收口为：

- **日常搜索：直接 `grep`**
- **`grep` 会自动 compile / refresh，一般无需手动 `compile`**
- **显式备库 / 离线准备 / 范围受控仓库：才单独用 `compile`**

默认推荐的类型筛选应优先教：

- `--type user`
- `--type assistant`

`tool_call` / `tool` 作为补充说明，不作为默认主推荐路径。

还应明确告诉模型：如果结果过宽，优先建议用户加 `--type assistant`、`--since/--until`，或把 query 改成更精确短语 / `--regex`。

## 这个 skill 要教会模型什么

模型应学会四件事：

1. 何时直接 `grep`
2. 何时才需要单独 `compile`
3. 何时用目录筛选缩小 session 范围
4. 何时用时间筛选缩小 session 范围
5. 何时用 `show` 回跳完整上下文

## 推荐工作流

这部分参考 VCC 的价值，不是照搬 VCC 的命令：

1. **先确认范围**
   - 是否应按当前项目目录筛选
   - 是否应按用户提到的时间窗口筛选
2. **默认让 `grep` 先自动 refresh repository**
   - `grep` 默认使用 `/root/.local/share/opencode/opencode.db`
   - 单独 `compile` 主要用于显式准备仓库或做离线搜索
3. **再做 `grep`**
   - 不直接扫原始历史
   - 不把 `show` 当搜索器
4. **最后 `show`**
   - 只对值得继续看的命中结果回跳完整上下文

## skill 应明确告诉模型的边界

### 1. 不搜索 `system`

`system` 从 compiled repository 边界上就已经被排除，不是“可以搜到但默认不显示”。

### 2. 不直接 grep SQLite

查询历史的默认路径应当是：

- compile upstream history → compiled repository
- 在 compiled repository 上 grep

### 3. `show` 不是搜索器

`show` 只负责根据已知 anchor 回跳完整上下文。

### 4. 先筛范围，再搜索

目录筛选和时间筛选优先于 grep，避免结果过宽。

## 示例调用风格

### 情况 1：当前项目里找旧问题

```bash
opencode-history-grep grep --repository .opencode-history-grep --directory /root/_/opencode --query "sqlite history"
```

### 情况 2：只查一段时间内的历史

```bash
opencode-history-grep grep --repository .opencode-history-grep --since 2026-04-01 --until 2026-04-23 --query "tool_result"
```

### 情况 3：看到命中后回跳

```bash
opencode-history-grep show --repository .opencode-history-grep --session <session-id> --anchor <block-id>
```

## 对 skill 文本的要求

skill 正文应清楚写出：

- CLI 的三个主命令：`compile / grep / show`
- 目录筛选参数
- 时间筛选参数
- regex 参数与跨行语义
- 分页参数
- 类型多选筛选参数
- `show --all / --before / --after / --full-text`
- 何时必须先 compile
- 何时应该先收窄范围而不是直接 grep
- 结果命中后为什么要 `show`

## 成功标准

这个 skill 写完后，应能让模型在以下场景稳定做对：

1. 用户说“帮我找这个项目以前讨论过的 X”时，知道优先加目录筛选
2. 用户说“帮我找上周关于 Y 的历史”时，知道优先加时间筛选
3. 模型不会退回普通 grep 或直接扫 SQLite 文本
4. 模型知道先 grep，再对重点结果 show，而不是盲目展开整段历史
