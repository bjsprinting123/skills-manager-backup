# 发布、部署、影响与回滚

## Release Matrix

| 类型 | 修改位置 | 是否必须 bump Core | 自动化 |
|---|---|---:|---|
| Knowledge | provenance / references | 否 | 人工审查后内容提交 |
| Recipe | recipe index / recipe reference | 通常否 | 人工审查后内容提交 |
| Capability | Skill + registry + upgrade state | 是/按 semver | capability_upgrade.py |
| Provider | provider registry + adapter | 视行为变化 | Provider release |
| Architecture | registry/contracts/skills/system | 是 | 独立迁移，不走普通 Promote |

## Capability 正式发布

前置：

1. Candidate 已完成；
2. Candidate 审计记录已经保存；
3. B1/B2 合格；
4. Protected Anchors 合格；
5. 需要的 B3 已说明；
6. B4/B5 状态明确；
7. Git 工作树 clean；
8. HEAD == origin/main。

正式控制器：

~~~powershell
python E:\AI短剧\技能仓库\system\tools\capability_upgrade.py validate
python E:\AI短剧\技能仓库\system\tools\capability_upgrade.py plan <candidate>
python E:\AI短剧\技能仓库\system\tools\capability_upgrade.py promote <candidate>
python E:\AI短剧\技能仓库\system\tools\capability_upgrade.py promote <candidate> --approved
python E:\AI短剧\技能仓库\system\tools\capability_upgrade.py promote <candidate> --approved --release
~~~

只有最后一条允许改 CURRENT。

## Knowledge / Recipe Release

知识/Recipe 默认不调用 Capability Promote。

流程：

1. Candidate + provenance；
2. 查重/冲突；
3. 更新 system/knowledge；
4. 必要时更新对应 Skill references/；
5. 跑 suite guard；
6. Git commit / push；
7. 如果 Skill 文件变化，刷新 Skills Manager；
8. 不改变 Capability version，除非默认行为/合同发生变化。

## Provider Release

必须区分：

- Provider facts；
- Adapter transform；
- upstream creative decision。

只允许前两类在 Provider release 中改变。

Provider runtime 参数易变时标记 verify-at-execution，不要写成永恒事实。

## Architecture Release

必须先有：

~~~text
Problem
Why current Capability Map cannot express it
New/changed owner
Artifact/contract impact
Migration plan
Backward compatibility
Regression plan
Rollback
Human approval
~~~

没有明确批准，不执行。

## Skills Manager

Git 发布成功后再刷新中央库。

当前 CLI：

~~~text
E:\tools\skills-manager\skills-manager-cli.exe
~~~

至少检查：

- source_type = git；
- source_ref 指向 bjsprinting123/ai-duanju-skills；
- 中央库与仓库逐文件一致；
- 目标 Agent deployed；
- preset membership 符合设计。

## Impact

Skill 更新后不要求所有项目重跑。

只标记真正依赖已改变决定的 artifact：

- upstream changed → downstream stale；
- Provider dialect changed → Provider Prompt 可 stale；
- Recipe 新增但 CURRENT 未变 → 既有项目通常不 stale；
- Architecture changed → 必须做显式 migration。

## Rollback

Rollback 不是删除候选。

至少保留：

- failed candidate；
- failure evidence；
- previous CURRENT；
- rollback commit / version；
- affected projects；
- 是否要撤销 Skills Manager deployment。

这样后续 Agent 不会再次重复同一个失败升级。

