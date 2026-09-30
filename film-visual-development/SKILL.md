---
name: film-visual-development
description: 根据Screenplay与Director Bible建立整部作品的Visual Bible：production design、角色造型、服装发型妆造方向、Palette、Color Script、材质质感、灯光概念和VFX视觉策略。决定“整部片长什么样”，不直接写Krea/Qwen等模型方言。
metadata:
  version: "0.1.0"
---

# Visual Development

先读[Visual Bible 方法](references/visual-bible.md)；来源见[Sources](references/sources.md)。

## 核心原则

视觉决定必须服务故事、人物和导演意图，而不是每镜重新“找一个漂亮风格”。

## Visual Bible

按项目需要包含：

### Production Design
- era / culture / location logic；
- architecture / furnishing；
- material；
- graphic/text policy；
- recurring visual anchors。

### Character Look
- identity visual intent；
- silhouette；
- costume arc；
- hair/makeup/age/injury state；
- what must stay recognizable。

### Palette
- base colors；
- character colors；
- location colors；
- accent/motif colors；
- forbidden collisions。

### Color Script

不是 LUT。

记录故事阶段或关键场景：

```text
story state
→ palette/light change
→ narrative reason
```

### Lighting Concept
- motivated sources；
- day/night logic；
- contrast strategy；
- practicals；
- how light changes with story。

### Look / Texture
- contrast；
- saturation；
- grain/texture；
- material response；
- sharpness/softness policy。

### VFX Visual Strategy
- 哪些效果必须与角色/世界色彩一致；
- 哪些适合后期分层，不强塞进一次生成。

## 参考资料使用

- Moodboard/电影参考只能提取可描述机制，不复制独特镜头/角色/美术。
- Provider 内置 style preset 可以作为执行工具，不能取代 Visual Bible。

## 禁止

- 不把 60/30/10、蓝橙、50–85mm 等当全项目强制。
- 不把 Color Script、Lighting、LUT、最终 Grade 混成一个字段。
- 不编写 Krea/H3 Prompt。
- 不因“写实”默认注入所有毛孔/雀斑/胶片颗粒。

