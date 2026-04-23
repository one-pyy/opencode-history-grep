# opencode-history-grep — vendor baseline 布局

状态：**已落地**

## 结论

VCC baseline 已经正式落到本项目目录，不再只是文档中的口头参考。

当前 vendor 路径：

- `my_plugins/opencode-history-grep/vendor/vcc_baseline/`

## 当前落入的最小文件集

- `vendor/vcc_baseline/README.md`
- `vendor/vcc_baseline/INSTALL.md`
- `vendor/vcc_baseline/skills/conversation-compiler/SKILL.md`
- `vendor/vcc_baseline/skills/conversation-compiler/scripts/VCC.py`
- `vendor/vcc_baseline/VENDOR.md`

## 为什么只落这几份

因为当前项目真正需要的 baseline 只有两层：

1. **产品行为层**
   - VCC 到底产出哪些视图
   - 搜索结果长什么样

2. **编译核心层**
   - `VCC.py` 具体如何做清洗、分块、降噪和输出

其余 Claude 专属 skill 目前不是实现本项目所必需的，因此先不引入，避免 vendor 目录里堆太多无关内容。

## 这对项目意味着什么

从现在开始，本项目可以明确说：

- VCC 是已落地的 vendor baseline
- 我们不是只在概念上参考它
- 后续实现时，任何“保留什么 / 改造什么”的讨论都可以直接对照这批文件展开

## 后续使用规则

### 可以直接参考的层

- `README.md` 里的视图目标
- `SKILL.md` 里的 compile/search workflow
- `VCC.py` 里的编译与清洗主干逻辑

### 不能直接照搬的层

- Claude JSONL 输入
- `.claude/skills` 宿主假设
- Claude 命令语义

### 推荐做法

后续真正落实现时：

- 在 `src/opencode_history_grep/` 下写本项目自己的代码
- 让 vendor baseline 保持为上游对照物
- 不把项目代码直接堆进 vendor 目录
