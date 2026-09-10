# 未来 Skill 通用输入输出契约

## 1. Skill 的真正核心

唯一必需输入是一个可解析的 ComfyUI JSON。视频、UP 主、作者说明、截图、模型页面、节点源码和本机测试都是可选证据，不是生成文档的前提。

因此同一个 Skill 必须同时支持：

1. `JSON-only`
2. `JSON + 视频`
3. `JSON + 作者资料`
4. `完整证据包`

输入形态只改变证据丰富度，不降低 JSON 节点和参数解析标准。没有视频、没有 UP 主不算失败，也不应生成空洞的“请补视频”占位文档。

## 2. 输入契约

```yaml
workflow:
  source: 本地路径或用户直接上传的 JSON
  format: auto                 # 自动识别 UI workflow / API prompt
  title: optional
  original_filename: auto
  sha256: auto

video_sources:                 # optional，可为空
  - platform: bilibili | douyin | youtube | local | other
    url_or_path: 地址或本地文件
    subtitle_or_transcript: optional
    creator: optional

author_materials:              # optional，可为空
  - type: note | readme | post | model_page | image | other
    source: 地址、本地文件或直接文本
    author: optional

evidence_bundle:               # optional
  comfyui_root: 本机 ComfyUI 目录
  custom_nodes_root: 自定义节点目录
  model_inventory: 模型目录或清单
  model_library_root: 共享模型资料库根目录；只读查询，optional
  screenshots: []
  benchmark_logs: []
  previous_document: 旧版文档路径

options:
  language: zh-CN
  target_hardware: optional
  research_web: true
  redact_sensitive_content: true
  overwrite_existing: false
```

### 2.1 两类 JSON

- **UI Workflow JSON**：通常有 `nodes`、`links`、`groups`、画布位置、节点模式和前端控件值。可以完整分析布局、物理 link ID、Reroute 和分组。
- **API Prompt JSON**：通常以节点 ID 为键，有 `class_type` 与 `inputs`。它可能没有布局、分组、物理 link ID 和前端状态。

API Prompt 缺少画布信息时写 `not_provided_by_source_format`，不算解析失败。未来脚本不应为了补齐 UI 信息而猜坐标、分组或前端控件。

## 3. 四种输入形态的行为

| 输入形态 | 必需内容 | 必须产出 | 绝不能假装拥有 |
|---|---|---|---|
| JSON-only | JSON | 全节点、当前参数、模型引用、原始连接、语义流、操作、排错、证据状态 | UP 主意图、视频讲解、作者推荐、本机性能 |
| JSON + 视频 | JSON、视频/地址 | JSON-only 全部；视频元数据、字幕/转写来源、时间映射、与 JSON 差异 | 没看见的画面、未获取字幕、无依据时间码 |
| JSON + 作者资料 | JSON、作者笔记/README/帖子 | JSON-only 全部；作者原话、意图、建议与 JSON 差异 | 作者未说过的观点 |
| 完整证据包 | JSON、视频、作者资料、源码/模型/测试等 | 完整文档、来源对账、版本核验、旧版对比、可条件化优化 | 仍未核实的来源、许可或性能结论 |

## 4. 每次运行的固定输出

```text
<工作流名>/<run-id>/
├─ 00-输入清单.json
├─ 01-输入快照/
├─ 02-机器解析/
│  ├─ 01-工作流解析结果.json
│  ├─ 02-参数覆盖对账.json
│  ├─ 03-节点查证任务清单.json
│  ├─ 04-控制面与模式清单.json
│  ├─ 05-素材与运行链路清单.json
│  ├─ 06-官方CLI核验.json
│  ├─ 07-模型资料交接.json       # 仅显式提供共享模型资料库时
│  └─ 其余按实际证据生成
├─ 03-证据台账.json
├─ 90-工作流文档候选版.md
└─ 99-验收报告.json
```

候选正文固定十章：

1. 工作流简介与适用范围
2. 数据流概览
3. 模型、插件与环境依赖
4. 从加载到运行的操作步骤
5. 全部节点与参数详解
6. 视频讲解与作者说明
7. 原始连接与语义连接
8. 性能、显存与优化建议
9. 常见问题与排错
10. 来源、证据和核验状态

