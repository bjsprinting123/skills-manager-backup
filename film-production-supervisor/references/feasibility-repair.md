# Feasibility / Production / Repair

## 每镜生产问题

1. 当前 Provider 真能做吗？
2. 必要参考齐不齐？
3. 主要失败模式是什么？
4. 预计重试成本合理吗？
5. 是否应先做 Previs / keyframe / 低成本验证？
6. 失败后最早应该回哪个 owner？

## Risk dimensions

可按人物数、接触复杂度、空间跨度、物件永久性、镜头路径、口型/声音、时长、VFX、参考素材完整度评估。

## Fallback ladder

从最小语义改变开始：补 reference/keyframe → 缩短生成单元 → 减少独立动作 → 调整 coverage/insert → 把接触放到 cut → 分 Shot → 后期/VFX → 返回 Director/Story 重设。

最后一步必须由创作 owner 决定。

## Retry budget

不要无限抽卡。每轮重试记录失败原因；连续同类失败说明需要改变生产方案，而不是继续加形容词。

## Earliest broken decision

失败定位顺序：Source/Story → Director → Visual → Shot → Performance/Action → Asset/Continuity → Provider → Take/Post。

视频不好不等于默认改 Prompt。

## Take Ledger

记录 take_id、shot_id、provider/version、prompt version、references、result path、technical status、review status、accepted/rejected、defect code、retry relation。

