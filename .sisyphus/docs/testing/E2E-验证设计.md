# opencode-history-grep — E2E 验证设计

状态：**已实现核心路径，交互层待继续扩展**

## 目标

这份文档定义第一版正式 E2E 验收路径，验证本项目是否真的实现了“基于 upstream SQLite 的全 session 编译式 grep”，而不是只完成了局部模块。

E2E 关注的不是单个函数是否工作，而是完整用户路径是否成立：

1. 从 upstream SQLite 读取真实历史
2. 编译到本项目自己的 compiled repository
3. 在 compiled repository 上执行 grep
4. 用 show 回到完整上下文

## 验收边界

### 本 E2E 必须覆盖的系统行为

- 全 session compile
- block-aware grep
- 高信号 `match` 输出
- anchor 回跳
- `tool_call` 参数保留规则
- `tool_result` 截断规则
- `system` 排除规则

### 本 E2E 不负责的内容

- 性能极限优化
- Web/TUI 展示
- Claude JSONL 兼容
- 向量检索

## 样本策略

### 基础抽样

从 upstream SQLite 的真实历史中，随机抽取 **50 条原始记录** 作为第一层样本。

这里的“原始记录”指进入 reader 层之后、尚未进入 block compiler 之前的真实上游历史单元。

### 覆盖要求

这 50 条不是为了“随机就好”，而是为了覆盖会进入搜索域的主要来源。

目标覆盖：

- `user`
- `assistant`
- `tool_call`
- `tool_result`
- `compaction`
- `subtask`

### 补齐规则

如果纯随机的 50 条没有覆盖上述所有主要来源类型，则必须补定向样本，直到覆盖完成。

这意味着 E2E 的规则不是：

- 只随机一次，没抽到就算了

而是：

- **先随机抽样，再补足低频来源**

原因：

- `subtask`、`compaction` 等类型在真实历史里可能是低频项
- 如果不补齐，E2E 会虚假通过，只证明“常见文本类型没坏”

## 固定验证步骤

### Step 1：抽样与来源确认

验证目标：

- 样本确实来自 upstream SQLite
- 样本包含主要搜索域来源类型
- `system` 样本如果出现，只能作为“过滤验证样本”，不能进入编译仓库

通过信号：

- 测试日志中明确列出样本来源分布
- 缺失来源会触发补样流程

### Step 2：执行 compile

验证目标：

- 属于搜索域的样本能稳定进入 compiled repository
- `system` 不进入 compiled repository

通过信号：

- 编译后仓库中存在对应 session 的 compiled 产物
- 仓库中不存在 `system` block

### Step 3：执行 grep

验证目标：

- grep 在 compiled repository 上执行，而不是回读原始 SQLite 现拼
- 返回结果是 block 级结果，不是原始行级 dump

通过信号：

- 结果包含 block 类型、命中片段、anchor
- 同一 block 多重命中不会刷屏

### Step 4：验证 tool 规则

验证目标：

- `tool_call` 默认保留调用参数
- `tool_result` 默认截断
- 如果工具输出包含 grep 命中，只保留命中附近局部窗口

通过信号：

- 至少有一个 `tool_call` 结果可见参数
- 至少有一个 `tool_result` 命中被截断显示，而不是整段展开

### Step 5：验证 system 排除规则

验证目标：

- `system` 完全不进入 compiled repository
- `grep` 结果中不存在 `system`
- `show` 回跳上下文时也不会因为完整视图而重新混入 `system`

通过信号：

- 编译结果中无 `system` block
- 搜索结果中无 `system` block
- show 输出中无 `system` block

### Step 6：执行 show

验证目标：

- grep 返回的 anchor 能稳定回跳
- 回跳结果能让人看懂命中的完整上下文

通过信号：

- 每个抽查命中都能用 anchor 打开完整上下文
- 打开的上下文与 grep 命中 block 一致

## 核验点清单

E2E 通过前，至少要确认以下事实全部成立：

1. compile 可以处理真实 upstream 历史
2. 编译后的最小单位是 block，不是行文本
3. grep 默认跨 session 生效
4. 结果默认是高信号 `match`，不是原始记录倾倒
5. `tool_call` 保留参数
6. `tool_result` 默认截断，命中时只保留局部窗口
7. `system` 不进入 compiled repository，也不进入 grep / show 结果
8. grep 结果可以通过 anchor 回到完整上下文

## 失败判定

以下任一情况出现，都应判定 E2E 失败：

1. 50 条随机样本后没有执行补样，导致来源覆盖不完整
2. grep 结果仍像原始日志转储，而不是 block-aware 结果
3. `tool_result` 命中后整段大输出直接泄到结果页
4. 任意阶段出现 `system` block
5. anchor 不能稳定回跳

## 建议实现方式

这条 E2E 已适合落成真实自动化测试路径，而不是停留在人工检查说明。

建议拆成两层：

1. **测试数据准备层**
   - 从 upstream SQLite 抽样
   - 统计来源覆盖
   - 自动补齐低频来源

2. **完整流程验证层**
   - compile
   - grep
   - show
   - 验证 block 类型、输出规则和 system 排除边界

## 这条 E2E 的意义

这条 E2E 不是附属检查，而是本项目第一版最重要的完成证明。

如果它不能通过，就说明以下至少有一个没有真正成立：

- reader 没有读对真实 upstream 历史
- compiler 没有把历史稳定编译成 block
- grep 没有提供高信号结果
- block 边界规则没有真正落地
- `system` 排除规则只是口头约定