第六章始终保留。如果没有相关输入，直接显示：

> 本次未提供视频或作者资料。本章不推测创作者意图，其他章节依据工作流 JSON、节点源码及已核实资料生成。

这样用户拿到的文档结构始终一致，但视频不会被误设成硬依赖。

## 5. 条件输出

仅在实际有资料时创建：

```text
03-视频证据/
  ├─ 视频元数据.json
  ├─ 原始字幕或转写
  └─ 视频内容映射.md

04-作者资料/
  ├─ 原始资料清单.json
  └─ 作者说明映射.md

05-外部查证/
  ├─ 节点资料查证矩阵.json
  ├─ 节点资料查证矩阵.md
  └─ raw/                    # 搜索与已打开页面的原始结果

91-与旧版文档对比.md       # 仅有旧文档时
92-本机实测报告.md           # 仅真正运行且有日志时
```

没有资料用 `not_provided`；有地址但无法读取用 `unavailable`；读取后内容不足用 `insufficient_evidence`。三种状态不能混写。

## 5.1 共享模型资料库交接

只有显式提供 `--model-library-root` 时才生成 `02-机器解析/07-模型资料交接.json`；默认运行的文件集合和终端摘要保持不变。交接报告只读取 `<model_library_root>/索引数据/model-index.json`，不得写共享资料库。

`run_directory` 和单独执行 `model_handoff.py` 时的输出路径必须在共享模型库之外；即使通过链接指回库内也应拒绝，防止工作流侧误覆盖索引或资料卡。

交接输入只来自解析结果中已可靠命名、未脱敏的模型选择字符串，或经过节点源码核实的嵌套字符串叶子；具体支持范围和保存态规则见 `model-library-handoff.md`。`unresolved_widgets`、URL、提示词、普通图片、视频、音频和说明文本不得用于推断模型身份。结果状态固定分开：

- `matched`：完整 SHA-256 命中，或角色和显式版本均无冲突的唯一别名命中。显式版本不同的唯一候选也不能命中；版本未知转待消歧。
- `missing`：索引有效，但没有匹配项；为该节点和参数生成待研究请求。
- `ambiguous`：多个条目满足同一精确引用，禁止自动挑选；生成消歧请求，等待精确哈希、发布者或版本证据。
- `not_checked`：共享根不存在、索引缺失、JSON 损坏或 schema 不兼容；不得降级成 `missing`。

四阶段统一为工作流分析（analysis）、共享索引查询（index）、模型研究（research）和模型发布（publish）。发布器先原子提交索引，再返回回执；工作流验证回执后才能确认新卡片已发布。用户已授权分析并入库时，同一助手读取模型库规则继续研究、发布并回填本次工作流；只解释或审阅时输出候选证据。

匹配结果的 `matched_library_entries` 保留库内状态、角色、制品形态、版本、哈希与 revision；外层字段仍是工作流引用提示。`conflict`、`deprecated` 或制品形态冲突转 `ambiguous`。`candidate`、`partial` 唯一命中仍标明 `library_review_required`，汇总为 `needs_library_review`（若同时缺资料或有歧义，优先报告对应状态）。

交接中的 `model_role` 和 `artifact_form` 必须使用模型库统一枚举；未知时写 `unknown`，不得另造 `weight_file`、`named_selector`、`unspecified_model` 等近义值。

共享库不可用或补录未完成不阻断 JSON、节点、连线和其他有证据正文；文档应保留模型身份待核实状态。两个 Skill 之间不得递归调用。工作流侧只维护具体工作流的加载节点、强度、连线与配方，模型库侧维护可复用身份、版本、作者资料与有来源的社区反馈。

## 6. 证据等级

- **A级：直接证据**——源 JSON、文件哈希、机器解析、本机源码、带环境记录的本机实测。
- **B级：一级权威来源**——ComfyUI/节点官方源码、官方文档、官方仓库、官方模型卡和发布说明。
- **C级：作者来源**——UP 主视频、作者 README/帖子、工作流内嵌 Note/MarkdownNote。
- **D级：社区来源**——Civitai、LiblibAI、ModelScope 社区内容、技术论坛。
- **E级：推断或未核实**——文件名推断、旧文档遗留说法、搜索摘要、无法打开页面。

所有参数建议都按下列列分开：

