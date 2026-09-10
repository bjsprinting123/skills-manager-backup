# T2VA／I2VA／FL2VA／L2VA

结合h3-common.md使用。模板变量在交付前填好，不把N、S.SS或花括号原样交给用户当执行稿。

## 基础字段

顺序固定，字段之间空行：

```text
integrated_multimodal_description: [Shot 1] {style, opening composition, subjects, action and synchronized sound; later shots if needed}

overall_soundscape: {ambience and physical sounds, without repeated dialogue}

non_diegetic_music: {score description, or N/A if no score}
```

T2VA直接从三字段开始，不加不存在的图／音频标签。风格在Shot1开头，以用户媒介为准。

## I2VA：图是实际开场

最前方加以下首行，然后空行接三字段：

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
```

先写实际首帧锚点，再写下一个动作。已经张开的伞不能无解释当成闭伞重新打开；保留图中身份、衣物、关键道具和空间。若图和用户想要的起点相反，说明冲突，建议补图或更改起点，不能虚称两者都保留。

## FL2VA：首尾之间的路径

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.
```

N替换为实际最后镜号，S.SS为有效时长两位小数。再空行接三字段。通常用连续单镜连接；用户明确要求多镜时交代切点和落帧。写前态→可见过渡→逐步接近→终态，不只是重复两张图的静态描述。

图中同一人物／道具可以早出现；末帧约束的是指定时刻状态，不是“所有末帧内容只能最后出现”。首尾差异过大时提出桥接或重设计，不承诺一定补全。

## L2VA：只锁定最后画面

```text
How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.
```

再空行接三字段。推定合理前态并说明提案，最后到达图中状态。该Picture1属于最终镜，不因编号1就当首帧。

## 完整无参考示例

用户：“8秒，二维水彩，一只小狗走到门边坐下，无对白无音乐。”

```text
integrated_multimodal_description: [Shot 1] A 2D watercolor animation opens in a medium-wide view of a quiet entryway. A small brown dog stands beside a woven mat, facing a closed blue door on the right. The camera remains still. The dog takes several unhurried steps toward the door, stops with its nose clear of the wood, then lowers its hindquarters onto the floor while keeping its front paws planted. It settles facing the door and stays seated through the end of the eight-second shot. No character speaks.

overall_soundscape: Soft paw taps cross the wooden floor, followed by a faint rustle as the dog sits. Quiet indoor room tone continues.

non_diegetic_music: N/A
```

示例并非模型实测，不把狗、门、静机或8秒变成默认设定。
