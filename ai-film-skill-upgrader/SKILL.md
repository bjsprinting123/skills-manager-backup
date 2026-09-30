---
name: ai-film-skill-upgrader
description: AI短剧/AI影视 Skill 体系的专用学习与升级管理员。用户要求“吸收这个新知识/新视频/新GitHub Skill/新模型版本/失败案例”“升级我们的短剧Skill”“把这个纳入体系”时使用。负责读取 CURRENT、分类、Provenance、Diff、Sandbox、固定回归、审批、Release、Impact、Skills Manager 部署与回滚；不参与普通影视项目创作，不维护第二套状态。
metadata:
  version: "0.1.0"
---

# AI Film Skill Upgrader

这是 E:\AI短剧 的系统维护入口，不是创作入口。

先按需读取：

- [标准升级工作流](references/upgrade-workflow.md)
- [分类、规则级别与证据](references/classification-evidence.md)
- [发布、部署、影响与回滚](references/release-rollback.md)
- [Sources / Provenance](references/sources.md)

## 唯一真源

不得在本 Skill 内维护第二套 Registry / Upgrade State。

正式状态只认：

~~~text
E:\AI短剧\技能仓库\system\registry\
E:\AI短剧\技能仓库\system\upgrade\
E:\AI短剧\技能仓库\system\knowledge\
E:\AI短剧\技能仓库\system\benchmarks\
E:\AI短剧\技能仓库\system\tools\
~~~

正式 Skill 实现只认：

~~~text
E:\AI短剧\技能仓库\skills\
~~~

## 何时触发

以下请求进入本 Skill，而不是 ai-film-studio：

- “这个新 Skill 值不值得吸收？”
- “把这个 GitHub 项目纳入我们的短剧体系。”
- “这个博主新视频里有新方法，更新一下。”
- “H3 / Krea / Seedance / 其他 Provider 出新版了。”
- “这次真实项目反复失败，把经验沉淀成规则。”
- “升级 film-director / film-shot-director / 表演 / 连续性等能力。”
- “检查我们的短剧 Skills 是否需要更新。”

普通拍片、写剧本、分镜、生成 Prompt 不触发本 Skill。

## 固定升级链

~~~text
DISCOVER
→ INGEST
→ CLASSIFY
→ PROVENANCE
→ DIFF
→ SANDBOX
→ BENCHMARK
→ REVIEW
→ APPROVE
→ RELEASE
→ IMPACT
→ DEPLOY
→ VERIFY
→ ROLLBACK（必要时）
~~~

任何阶段都允许结论为：

- REJECTED
- KNOWLEDGE_ONLY
- RECIPE_ONLY
- SUSPENDED
- NEEDS_REAL_MEDIA

“发现了新东西”不等于“必须升级”。

## 五类入口

| classification | 典型内容 | 默认落点 |
|---|---|---|
| knowledge | 专业知识、方法解释、反例 | system/knowledge 或对应 Skill reference |
| recipe | 有适用条件的镜头/表演/动作/美术做法 | Recipe Library |
| capability_implementation | 可替换现有 Capability 的实现 | Sandbox → Benchmark → Promote |
| provider_model | 新模型、新版本、新方言、新限制 | Provider Registry / Adapter |
| architecture_change | 现有职责模型表达不了的新责任 | Architecture Migration；最高风险 |

## Candidate 必须先于 CURRENT 修改

每个正式候选先建：

~~~text
system/upgrade/candidates/<candidate_id>.json
~~~

使用 system/upgrade/candidate-template.json。

在本项目环境中，可用随 Skill 部署的：

~~~text
scripts/upgrade_candidate.py
~~~

创建/校验 Candidate。它只写 system/upgrade/candidates，不修改 CURRENT。

Candidate 至少记录：

- source / version / date；
- license；
- capability IDs；
- classification；
- evidence level；
- ADD / MODIFY / REMOVE / CONFLICT；
- benchmark；
- protected anchor check；
- impact；
- rollback；
- B4 / B5 状态。

在 Candidate / Diff / Review 完成前，禁止直接改 CURRENT。

## Release 分流

### Knowledge / Recipe

只更新知识/Recipe及 provenance；除非行为默认或合同发生变化，否则不自动升级 Core Skill 版本。

### Capability Implementation

使用正式控制器 system/tools/capability_upgrade.py。

三态严格区分：

- 无批准：DRY_RUN
- 已批准但未发布：APPROVED_PENDING_RELEASE
- 明确 --approved --release：才允许修改 CURRENT

### Provider / Model

只修改 Provider Registry、Provider Adapter 和必要的模型专用参考；不得把模型限制反写成 Story / Director / Visual 的全局规则。

### Architecture Change

必须单独输出 Architecture Migration Proposal，并取得用户明确批准。不得复用普通 Capability Promote 冒充架构迁移。

## Benchmark

任何会改变影视创作行为的升级，至少检查固定 5 类：

1. 双人文戏；
2. 多人室内；
3. 动作追逐；
4. 复杂打斗；
5. 情绪长对白。

不能只拿候选作者自己的 Demo 证明“更好”。

## 真实媒体边界

- B1/B2/B3 通过 ≠ B4 媒体质量通过。
- B4 通过 ≠ B5 用户接受。
- Prompt / task success / render success 都不是用户审美验收。
- ComfyUI / 实际媒体生成继续由用户人工执行，除非用户明确改变这一边界。

## 发布后

必须检查：

1. system/registry 与 system/upgrade/state.json；
2. Git commit / origin/main；
3. Skills Manager 中央库；
4. 目标 Agent 部署；
5. 已有项目的 impact / stale；
6. 是否需要 B4/B5 继续验证。

## 输出格式

每次升级任务至少输出：

~~~text
Upgrade Candidate:
Classification:
Source / Version / License:
Evidence Level:
Affected Capability:
CURRENT Diff:
Protected Anchor Result:
Benchmark Result:
B4/B5:
Decision:
Approval Needed:
Release Status:
Impact / Stale:
Rollback:
~~~

## 禁止

- 禁止看到新资料就直接覆盖正式 Skill。
- 禁止把 Creator Recipe 提升成 STRUCTURAL_INVARIANT，除非证据支持。
- 禁止因为一个 Provider 做不到就改写电影语言。
- 禁止把宣传、Demo 或单次成功写成 E4/E5。
- 禁止在没有用户明确批准时执行正式 Release。
- 禁止维护本 Skill 私有的 CURRENT / Registry / Upgrade State。
- 禁止把 3-工作区 或历史 4-迁移记录 当运行时真源。

