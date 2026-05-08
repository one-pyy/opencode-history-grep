# opencode-history-grep — upstream 历史存储调研

状态：**已调研**

## 结论

opencode upstream 的历史记录**不是** Claude Code 的 `~/.claude/projects` JSONL。

它使用的是自己的历史模型与存储链路：

- SQLite 数据库作为主存储
- `session` / `message` / `part` 作为核心历史结构
- 服务端 API 与内部读取逻辑都围绕这套结构展开

因此，`opencode-history-grep` 第一版的输入层应当优先面向 upstream 自己的历史记录，而不是围绕 Claude JSONL 兼容性设计。

## 关键证据

### 1. 主数据库存在且默认落到 opencode 自己的数据目录

文件：`/root/_/refs/opencode-upstream/packages/opencode/src/storage/db.ts`

确认点：

- 默认数据库文件名是 `opencode.db`
- 路径位于 `Global.Path.data`
- 启动时初始化 SQLite 并执行 migration

这说明 upstream 有自己的持久化数据库，而不是依赖外部聊天日志文件。

### 2. 历史结构由 session/message/part 三张核心表定义

文件：`/root/_/refs/opencode-upstream/packages/opencode/src/session/session.sql.ts`

确认点：

- `SessionTable`
- `MessageTable`
- `PartTable`

`MessageTable` 存消息 info，`PartTable` 存消息 part。历史记录不是一条扁平文本流，而是结构化记录。

### 3. 历史数据通过 projector 落表

文件：`/root/_/refs/opencode-upstream/packages/opencode/src/session/projectors.ts`

确认点：

- `Session.Event.Created/Updated/Deleted` 写 `SessionTable`
- `MessageV2.Event.Updated` 写 `MessageTable`
- `MessageV2.Event.PartUpdated` 写 `PartTable`

这说明历史库是 upstream 正式事件投影产物，不是临时缓存。

### 4. 历史读取已有正式 API 与内部读取函数

文件：

- `/root/_/refs/opencode-upstream/packages/opencode/src/session/message-v2.ts`
- `/root/_/refs/opencode-upstream/packages/opencode/src/server/routes/instance/session.ts`

确认点：

- `page({ sessionID, limit, before })` 负责分页读取历史消息
- `stream(sessionID)` 负责迭代整段历史
- `get({ sessionID, messageID })` 负责读取单条消息
- `hydrate(...)` 负责将 message 与 part 组装回 `{ info, parts }`
- 服务端公开了 `GET /session/:sessionID/message` 等接口

这意味着第一版工具可以有两种合法输入路径：

1. 直接读 SQLite
2. 调 upstream session/message API

## 对本项目的影响

### 已确定

1. 第一版不把 Claude JSONL 当作主输入
2. 第一版可以直接建立在 upstream 原生历史之上
3. “先编译，再检索”的方向是成立的，因为 upstream 本身已经提供结构化历史底座

### 尚未确定

1. 第一版优先走 SQLite 直读，还是走 HTTP/API 读取
2. 编译产物是否要长期缓存
3. 多 session 搜索第一版是否进入范围

## 当前建议

第一版优先做：

- 单 session 历史读取
- 编译成 block 视图
- 对 block 视图做搜索与概要输出

暂时不要在第一版同时解决：

- 跨 session 聚合索引
- 自动增量同步
- Claude JSONL 兼容层
