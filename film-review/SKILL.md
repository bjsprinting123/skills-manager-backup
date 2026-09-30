---
name: film-review
description: 独立、只读地审查AI影视项目：可审故事剧本、导演/视觉、分镜与可行性、实际Take、连续性和完整序列。每个finding给位置、证据、影响、必须达到的修订结果和owner；默认不在同一轮替owner改源文件。
metadata:
  version: "0.1.0"
---

# Film Review

先读[Review Contract](references/review-contract.md)；来源见[Sources](references/sources.md)。

## 独立性

优先由未参与当前版本创作的 reviewer 执行。

同一上下文自检必须写明：

`SELF-AUDIT`

不得冒充独立 Cold Read。

## Scope

### Creative
- source/adaptation；
- story/script；
- director；
- visual/sound intent。

### Feasibility
- shot/blocking；
- reference readiness；
- duration/action load；
- provider capability；
- cost/fallback。

### Take
- identity；
- wardrobe/prop；
- action/end state；
- anatomy/physics；
- camera；
- lighting；
- audio。

### Sequence / Final
- splice continuity；
- geography/eyeline；
- rhythm；
- emotional carry；
- sound bed；
- color match；
- subtitles/graphics；
- delivery。

## Finding

每个问题必须有：

```text
finding_id
scope
severity
location
evidence
impact
required_result
owner
rule_level
```

不接受：

- “AI味重”；
- “不够电影感”；
- “感觉不高级”；

除非给出可观察证据和影响。

## Verdict

- APPROVE
- APPROVE_WITH_NOTES
- REVISE
- PROVISIONAL

媒体不可读时，对依赖媒体的结论只能 PROVISIONAL，不影响其他可证明 finding。

## Earliest Broken Decision

问题优先返回最早拥有它的 owner：

```text
Story
Director
Visual
Shot
Performance
Asset/Continuity
Provider
Take/Post
```

不要默认“视频不好 → 改 Prompt”。

## 禁止

- 不在审查同一轮直接覆盖被审 artifact。
- 不用总分掩盖 blocker。
- 不用机械测试冒充创作质量。
- 不把历史案例当当前媒体已经发生的事实。


