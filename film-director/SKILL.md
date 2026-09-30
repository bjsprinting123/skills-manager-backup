---
name: film-director
description: 从已接受剧本建立导演意图与Director Bible：观众知情、POV、潜台词、场面调度意图、表演方向、视觉命题、声音与剪辑策略。回答“为什么这样拍”，不把导演分析直接写成Provider Prompt，也不替摄影/美术完成全部细节。
metadata:
  version: "0.1.0"
---

# Film Director

先读[Director Book 方法](references/director-book.md)；来源见[Sources](references/sources.md)。

## 先回答六件事

1. 这场/这部作品表面发生什么？
2. 人物真正争夺什么？
3. 观众此刻知道什么、不知道什么？
4. 观众应贴近谁的体验？
5. 场面结束时关系/信息/权力怎样变化？
6. 最简单、可被拍出来的视觉命题是什么？

## Director Bible

至少记录：

- audience effect；
- POV / information strategy；
- director path；
- subtext；
- visual thesis；
- spatial power；
- performance intent；
- sound intent；
- editing intent；
- must-show / must-hide；
- anti-default choice；
- non-negotiables。

## 决策可解释

重要决定应能回答：

```text
decision
why
what audience gains
alternative considered
constraint
```

“更电影感”“更高级”不是充分理由。

## Blocking before framing

导演先决定：

- 人物目标；
- 走位/距离/遮挡；
- 谁接近/离开；
- 谁听、谁看、谁不反应；

再交给 film-shot-director 选择摄影机。

## 声音与剪辑

导演决定：

- 是否用音乐；
- 什么声音应先于画面；
- 哪个沉默必须保留；
- 什么信息应该用 reaction 而不是对白；
- cut 的动机是什么。

## 禁止

- 不把“悲伤=特写”“紧张=慢推”当机械规则。
- 不指定 H3/Seedance 方言。
- 不以当前模型做不到为理由偷偷改主题/人物行为；只能提出 feasibility conflict/fallback。
- 不替 Review 宣布自己的方案通过。


