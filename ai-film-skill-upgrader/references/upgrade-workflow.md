# 标准升级工作流

## 1. DISCOVER

接受来源：

- GitHub / Git 仓库；
- 官方文档 / Changelog；
- 博主视频、文章、飞书；
- 用户提供的 Skill / Prompt / 方法；
- 真实项目失败案例；
- 新模型 / Provider 版本。

先回答：它声称解决什么问题？不要先回答“要不要装”。

## 2. INGEST

尽可能读一手材料：

- 源码优先于 README 宣传；
- 官方 release note 优先于二手转述；
- 完整视频/转写优先于标题；
- 真实失败媒体优先于 Prompt 自述。

记录未读到的部分，不用推测补齐。

## 3. CLASSIFY

先决定属于：

- knowledge；
- recipe；
- capability_implementation；
- provider_model；
- architecture_change。

如果一个来源同时包含多类内容，拆成多个 Candidate / Diff，不把整个仓库一口吞进 CURRENT。

## 4. PROVENANCE

至少记录：

- source id；
- author / repository；
- URL 或本地来源；
- version / commit / date；
- license；
- evidence type；
- 已读范围；
- 未验证范围。

公开/第三方长文本不要整段复制进正式 Skill；吸收可复用方法、结构和短摘要。

## 5. DIFF

对 CURRENT 输出：

~~~text
ADD
MODIFY
REMOVE
CONFLICT
MODEL_ONLY
KNOWLEDGE_ONLY
NO_CHANGE
~~~

必须指出 owner：

~~~text
Source
Story
Director
Visual
Shot
Performance
Assets/Continuity
Production
Review
Post
Provider
System Upgrade
~~~

## 6. SANDBOX

候选实现不得先覆盖 CURRENT。

Sandbox 里允许：

- 独立 reference；
- 独立候选 Skill；
- Candidate JSON；
- 临时 benchmark 输出。

## 7. BENCHMARK

### B1 Structural

文件、Schema、链接、边界、静态门禁。

### B2 Semantic

职责是否正确、是否保留用户意图、是否产生跨层 ownership leak。

### B3 Feasibility

当前执行面是否能实际使用；成本、参考、模型限制、fallback。

### B4 Media

真实图片/视频结果。

### B5 User Acceptance

用户实际接受。

B4/B5 未跑必须显式写 not-run。

## 8. REVIEW

检查：

- Protected Anchors；
- 是否退化其他场景；
- 是否把 Recipe 错升为硬规则；
- 是否污染 Provider 边界；
- 是否需要版本升级；
- rollback 是否真实可执行。

## 9. APPROVE / RELEASE

审批和发布分开。

Capability 使用：

~~~text
DRY_RUN
→ APPROVED_PENDING_RELEASE
→ --approved --release
~~~

Knowledge / Recipe / Provider / Architecture 按各自 release matrix 处理。

## 10. IMPACT

发布后回答：

- 哪些 Capability 改了；
- 哪些 artifact 需要 stale；
- 哪些项目可继续复用；
- 是否需要重新生成 Provider Prompt；
- 是否需要 B4/B5 回归。

## 11. DEPLOY / VERIFY

检查 Git、中央库、目标 Agent。

部署成功不代表媒体质量通过。

## 12. ROLLBACK

若发现退化：

- 恢复上一个 CURRENT；
- Candidate 标记 suspended / rejected；
- 保留失败证据；
- 不删除历史，让后续升级知道为什么回滚。

