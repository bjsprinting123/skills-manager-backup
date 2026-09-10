# 官方规范原文与中文改写的对应关系

本包（h3-video-prompts）含**两层资料**，用途不同，不要互相替代：

| 层 | 文件 | 语言 | 什么时候用 |
|---|---|---|---|
| **规格层** | `official-h3-base-en.md`、`official-h3-ref-en.md` | 英文 | **要"原文怎么规定的"**：字段顺序、标签语义、镜头运动词表、时间记法、完整示例。照抄格式时以这一层为准 |
| **工作层** | `h3-base.md`、`h3-reference.md`、`h3-common.md` | 中文 | **要"这份活怎么干"**：中文工作流程、常见坑、交付纪律、与本地工作流的接口边界 |

**规则：格式与字段名以规格层为准；写作纪律与本地接口以工作层为准。两层冲突时，格式服从规格层，并在工作层标注差异。**

## 来源与版本锁定

- 官方出处：`https://github.com/MiniMax-AI/MiniMax-H3/tree/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/references`
- **commit 锁定 `d21241f0`**（`sources.md` 已记该版本；两份官方原文即该 commit 下的 `base-en.txt` 与 `ref-en.txt`）
- 并入日期：2026-09-10。原始文件名为 `base-en.txt`／`ref-en.txt`，为免与工作层混淆，加前缀 `official-h3-`。

## 逐节对应

### 规格层 A：`official-h3-base-en.md`（222 行，T2VA／I2VA／FL2VA／L2VA）

| 官方节 | 内容 | 工作层对应 |
|---|---|---|
| §1 Task Overview | 四种模式的构成式定义 | `h3-base.md` 各模式小节 |
| §2.1 Part One Is the Instruction | **四种模式的固定对齐句原文**（T2VA 无指令行；I2VA／FL2VA／L2VA 各有固定句） | `h3-base.md` 三处代码块（已逐字对应） |
| §2.2 Three Core Fields | 三字段顺序与各自职责 | `h3-base.md`「基础字段」 |
| §3.1–3.3 Keyframes | I2VA→前推；FL2VA→首尾路径（**通常单镜**）；L2VA→推前态落尾帧 | `h3-base.md` 各模式小节 + `h3-common.md` 帧锚说明 |
| §4.1 Multimodal Description | 风格写在 `[Shot 1]` 开头；**列举官方承认的风格词**（Cinematic／live-action／2D-animated／3D CG／claymation／watercolor／vintage film） | `h3-common.md`「语言、镜头、时间」 |
| §4.2 Shots and Cuts | 首镜不加时间；后续 `[Shot N] At 00:03.500, ...`；**普通切可用动词表**；只变距离或角度优先用运镜 | `h3-common.md`「语言、镜头、时间」 |
| §4.3 Camera Motion | **三要素：运动类型＋幅度＋速度**，含完整英文词表（Zoom／Push／Pan／Truck／Tilt／Pedestal／Arc／Tracking／Static／Shake／POV／Roll） | `h3-common.md` 相机段（中文对译），**英文用词一律回本表** |
| §4.4 Speakers and Dialogue | `(S1)` 稳定编号、合声 `(S1,S2)`；`<d>` 内只放语言标签与原话；旁白固定句 `says in an off-screen voiceover` 且**须紧接说明画内角色嘴不动**；跨切 `<scenetrans>`、截断 `<cutoff>` | `h3-common.md`「人声」（含中文例句） |
| §4.5 On-Screen Text | 可见文字用英文双引号、保留原文不译 | `h3-common.md`「声音层」末段 |
| §4.6 overall_soundscape | **1–4 句一段**；只写环境／物理声／非语人声；不重复台词；**仅用户明确要求全片静音才写 `N/A`** | `h3-common.md`「声音层」 |
| §4.7 non_diegetic_music | **1–3 句**；只写配器、速度、节奏、强弱；**不写抽象情绪词、不解释配乐功能**；无配乐写 `N/A` | `h3-common.md`「声音层」 |
| §5 Cases 1–4 | **四种模式各一个完整示例** | 工作层只有 T2VA 一个中文示例；其余三例看本文件 |

### 规格层 B：`official-h3-ref-en.md`（341 行，Ref2VA 全参考）

| 官方节 | 内容 | 工作层对应 |
|---|---|---|
| §1 Overall Structure | 六字段固定顺序与各自用途表 | `h3-reference.md`「六字段顺序」 |
| §2 Reference Labels | 四类标签定义；**同一标签跨字段同义**；`subject_definitions` 逐条成行 | `h3-reference.md`「标签与任务关系」 |
| §2.1 `<Subject N>` | 可复用可见内容；**一 Subject 可来自多素材、一素材可提供多 Subject** | 同上 |
| §2.2–2.4 `<Picture N>`／`<Video N>`／`<Audio N>` | 各标签的成立条件；只作来源时**不单独列定义行** | 同上 |
| §3（及后续）保留分析与任务关系 | `fully_preserved`／`partially_preserved`／`attribute_transfer`／`weak_reference`；音频四关系 | `h3-reference.md`「保留关系」「summary 关系选择」 |
| 说话与音轨 | 实际发声才编号；S 编号按发声先后 | `h3-reference.md`「说话和音轨」 |

## 工作层多出、规格层没有的部分（保留，勿删）

这些是本地作业纪律，官方原文不含，**不是冗余**：

- `h3-common.md`：与本地 ComfyUI 原生节点的接口边界（`ref_images` 与 Add Guide 职责差异、"仅接帧锚不等于文本编码器看到该图"）、第三方标签映射核对、"不编造采样器/节点/参考上限"。
- `h3-base.md`：交付纪律（模板变量不原样交给用户）、图与意图冲突时如实说明而不虚称两者都保留。
- `h3-reference.md`：不新增自造顶层字段（如 `on_screen_text`）；详细段 350–500 英文词的建议与其例外；不用 `background_preserved` 之类非官方关系名。
- `runtime-contract.md`／`templates-and-checks.md`／`repair.md`：运行前提、交付检查、返修分流。

## 使用提示

- **写稿时**：先读 `h3-common.md` + 对应模式的工作层文件，格式拿不准或要抄示例时再打开规格层。
- **报价"已按官方格式"时**：以规格层为准核对字段名、标签、时间记法（两位小数 `S.SS`）。
- **官方更新后**：只替换两个 `official-h3-*.txt` 并更新上面的 commit，工作层按需再改。
