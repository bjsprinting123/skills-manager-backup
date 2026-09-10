# 生图交付模板

花括号是写作槽位。应用时填完并消除可选分支，最终交付不保留槽位。不要让用户为了填表才能得到提示词。

## 单图直达

中文说明（需要时一句）：我按{可调整的视觉方案}补充，保留{用户核心意图}。

```text
{Medium and main subject, with identifying features relevant to this image}. {One visible pose or action state, with hands, objects and contact assigned to the right subject}. {Setting, subject placement and framing}. {Light direction and visible material response}. {Coherent color and style, and essential exclusions only when needed}.
```

完整示例，仅示范表达，不当默认风格：

用户：“窗边一盆薄荷，雨天，安静一点，只要提示词。”

```text
A quiet still-life photograph of a small mint plant in a plain terracotta pot on an indoor wooden windowsill. The mint occupies the left third of the frame, its fresh green leaves clearly separated from the softly blurred window behind it. Small rain droplets cling to the outside of the glass. Diffuse overcast daylight reveals the matte clay and the gentle veins of the leaves, with restrained green and warm brown colors and soft shadows across the sill. The right side of the composition remains open and uncluttered.
```

## 资产任务

```text
用途：身份／服装／道具／场景／构图／关键帧，按需选择。
必须看清：
保持／不继承：
中文画面：
生图正文：按单图结构写成完整段落。
用户检查：身份、裁切、接触、重要细节及该图用途。
```

不强制一次生成正侧背或所有资产类别。需要多张时逐图给可独立使用的正文，重复必要身份锚点但不堆整个人物生平。

## 修订目标

```text
看到的问题／尚未看到的部分：
保持项：
改变项与理由：
输入能力：真实编辑／控制已确认，或仅文字重建。
修订后完整正文：
需要核查的区域／部位：
```

若用户只要正文，省略说明；若隐藏能力缺口会误导，则先一句说明限制，不假装已经保真编辑。
