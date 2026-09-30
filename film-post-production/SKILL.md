---
name: film-post-production
description: 将已存在且通过最低Take审查的真实媒体组织为成片：Picture Edit、声音后期、音乐、VFX/Compositing、Color Grade、字幕图形、Master QC和Delivery Manifest。只处理真实可读素材；需要补拍/改剧本/改镜头时退回上游owner。
metadata:
  version: "0.1.0"
---

# Film Post-production

按需读取[后期制作方法](references/post-production.md)；来源见[Sources](references/sources.md)。

## 入口

必须有实际媒体文件。以下都不算素材：

- Prompt；
- IMG/PLAN 条目；
- job preview；
- Provider 返回“成功”但文件不可读。

在本项目环境中，可先用技能仓库 `system/tools/media_probe.py` 对真实文件做 ffprobe 检查；只有探针能读出媒体流，才进入实际后期审查。

## 1. Picture Edit

先完整看素材，记录：

- usable range；
- bad head/tail；
- action completion；
- drift；
- dialogue region；
- reaction；
- candidate in/out。

再决定：

- cut order；
- in/out；
- hard cut / match / J / L；
- reaction coverage；
- whether a shot is omitted。

剪辑可取舍 Shot，不可悄悄改台词含义或故事事实。

## 2. Sound Post

区分：

- dialogue / ADR；
- room tone；
- ambience；
- foley；
- spot SFX；
- music；
- intentional silence。

Sound Bible 是创作上游；后期实现它，不重新发明故事。

## 3. Music

根据 Music Map 做：

- cue in/out；
- edit；
- ducking；
- silence；
- transition。

不因“情绪场”默认加配乐。

## 4. VFX / Compositing

建立 VFX Shot List：

- cleanup；
- screen/text replacement；
- tracking；
- mask/roto；
- environment/VFX layer；
- face/hand patch；
- transition repair。

优先判断后期能解决还是必须返工生成。

## 5. Color

### 上游
`Visual Bible / Color Script`

### 本阶段
- shot matching；
- exposure；
- white balance；
- saturation；
- contrast；
- look/grade；
- LUT/transform（需要时）。

不把 Grade 重新设计成与 Visual Bible 冲突的新影片。

## 6. Titles / Subtitles / Graphics

- 字幕文字来自 accepted screenplay；
- UI/屏幕可读文字按已接受图形规格；
- safe area / language / version 明确。

## 7. Master QC / Delivery

至少记录：

- resolution；
- fps；
- aspect；
- codec/container；
- color space；
- audio layout；
- loudness target；
- subtitle mode；
- duration；
- version；
- checks / unresolved notes。

## 禁止

- 不把 render success 写成 creative approval。
- 不为修一个剪辑问题重写整个剧情。
- 不用单镜局部调色破坏全片 color continuity。
- 不在素材不可读时宣称成片完成。