```text
当前值｜源码通用默认｜专项官方基线｜作者建议｜本机实测｜适用条件｜修改风险
```

没有源码或官方 schema 时，绝不能把“当前值”叫作“默认值”。社区经验不能冒充官方建议，作者说明也不能自动覆盖 JSON 事实。

## 7. 处理流水线

### 7.1 锁定输入

- 复制只读快照，记录绝对来源路径、文件名、大小和 SHA-256。
- 默认不覆盖源 JSON、正式文档、原字幕和作者资料。
- 检查 API Key、Cookie、Token、密码、成人提示词和个人敏感信息；正文脱敏，证据清单只保留必要哈希。

### 7.2 解析 JSON

- 识别 UI Workflow 或 API Prompt。
- 对账节点 ID、类型、模式、包、版本、输入、输出、控件值、前端状态、注释、分组和物理连接。
- Reroute 同时保留物理连线和折叠后的语义连线。
- UUID 子图先解析其 definitions，再展开内部节点；不能把子图实例当成一个未知普通节点结束。
- 无法命名的 `widgets_values` 保留索引与原值，标成 unresolved，禁止按位置猜名字。

### 7.3 解析依赖

- 模型依赖只取 JSON 真实引用，不从作者目录树自动增加。
- 检查本机文件时记录真实路径、大小、SHA-256 和 safetensors dtype；文件名不是精度或来源证据。
- 核心、自定义和未知节点分栏；自定义包通过节点 properties、本机源码和作者仓库交叉确认。

### 7.4 节点资料查证

- 从解析结果生成 `03-节点查证任务清单.json`，覆盖每个不同节点类型，并记录关联 ID、canonical type、包提示和保存版本；Reroute、标签和说明节点标为非执行辅助类型。
- 先查当前环境的 `/object_info`、节点源码或包清单，再查官方文档、官方仓库、发布说明和模型卡；不得先按画布显示名盲搜。
- 每个节点类型至少需要一项可追溯的实现依据，或明确的 unresolved 状态。自定义、未知、缺失、版本冲突和行为敏感节点还必须进行官方来源发现和针对性社区检索。
- 社区内容只补充兼容性、常见报错和实际经验，不能覆盖 JSON、当前源码或官方资料。没有可靠社区结果时记录 `unavailable` 或 `insufficient_evidence`，不能静默跳过。
- 原始搜索结果与已打开页面的抽取结果进入外部查证目录；搜索摘要只用于发现链接，不能单独支撑正文结论。
- 在节点资料查证矩阵覆盖完成或每个缺口都有明确状态之前，不起草候选正文。

### 7.5 处理可选证据

- 视频先匿名读取公开元数据；若字幕不可得，如实记录。未经用户明确授权，不读取浏览器 Cookie 或本地 Cookie 文件。
- 本地 Whisper 转写必须标明模型、设备、参数、哈希和 ASR 局限，不能冒充平台字幕。
- 作者原文程序原样抽取并单独保存；正文可读转录旁边直接附核验注释。
- 外部研究先搜索发现，再抽取/打开原页面；原始 JSON 归档，搜索摘要不作为最终事实。

### 7.6 生成、比较和验收

- 先生成候选版，不覆盖正式版。
- 有旧文档时按章节列“保留、改写、删除/移出、原因”。
- 所有用户操作所需的重要说明直接放到相关节点旁，不只写“去 A 册查看”。
- 最后重新计算源文件与正式文档哈希，证明没有静默改源。

## 8. 验收门槛

一次运行至少满足：

