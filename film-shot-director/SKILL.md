---
name: film-shot-director
description: 把已接受的剧本、Director Bible与Visual Bible转成可执行Shot Bible与模型中立Generic Shot Spec。先做空间调度和镜头句，再选择景别、机位、焦段、构图、运镜与关键帧；复杂场景可生成Previs方案。禁止直接写H3/Seedance方言。
metadata:
  version: "0.1.0"
---

# Shot Director / Cinematography / Storyboard

按需读取[空间、摄影与 Previs 方法](references/space-camera-previs.md)和[Camera Recipes](references/camera-recipes.md)；来源见[Sources](references/sources.md)。

## 工作顺序

```text
理解本场因果与变化
→ 固定世界空间
→ 人物调度
→ 整段镜头句
→ 单镜职责
→ 摄影机与构图
→ 起点/变化/终点
→ Generic Shot Spec
```

## Scene World State

复杂空间先建立：

- 固定地标；
- 人物世界位置；
- 朝向/视线；
- 道具持有人/位置/状态；
- 行动轴；
- 主要光源世界位置；
- 环境连续状态。

世界坐标不因切镜改变；每次换机位重新计算屏幕左/右、遮挡和受光。

## Blocking

先决定：

- 谁移动/停下；
- 谁接近/远离；
- 谁遮挡/显露；
- 谁进入/离开；
- contact 的前后状态。

不要先写焦段再硬塞人物。

## Shot Sentence

先设计一整段观看关系，再拆镜：

- shot function；
- information timing；
- shot size progression；
- focus/attention；
- cut motivation；
- movement trigger；
- end composition。

景别多样性本身不是目标。

## Cinematography

每镜按需写：

- shot size；
- camera world position；
- height / angle；
- lens feel；
- depth/focus；
- composition；
- camera movement；
- movement magnitude/path；
- lighting state；
- cut / transition intention。

复杂运镜必须有：起始构图 → 触发 → 分段路径 → 焦点/遮挡接力 → 终点构图。

## Previs

多人、打斗、跨房间、复杂长镜头才优先使用：

- top view；
- clay/white-model board；
- camera path；
- action path；
- animatic。

不强迫简单文戏先做宫格。

## Generic Shot Spec

必须明确：

- story_function；
- source_scene；
- world_state；
- camera；
- visual；
- performance references；
- sound intention；
- state.start / change / end；
- reference authority；
- continuity；
- risk / fallback。

## 禁止

- 不写 provider-specific slot / mode。
- 不把“氛围”直接翻译为运镜。
- 不让镜头移动重新定义世界位置。
- 不为了规整机械均分镜长。
- 不在 Shot 层改剧本台词。


