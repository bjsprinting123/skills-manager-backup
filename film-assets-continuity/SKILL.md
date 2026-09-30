---
name: film-assets-continuity
description: 从剧本、Visual Bible、Shot Bible建立最少充分的角色/造型/地点/道具资产、参考素材权限与跨镜连续性账本。区分身份、变体、镜头瞬态和故事状态；维护Continuity Ledger，但不生成图片、不改故事。
metadata:
  version: "0.1.0"
---

# Assets & Continuity

先读[资产、参考权威与连续性方法](references/assets-continuity.md)；来源见[Sources](references/sources.md)。

## 四分法

### Identity

换掉就不再是同一个人/地/物。

### Variant

身份不变，但发生：

- costume；
- hair/makeup；
- injury；
- wet/dirty；
- day/night；
- prop open/closed；
- state change。

### Shot transient

- pose；
- gaze；
- current screen position；
- temporary hand placement；
- camera angle。

归 Shot / Performance，不创建新身份。

### Story state

- knowledge；
- relationship；
- objective；
- emotion。

归 Story/Director，只把可见后果投影到资产/连续性。

## Asset Manifest

每项写：

- asset_id；
- kind；
- identity anchors；
- current variants；
- allowed changes；
- appearances；
- continuity risk；
- actual media status。

## Reference Authority

每个实际参考素材必须声明：

```text
controls:
does_not_control:
scope:
version:
actual_file_status:
```

例如身份图不自动控制动作、镜头、声音或背景。

## Continuity Ledger

按生效范围记录：

- story day/time；
- character look；
- costume；
- hair/makeup/age/injury；
- prop holder/state；
- world position；
- action residue；
- eyeline；
- emotional residue；
- lighting state；
- Shot end → next start；
- accepted Take。

## 连续性不是“所有东西永远不变”

必须区分：

```text
invariant
planned change
unknown
error/drift
```

## 禁止

- 不把“已有图片提示词”当作实际图片。
- 不用文件名猜素材内容。
- 不创建不存在的引用路径。
- 不让连续性检查篡改剧情变化。
- 不把 screen-left 锁成 world-left。


