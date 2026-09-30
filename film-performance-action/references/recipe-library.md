# Action / Performance Recipe Library

这些是按条件调用的 Recipe，不是结构硬规则。

## R-A01 白模动作预演

适用：多人打斗、复杂走位、长镜头、跨空间动作。

做法：先用 top view / 白模 / 路径把人物、道具、接触点和相机路线跑通，再绑定正式角色、服化道和风格。

不适用：简单单人文戏、无需复杂空间的短动作。

## R-A02 受力-速度-结果

适用：高强度动作。

做法：动作提示至少明确方向、速度、接触/落空、受力、位置变化和结果。

避免：只列招式名或“高燃、炸裂”形容词。

## R-A03 复杂接触切点

适用：当前 Provider 对多人身体接触不稳定。

做法：把最难的接触落在 cut / occlusion / insert 上，分别生成可读起终状态。

前提：不能改变导演意图或动作结果。

## R-A04 对白暗流

适用：争吵、压抑文戏、长对白。

考虑：话权、pickup、打断、重叠、failed start、自我修正、沉默、触发词、listener reaction。

避免：平均分配口吃、停顿、眨眼。

## R-A05 群像异步反应

适用：3人以上同场。

每人保留独立 current task、attention target、反应延迟；不让所有人同时看镜头或同时做同类动作。

## R-A06 Asset-first 高风险镜头

适用：身份、服装、道具跨镜必须稳定。

先锁 identity / look / prop state 和 reference authority，再投入高成本视频生成。

来源与证据级别见 [Sources](sources.md) 及技能仓库 system/knowledge/recipe-index.json。
