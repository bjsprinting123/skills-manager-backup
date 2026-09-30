---
name: ai-film-studio
description: AI影视项目总入口。根据用户实际拥有的灵感、小说、经历、剧本、资产、分镜或生成结果判断当前入口，只路由需要的专业职责，维护版本、权威输入、下游失效与人工确认，不代替编剧、导演、美术、摄影或Provider写正文。
metadata:
  version: "0.1.0"
---

# AI Film Studio Router

按需读取[路由、版本与升级规则](references/routing-versioning.md)；来源见[Sources](references/sources.md)。

## 核心职责

1. 判断当前项目从哪里进入，不强迫补齐不存在的上游。
2. 标记当前 authoritative artifact 与版本。
3. 一次只把任务交给真正拥有该决定的 owner。
4. 上游变化时标记受影响下游为 stale，不自动重写。
5. 根据影响等级决定自动、事后报告或先确认。
6. Provider、Review、Post 都是下游职责，Router 不抢写。

## 项目状态持久化

真实项目使用 `scripts/project_state.py` 维护项目目录下的 `.ai-film/project-state.json`。accepted / stale / retired、artifact version、dependency 与 impact 不再依赖聊天记忆。

常用动作：

- `init <project>`：初始化项目状态；
- `set <project> <slot> --version ... --path ... --depends-on ...`：登记/更新 artifact；上游版本变化会递归标记下游 stale；
- `status <project>`：查看当前权威版本；
- `impact <project> <slot>`：查看下游影响；
- `validate <project>`：检查依赖、循环、accepted 文件是否真实存在。

## 入口路由

| 用户现状 | 路由 |
|---|---|
| 一句话灵感/经历 | film-source-adaptation → film-story-screenplay |
| 小说/长篇 | film-source-adaptation |
| 已有大纲/故事 | film-story-screenplay |
| 完整剧本 | 直接 film-director；不要伪造 synopsis/treatment |
| 已有导演方案 | film-visual-development / film-shot-director |
| 已有视觉设定 | film-shot-director / film-assets-continuity |
| 只要表演/打斗 | film-performance-action |
| 只要 Krea/H3 Prompt | 对应 Provider Adapter |
| 已有生成结果 | film-production-supervisor → film-review / film-post-production |
| 成片问题 | film-review；按 finding 返回最早 broken owner |
| 新知识/新Skill/新模型/升级请求 | ai-film-skill-upgrader；不要在创作 Router 内直接改 CURRENT |

## 状态原则

- `draft`：可变候选。
- `accepted`：当前权威版本，但仍可创建新版本。
- `stale`：上游已变化，不能冒充当前有效。
- `retired`：历史保留。

## 人工门

- LOW：格式/引用/不改语义的机械修复，可执行后报告。
- MEDIUM：局部拆镜、局部换 Provider、局部返工，执行后报告。
- HIGH：改结局、主角、POV、导演核心意图、Visual Bible 核心、Promote CURRENT，执行前确认。

## 禁止

- 不把“流程完整”当成必须从第1步跑到最后。
- 不自行改 screenplay / Director Bible / Visual Bible。
- 不把 Provider 限制反写成故事事实。
- 不把未知信息补成用户已确认。
- 不把当前 Candidate 自动替换 CURRENT。

## 输出

只输出当前必要的：

- Routing Decision；
- 当前 authoritative versions；
- stale 列表；
- 本轮 owner；
- 真正需要用户确认的高影响分叉。


