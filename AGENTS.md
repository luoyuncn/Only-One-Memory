1. 始终保持中文语言习惯
2. 每次发生一些编程相关的变动，记得同步AGENTS.md
3. 尽可能减少显示配置项
4. env example每次发生变动主动更新

## 开发同步

- 2026-05-19：V0.2 主线新增 L1 prompt/JSON 解析、embedding/RRF、L1 store 契约、L1 抽取/写入、recall API 与最小 pipeline trigger。
- 2026-05-19：并行落地 V0.3 checkpoint 基础、V0.4 scene Markdown 基础、V0.5 offload ref 文件存储基础、V0.6 audit 基础。
- 2026-05-19：继续推进 V0.3，新增 L1 flush、L2/L3 最小调度、checkpoint 文件持久化、Postgres pipeline job 基础、worker 入口与 admin pipeline 状态接口。
- 2026-05-19：收口 V0.3，接入 MemoryCore checkpoint 恢复/保存、admin reindex 计数、pipeline idle flush、worker job complete/fail 生命周期。
- 2026-05-19：补齐 V0.2 OpenAI-compatible LLM runner 与 FTS+vector RRF hybrid recall；开始并推进 V0.4，新增场景工具沙箱、场景抽取、人设生成、场景/画像 API 与 TencentDB-Agent-Memory 归因文档。
- 2026-05-19：V0.4 验收收口，新增场景导航块、Persona 生成导航追加、SceneExtractor 到 L2 store 同步，以及场景 PATCH/GET 验收测试。
- 2026-05-19：使用 executing-plans 执行 V0.5，新增 Offload refs/restore API、entries 持久化、Mermaid 图、compressor helper 与 node_id restore 端到端链路。
- 2026-05-19：开始执行 V0.6，新增可选 API key 配置并保护 admin API，未配置 key 时保持本地开发开放。
- 2026-05-19：V0.6 继续新增审计日志持久化契约，SQLite/Postgres 均增加 audit_logs 表与查询能力。
