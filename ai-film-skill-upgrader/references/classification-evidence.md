# 分类、规则级别与证据

## Classification

### knowledge

用于解释“为什么 / 怎么理解”。

示例：视觉开发与调色职责区别、对白话权、电影轴线、Sound Perspective。

默认不改变系统硬行为。

### recipe

有条件、可选择、可能因题材/模型而变化的做法。

示例：白模预演、遮挡切、某类打斗受力写法、某类镜头组合。

Recipe 必须写适用条件和不适用条件。

### capability_implementation

替换/升级现有稳定职责的实现。

例如新 Director Skill、新 Storyboard / Shot 设计器、新 Review 实现。

必须 Benchmark。

### provider_model

模型/Provider 专属：新模式、参数、token/tag、reference protocol、时长/分辨率、已知限制。

不得提升成全局电影规律。

### architecture_change

现有能力图无法正确表达的新职责、owner 或跨层合同。

最高风险；必须独立 Architecture Migration。

## Rule Level

### STRUCTURAL_INVARIANT

破坏就会让系统事实/职责失真。

例如：

- unknown 不得补成事实；
- Provider 不拥有 Story；
- accepted 变更必须新版本；
- review 不冒充 media proof。

### REVIEWED_INVARIANT

经过多来源/多案例复核，通常成立，但仍允许明确例外。

### CRAFT_DEFAULT

专业默认，不是法律。

### TASTE_OPTION

审美选择。

### RECIPE

条件式做法。

### MODEL_SPECIFIC

模型/Provider 方言和限制。

### EXPERIMENTAL

尚未获得足够证据。

## Evidence Level

### E0

宣传、标题、转述、未读原文。

### E1

已阅读一手源码/文档/完整材料。

### E2

作者案例或单一具体 case。

### E3

本地机械/语义验证，或固定回归 dry-run。

### E4

真实项目反复验证。

### E5

跨项目、跨 Provider 重复成立。

## 升级阈值

- E0/E1：可以进 Knowledge Inbox，不足以成为硬规则。
- E2：可以成为 Recipe Candidate。
- E3：可以考虑 Capability/Default 候选，但不能冒充媒体质量。
- E4：可以提升稳定生产方法。
- E5：才有资格讨论更高层通用性。

证据等级描述“我们知道到哪一步”，不代表审美评分。

