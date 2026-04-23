# opencode-history-grep — VCC 基线与改造边界

状态：**已调研**

## 结论

VCC 不应该只作为“一个被抽象提到的思路”。

对本项目更合适的做法是：

**把 VCC 当作可直接纳入的 baseline（基线实现），然后明确区分：哪些层可以直接参考或 vendor 进来，哪些层必须按 opencode-history-grep 的目标改造。**

这里的 baseline 指的是：

- 它已经证明“先编译，再搜索”是可行的
- 它已经实现了多视图编译、block-aware 搜索、输出截断和上下文回跳这些核心能力
- 它的不足主要不在编译思想，而在输入来源、宿主环境、默认块规则和 CLI 目标与本项目不同

## 建议的纳入方式

### 不建议

- 把 VCC 只当灵感来源，完全重写所有核心层
- 继续在文档里只写“参考 VCC 风格”，但不说到底参考哪部分

### 建议

- 在本项目内新增一个明确的 `vendor/vcc_baseline/` 或等价目录，保存引入的 baseline 源
- 将 VCC 的编译核心视为可直接对照和迁移的上游参考
- 在本项目自己的 `reader / compiler / repository / search / cli` 层上定义改造边界

这样做的好处是：

1. 后续实现时不会一边说“像 VCC”，一边靠回忆猜它到底怎么做
2. 可以逐层判断“直接沿用”还是“明确改造”
3. review 时能直接看到哪些行为来自 baseline，哪些是我们自己的决定

## 可直接参考或 vendor 的部分

以下内容可以直接作为 baseline：

### 1. 多视图编译目标

来源：`VCC/README.md`

可直接参考：

- Full View
- Brief / Min View
- Search-focused View
- block range pointer 的思想

这些能力和本项目目标高度一致，不需要推翻。

### 2. 核心编译流水线思想

来源：`VCC/README.md`、`VCC.py`

可直接参考：

- lex / parse / lower / emit 的阶段化处理
- 先统一分块，再产出多个视图
- search view 建立在 full view 之上，而不是每次从原始历史现拼

这部分就是本项目的核心方法论基线。

### 3. block-aware grep 的输出目标

来源：`VCC/README.md`、`skills/conversation-compiler/SKILL.md`

可直接参考：

- 搜索结果按 block 返回
- 结果带角色标签
- 结果带可回跳定位
- 结果输出不是整段全文，而是命中片段 + block 范围

### 4. 文本清洗与工具输出整理的总体方向

来源：`VCC.py`

可直接参考：

- 清洗 ANSI/控制字符
- 把结构化 tool 参数转成更可读的文本
- 对冗余系统记录进行过滤
- 统一生成适合搜索的文本表示

## 必须改造的部分

以下部分不能直接照搬，必须按本项目需求修改。

### 1. 输入层：Claude JSONL → opencode upstream SQLite

这是最大的改造点。

VCC 当前输入是：

- Claude Code JSONL
- `.claude/skills`
- `~/.claude/projects`

本项目必须改成：

- upstream SQLite 直读
- 数据模型来自 `session / message / part`
- 编译前先完成 SQLite → 内部统一历史模型的读取层

### 2. 宿主层：Claude skills → 本项目核心库 + CLI

VCC 当前宿主形态是 Claude skills + Python script。

本项目必须改成：

- Python 核心库优先
- CLI 是外壳
- 不依赖 `.claude/skills`
- 不沿用 `/readchat` `/searchchat` `/recall` 这些命令语义

### 3. block 规则：不做 reasoning block

VCC 的示例结果里显式展示 thinking / reasoning。

本项目当前规则已经确定：

- **不单独暴露 reasoning block**

这意味着：

- VCC 在这部分不能直接照搬
- 对 upstream 历史里的相关信息，要么丢弃，要么并入别的摘要策略，但不作为独立 block 类型对外展示

### 4. tool 结果展示规则

VCC 的工具命中展示是“保留 block 范围 + 命中行”。

本项目要改成更明确的默认策略：

- `tool_call` 默认保留调用参数
- `tool_result` 默认截断输出
- 只有当 grep 命中 tool 输出时，才保留局部窗口
- 局部窗口规则固定为：
  - 上下各 5 行
  - 与前后各 500 字符比较
  - 实际取两者中更小的范围

这是本项目对 VCC baseline 的明确偏离。

### 5. 编译仓库层

VCC 默认是“对输入文件即时编译，即时输出旁边的 `.txt/.min.txt/.view.txt`”。

本项目必须改成：

- 全 session compiled repository
- 每个 session 的编译产物独立存放
- 有元数据支持后续刷新与增量重编译

这一层是本项目自己的新增系统层，不是 VCC 现成提供的。

## 推荐的分层对应关系

### 我们直接参考 VCC 的层

- compiler 的总体流水线
- full/min/search 三类视图思想
- block-aware 搜索结果形态
- 文本清洗与 tool 文本化思路

### 我们自己的层

- SQLite reader
- compiled repository
- 全 session compile 策略
- tool block 默认保留/截断规则
- CLI 命令语义

## 当前决策

从现在开始，项目文档不再写成“抽象参考 VCC”。

正式叙事改为：

**本项目以 VCC 作为 baseline，直接参考其编译与搜索思想，并在输入层、宿主层、block 规则和编译仓库层上做面向 opencode upstream 的定制改造。**
