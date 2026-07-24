# opencode-history-grep — history recall skill 设计

状态：**已实现**

## 目标

这份文档描述一个给模型使用的 skill：让模型学会如何调用 `opencode-history-grep` 的 CLI 查询历史记录和读取有边界的 session 证据，而不是直接重扫原始 SQLite、退回普通文本 grep 或用格式化 session 摘要替代 block 证据。

固定默认路径：

- upstream DB：`/root/.local/share/opencode/opencode.db`
- compiled repository：`/root/.local/share/opencode-history-grep`

对外话术应收口为：

- **日常搜索：直接 `grep`**
- **`grep` 和 `show` 都会自动 compile / refresh，一般无需手动 `compile`**
- **显式备库 / 离线准备 / 范围受控仓库：才单独用 `compile`**

默认推荐的类型筛选应优先教：

- `--type user`
- `--type assistant`

`tool_call` / `tool` 作为补充说明，不作为默认主推荐路径。

还应明确告诉模型：如果结果过宽，优先建议用户加 `--type assistant`、`--since/--until`，或把 query 改成更精确短语 / `--regex`。

还应明确告诉模型：当前 `grep` 本质上是文本匹配，不是语义检索；如果第一次没命中，不要只换筛选条件，也应主动尝试不同但相近意思的词、常见同义表达，必要时切换中英文关键词重搜。

## 这个 skill 要教会模型什么

模型应学会六件事：

1. 何时直接 `grep`
2. 何时才需要单独 `compile`
3. 何时用目录筛选缩小 session 范围
4. 何时用时间筛选缩小 session 范围
5. 何时用 `show` 回跳完整上下文
6. 已知 `session_id` 时如何用 `--from` / `--to` 固定审查边界，并用 `--block` 回源读取完整原始内容

## 推荐工作流

这部分参考 VCC 的价值，不是照搬 VCC 的命令：

1. **先确认范围**
   - 是否应按当前项目目录筛选；`--directory` 的语义是“匹配当前目录本身，或以该目录为前缀的所有子目录”
   - 如果当前项目路径不明确，就不要指定 `--directory`，否则可能因为过滤过窄而搜不到本来存在的命中
   - 是否应按用户提到的时间窗口筛选
2. **默认让 `grep` / `show` 先自动 refresh repository**
    - `grep` 和 `show` 默认使用 `/root/.local/share/opencode/opencode.db`
    - 单独 `compile` 主要用于显式准备仓库或做离线搜索
3. **再做 `grep`**
    - 不直接扫原始历史
    - 不把 `show` 当搜索器
   - 因为当前 `grep` 使用文本匹配，query 应多尝试近义词、不同说法和关键词组合
   - 如果用户当前明确用英文沟通，默认先搜英文；如果上下文里有中文使用迹象，再补搜中文 / 英文两组词
4. **最后 `show`**
   - `show` 也应先自动 compile / refresh，避免回看已知 session 时读到旧 compiled view
   - 只对值得继续看的命中结果回跳完整上下文
5. **审查已知 session 时直接读取边界**
    - 已知 `session_id` 时不重新搜索 session
    - Oracle candidate 模式第一阶段只读到 source boundary；第二阶段才读取 candidate evidence
    - Oracle session 模式第一阶段使用 `--type 'user' --type 'assistant' --from 'text:<source-start>' --to 'text:<source-boundary>'` 读取严格受限的可见对话；assistant 内容只在用户明确接受后成为契约，第二阶段才读取 bounded full execution evidence
    - `current_session_id` 的 bare `message_id` 不是 range endpoint；调用方把返回的 `session_id` 作为带引号的 `--session` 值，并把唯一 marker 直接作为带引号的 `text:<literal>` all-block endpoint
    - `text:` 在 `--type` 过滤后执行区分大小写的字面子串匹配，只允许唯一命中；零命中或多命中时失败，再用 `grep` 查看候选并选择完整 block id
    - endpoint 是 tool result marker 时使用 `--type 'all'`，避免先按 message 类型过滤后丢失边界
    - Session Phase 1 的 source start/to 原文摘录各至少 20 个字符；消息不足 20 个字符时使用整条消息。即使歧义后改用 block id，调用包仍保留该原文
    - `question` 工具中的用户选择原生保存在 completed tool result；编译视图将它标成 `user_decision`，因此 `--type user` 自动保留问题 input、选项说明和用户答案，同时不会纳入其他 tool result
    - `--type assistant` 将同一 assistant message 的可见 text parts 按创建时间合并为一个 block；不包含 reasoning/system/tool 内容，也不声称保留 text 与 tool 的交错顺序
    - 已接受 source docs 由 caller 提供精确 path、accepted ref/block 和接受证据；Phase 1 不宽泛读取 tool，仅在精确版本无法恢复时定向读取对应写入 block
    - 无法定位干净的候选前边界时，明确标记为 candidate-exposed retrospective review

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
session_id='<provided session_id>'
opencode-history-grep show --repository '.opencode-history-grep' --session "$session_id" --anchor '<block-id>'
```

## 对 skill 文本的要求

skill 正文应清楚写出：

- CLI 的三个主命令：`compile / grep / show`
- 目录筛选参数：`--directory` 匹配当前目录本身，或以该路径为前缀的所有子目录；如果项目路径不明确，不应指定这个参数
- 时间筛选参数
- regex 参数与跨行语义
- 分页参数
- 类型多选筛选参数
- `show --all / --before / --after / --full-text`
- `show --from / --to / --block` 的 inclusive block 边界、quoted `text:<literal>` 唯一匹配与 raw recovery 语义；`user`/`message`/`tool_result`/`tool`/`all` 视图均按各自语义保留 `user_decision`
- `show --type user` / `--type assistant` 的角色过滤，以及 session 模式 bounded user+assistant Phase 1 → all-block Phase 2 的顺序
- 按 `session_id` 做 Oracle candidate/session review 时必须使用该 skill
- 何时必须先 compile
- 何时应该先收窄范围而不是直接 grep
- 当前 grep 是文本匹配，因此 query 需要主动尝试近义词、不同措辞与中英文变体
- 结果命中后为什么要 `show`

## 成功标准

这个 skill 写完后，应能让模型在以下场景稳定做对：

1. 用户说“帮我找这个项目以前讨论过的 X”时，如果项目路径明确，知道优先加目录筛选；如果项目路径不明确，知道先不要加 `--directory`
2. 用户说“帮我找上周关于 Y 的历史”时，知道优先加时间筛选
3. 模型不会退回普通 grep 或直接扫 SQLite 文本
4. 模型知道先 grep，再对重点结果 show，而不是盲目展开整段历史
5. reviewer 已知 session 和边界时直接使用 bounded `show`，不会在 candidate Phase 1 提前读取候选，也不会把 session Phase 1 中未被接受的 assistant 自述或工具执行当作契约
