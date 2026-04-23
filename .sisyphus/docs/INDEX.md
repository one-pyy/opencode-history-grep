# opencode-history-grep — Docs Index

Project: /root/_/opencode/my_plugins/opencode-history-grep
Purpose: 记录基于 opencode upstream 历史记录的编译式检索 CLI 工具设计、输出格式与实现约束。

## Summary

当前文档覆盖的是一个面向 opencode upstream SQLite 历史的编译式检索系统：核心形态是“库优先 + CLI 外壳”，重点已经收敛到全局默认 DB / repository、自动 refresh 的 `grep`、分页与类型筛选、regex / 跨行查询、`show` 回跳，以及给模型调用的 skill 工作流。涉及结果编译、搜索输出、目录筛选、时间筛选、全局安装刷新或 skill 调用方式时，应优先阅读本目录。

---

## Planning

[planning/功能定位.md] — 未实现：工具目标、非目标与系统级能力边界
[planning/版本边界与长期路线.md] — 未实现：完整系统目标下的阶段划分与演进路线
[planning/实施计划.md] — 未实现：围绕库优先 + 全 session 编译检索的正式工作计划
[planning/任务拆分计划.md] — 未实现：按 reader / compiler / repository / search / CLI / testing 分层拆解的执行计划

## Research

[research/upstream-history-storage.md] — 已调研：opencode upstream 历史使用 SQLite `session/message/part`，不是 Claude JSONL
[research/vcc-baseline-and-adaptation.md] — 已调研：VCC 应作为 baseline 纳入，并明确区分可直接参考层与必须改造层
[research/vendor-baseline-layout.md] — 已落地：VCC baseline 已 vendor 到项目目录，并固定最小文件集与使用规则

## Compiled Views

[compiled-views/视图编译设计.md] — 未实现：从 opencode session/message/part 到 block 视图的编译规则

## CLI

[cli/命令设计.md] — 未实现：Python CLI 命令、输入输出与结果呈现约定
[cli/筛选设计.md] — 已设计：目录筛选与时间筛选的输入语义、作用边界与命令映射

## Skills

[skills/history-recall-skill.md] — 已设计：教模型如何用本项目 CLI 编译、搜索并回看历史记录的 skill 约定

## Testing

[testing/E2E-验证设计.md] — 未实现：基于真实 upstream SQLite 的 50 条抽样 + 补样 E2E 验收设计
