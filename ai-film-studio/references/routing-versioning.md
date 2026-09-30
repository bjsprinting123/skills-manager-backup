# Routing / Versioning / Upgrade

## Router 只决定“谁来做”

Router 不拥有创作正文。它根据用户当前真正拥有的材料与目标，选择最短合法路径。

- 灵感／经历 → Source/Adaptation
- 小说／长篇 → Source/Adaptation
- 已有大纲 → Story/Screenplay
- 已有完整剧本 → Director，可直接 screenplay takeover
- 已有导演方案 → Visual / Shot
- 只有资产或分镜问题 → Assets / Shot
- 只要某模型提示词 → 对应 Provider Adapter
- 已有生成媒体 → Production / Review / Post

**跳阶段合法；伪造上游不合法。**

## Version state

- draft：尚未接受，可自由改。
- accepted：当前权威版本；仍可通过新版本修改。
- stale：依赖的上游已变化，不能继续冒充当前有效。
- retired：历史保留，不参与当前决策。

“已确认”不是永久锁死，只是当前 Source of Record。

## Impact propagation

上游改动只污染真正依赖它的下游。例如 Performance v2→v3，可让 Performance Bible、依赖该表演的 Shot Spec 与对应 Provider Prompt stale，但不自动污染 Screenplay、Character identity、Location assets 或 Visual Bible。

## Human Gate

LOW：格式、引用、无语义变化的机械修复；自动执行并记录。

MEDIUM：局部拆镜、局部换 Provider、局部返工；可先形成候选，再报告影响。

HIGH：改结局、主角、POV、Director Bible 核心、Visual Bible 核心，或 Promote 新 Capability；执行前确认。

## Upgrade classification

新东西默认先进入 Candidate，再分类为 Knowledge、Recipe、Capability implementation、Provider/Model 或 Architecture change。

证据等级：E0 宣传/转述；E1 已读原文；E2 有案例；E3 有本地机械验证；E4 真实项目重复验证；E5 多项目/多 Provider 重复验证。

结构测试通过不等于媒体质量通过。

## Protected anchors

1. unknown 不补成事实。
2. Prompt/计划不等于已有媒体。
3. 工具成功不等于媒体质量通过。
4. Provider 不拥有 Story/Director/Visual。
5. Reference 必须声明职责。
6. world coordinate 不等于 screen-left/right。
7. accepted 内容修改要建新版本。
8. Reviewer 默认只写 finding。
9. Candidate 不自动替代 CURRENT。
10. ComfyUI 继续人工执行，除非用户明确改变。