- 源格式、路径、大小、SHA-256 已记录。
- 节点、具名字段、未命名控件、分组和原始连接全部对账。
- 物理连接数与语义连接数分别统计。
- 每个字段归入执行参数、连接输入、前端状态、说明文本或 unresolved。
- 模式、枚举和弹窗参数只按当前证据生成，实际选项数完整覆盖；没有模式控件时明确记为 `not_applicable`，不套固定四模式。
- 素材启用、路径存在、提示词引用、槽位绑定、运行使用和最终合成分别记录；计划值与日志/输出证明的生效值分别记录。
- 节点查证任务清单覆盖全部不同节点类型；每种类型都在查证矩阵中有权威实现依据或明确的 unresolved 状态，非执行辅助类型单独标识。
- 自定义、未知、缺失、版本冲突和行为敏感节点均有官方来源发现记录与社区检索状态；检索无结果不伪造来源。
- 文档验收调用 `validate_document.py` 时必须通过 `--node-research` 提供本次节点资料查证矩阵；缺少矩阵或覆盖不全时不得通过。
- 未知节点不猜包；缺包不假装已安装。
- 当前值、默认、官方模板、作者建议和本机实测严格分栏。
- 视频访问失败、需登录、无字幕或 ASR 不确定均明确记录。
- 没有视频/作者资料不算失败；只有必需 JSON 无法解析才失败。
- 正文和日志不泄露 API Key、Cookie、Token 或敏感提示词。
- Obsidian 目标文档声明 `comfyui-workflow-doc` 样式类，并已在该候选文件的阅读视图核对宽屏正文、Mermaid SVG、参数卡和横向滚动状态。
- 候选版默认不覆盖正式文档，除非用户明确确认。

建议最终状态只有：

- `PASS`
- `PASS_WITH_UNRESOLVED_NODES`
- `FAIL_INVALID_JSON`

以上是完成契约的摘要，不替代验证器实际返回的 FAIL_VALIDATION 等失败状态；任一必需检查失败时不能强制归为 PASS。

交付还须分别报告结构校验、视觉核验、语义核验和运行验证。结构 PASS 不代表语义完善或可以运行；明确列出语义未核实范围，由助手继续核验，不让用户逐节点补审。运行未执行、视频未提供、作者资料未提供、模型来源待确认等放在独立字段中，不滥用失败状态。

### 独立的知识回写验收层

以上 PASS 等状态只描述文档校验，不代表知识目标已完成。prepare_run.py 同时生成 `98-知识回写核对.json`，默认全部 pending_research；不会自动授权研究范围扩张或发布。必须依据本次证据、范围和已有授权逐项改成真实状态，再运行 `scripts/validate_closeout.py`。八类目标和字段规范见 [模型库交接](model-library-handoff.md)。

验收结果独立显示 PASS_CLOSED、PARTIAL 或 FAIL；存在待研究、待批准或阻塞项时，最终答复必须列下一动作，不能仅给出文档 PASS。只补视频、不重跑 prepare_run 的增量任务也要建立同样的核对记录。已有索引/指南若同时有机器源，更新两者并保留无关旧记录。

## 9. 本次样板怎样证明通用性

`01-Z_image_Turbo-文生图` 使用的是“完整证据包”路径，所以第六章有视频和作者原文，第十章有官方/社区查证。若下次只收到一个普通 JSON：

- 保留相同十章、解析文件和验收报告。
- 第六章显示 `not_provided`。
- 不创建视频或作者原文目录。
- 第五、七章仍必须达到节点、参数和连接全覆盖。
- 即使没有视频，节点查证任务清单和查证矩阵仍必须完成；视频不是节点资料查证的替代品。
- 第八章只能给条件化测试方法，不能凭空出现 UP 主经验或本机性能数字。

因此模板不依赖 B 站、抖音或特定 UP 主；这些来源只是让证据更丰富，而不是让工作流文档成立的前提。

## 10. 权威 widget schema

旧版 UI Workflow 常只有 `widgets_values` 数组，没有 `widgets_values_named`。需要从当前环境的 `/object_info`、节点源码或其他可追溯 schema 建立字段顺序文件：

```json
{
  "source": {
    "kind": "local_comfyui_core_source",
    "path": "<SOURCE_PATH>",
    "commit": "<COMMIT_OR_NOT_VERIFIED>",
    "file_sha256": "<SHA256>"
  },
  "nodes": {
    "EmptyLatentImage": ["width", "height", "batch_size"],
    "KSampler": [
      "seed",
      "control_after_generate",
      "steps",
      "cfg",
      "sampler_name",
      "scheduler",
      "denoise"
    ]
  }
}
```

映射只有在节点类型存在且 schema 字段数与保存值数量完全一致时才能生效。数量不一致必须保留全部原值为 unresolved，并记录 `widget_schema_length_mismatch`。schema 自身的路径和 SHA-256 必须进入解析报告；不能用无来源的手写数组冒充权威 schema。
