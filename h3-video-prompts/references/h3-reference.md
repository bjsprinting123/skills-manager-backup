# Ref2VA全参考

结合h3-common.md使用。输入资产必须真实存在且作用说明清楚；未实际查看则以用户描述为依据并标明，不编造观察。语义可以规划，但当前工作流能否接入这些模态需另核。

## 六字段顺序

```text
subject_definitions:
{one line per tracked reference role, using actual sources}

summary:
[{actual task relationships joined by +}] {target video and reference roles}

retention_analysis:
{each tracked label: where used, selected relationship, scope}

detailed_description:
{one or two sentences of overall style}
[Shot 1] {visible composition, subjects, environment, event, camera and sound}
{later shots with increasing cut times if needed}

overall_soundscape:
{ambience and physical sound; reference/copy relation if relevant}

non_diegetic_music:
{score and its reference/copy relation, or N/A}
```

填写具体内容，不输出占位符；不要增加自造顶层`on_screen_text`字段，画面文字放主描述。详细段通常参考350—500英文词的官方建议，但台词完整性、必要信息和任务复杂度优先，不机械凑字数。

## 标签与任务关系

| 标签 | 含义 |
|---|---|
| `<Subject N>` | 复用的可见内容：人、物、场景、服装、风格、姿态等，不是一个文件名 |
| `<Picture N>` | 来源图片；单独列定义时承担首／尾／关键帧或构图规划职责 |
| `<Video N>` | 原视频编辑／续接或整段镜头节奏等结构来源 |
| `<Audio N>` | 实际采用的音频信号；复制还是仅参考需说明 |

只用于提供人物外观的图片，在Subject定义中写来源Picture即可，不必冗余列独立Picture定义。一个Subject可用多图，各图提供什么分清；一图也可提供多个内容单元。所有标签跨六字段保持同义。

参考视频只提供某个动作／人物时可定义Subject并注明Video来源；只有整段结构、编辑或续接才单独定义Video。视频文件带音轨不自动创建Audio，确实启用才定义。Video和Audio分别编号，不要求同号配对。

summary关系选择：

- `reference generation`：借人物、环境、风格、动作或镜头节奏，不直接编辑／续接源视频。
- `keyframe completion`：图承担目标片某个具体时间帧。
- `video editing`：直接修改源视频；summary正文以`The target video is an edited version of <Video 1>.`起头。
- `video continuation`：从原视频继续。
- `audio reuse`：直接复用全部或部分信号。
- `audio reference`：仅借音色、内容、节奏／音乐风格等，不复制信号。

同时满足可用` + `连接。只传了一个视频不自动构成video editing；只借音色不构成audio reuse。

## 保留关系

| 对象 | 可选关系及意义 |
|---|---|
| Subject／Picture／Video | `fully_preserved`保留已定义职责；`partially_preserved`部分保留；`attribute_transfer`把属性迁移给另一主体；`weak_reference`只借宽泛相似性 |
| Audio | `fully_copy`原音完整作为整片最终音轨；`partially_copy`选段／分层复用或另加声音；`reference`借具体特征但不复制；`weak_reference`只借宽泛氛围 |

写作用镜号／时点和职责，不用`background_preserved`或`audio_preserved`冒充官方关系。关系是目标要求，不能说已实际锁定。新增剧情不是自动损失身份保留；反过来只写weak_reference不能声称精确保脸。

## 说话和音轨

可见引用角色实际发声时写`<Subject 2> (S1)`；S编号按目标片实际发声先后，不按Subject编号。音色定义绑定同一S，保留分析不分配S。

直接复用原音中的语言且无独立人物实际发声时，以Audio标记可听来源，不凭歌词给画内静默角色造说话人。借音色时只表演目标台词，不能顺手复用原音台词。

台词保持原话；官方对音频转写有基础标点规范化建议，若与用户确认的精确文本冲突，保留确认文本并在正文外说明差异，不静默覆盖。不可辨处用`[unclear]`，只影响确实不可辨范围。

## 结束前核对

定义与正文逐标签对齐；每个来源有实际文件／用户明确的输入说明；保留范围没有互斥造型；帧锚不是普通风格图；动作与前后镜当前状态一致；复制音频与自行生成新声音不矛盾。引用顺序按真实入口核对，不能按示例编号假造资产。
