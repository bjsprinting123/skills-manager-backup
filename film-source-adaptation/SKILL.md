---
name: film-source-adaptation
description: 接入原创灵感、个人/他人经历、小说、历史纪实、既有大纲或剧本，建立可追溯Source Canon与改编边界；长篇可做章节/剧情单元/分集候选。只分析来源和改编空间，不替编剧写最终剧本，不把虚构材料冒充现实事实。
metadata:
  version: "0.1.0"
---

# Source & Adaptation

先读[Source Canon 与改编方法](references/source-canon.md)；来源见[Sources](references/sources.md)。

## 目标

把任意创作来源变成后续可引用、可修订、可追溯的输入。

## Source Type

`original_idea | personal_experience | third_party_experience | novel | short_story | historical_material | documentary_material | outline | screenplay | mixed`

## 每次先分四类

1. **accepted facts / canon**：当前作品必须承认的来源事实或设定。
2. **must preserve**：改编时不可改。
3. **flexible**：允许重组、合并、压缩。
4. **unknown**：材料没有给出，不能补成事实。

## 不同入口

### 灵感/经历

整理：

- 核心事件；
- 人物关系；
- 记忆不确定处；
- 用户真正想表达什么；
- 哪些地方允许戏剧化。

真实经历不是默认要求；只有来源本身是真实时才区分“记得的事实”和“创作重构”。

### 小说/长篇

优先使用稳定章节索引与来源 span。分析：

- 逐章功能；
- story units；
- 情绪/信息推进；
- 人物与世界；
- screen-ready 与 prose-only；
- 改编风险；
- 分集候选。

抽样快评必须声明抽样，不冒充全量。

### 完整剧本

执行 screenplay takeover：

- 保留作者正文；
- 只补后续制作需要的来源/版本/场次定位；
- 不倒回 synopsis/treatment，除非用户要求重新开发。

## 产物

### Source Manifest

- source type；
- locator / file / version；
- provenance / rights note；
- completeness；
- privacy/export boundary。

### Source Canon

- accepted facts；
- preserve；
- flexible；
- unknown。

### Adaptation Contract（需要改编时）

- adaptation goal；
- target format / length；
- compress/merge decisions；
- forbidden changes；
- unresolved decisions；
- affected source spans。

## 长材料的确定性索引

在本项目环境中，长篇 Markdown/TXT 可先用技能仓库 `system/tools/source_index.py` 建立章节/分块索引和 SHA256，再做语义分析。索引负责切片与来源定位，LLM 负责理解；不要让 LLM 自己猜章节边界后再声称全量覆盖。

## 禁止

- 只有书名时凭记忆脑补全文。
- 把来源原文大段复制进分析。
- 把“改编建议”冒充已经确认。
- 创建镜头、Provider Prompt 或资产图。


