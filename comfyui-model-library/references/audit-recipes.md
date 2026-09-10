# 模型卡审计配方集（2026-09-10 全库审计沉淀）

本文收录 2026-09-10 全库 234 张卡审计中实际验证过的方法与踩坑，供后续逐卡核对、NSFW 样图目视、退役排查直接套用。与[中文模型卡语义与图片证据](chinese-card-semantic-audit.md)配合阅读；冲突时以该规范为准，本文是操作层补充。

## 一、命名精度：具体部位不得泛化为上位词

**中文卡名称与定位必须落在模型实际作用的具体部位/概念上，不能用上位词泛化。** 真实踩过的三个坑：

| 实际作用 | 错误命名 | 错在哪 |
|---|---|---|
| 足部特写概念 LoRA（Barphot） | 「成人局部概念」 | 「局部」让人以为是体态/躯干，完全猜不到是足部 |
| 臀胯突出+腰部纤细的体型比例（pawg） | 「成人体型比例」 | 「体型」泛化掉了「臀胯 vs 腰」的核心对比 |
| 单眼皮眼睑形态（Monolid） | 「眼部外观滑块」 | 「眼部」范围太大——双眼皮/眼型/卧蚕都算眼部 |

规则：
1. 命名格式「日期_具体作用_原文件名」中，具体作用段写到**部位+方向**（如「臀髋强化细腰」「足部特写」「单眼皮眼睑」），宁可长不可泛。
2. 自查法：把名字给没读过卡的人看，让对方猜模型干什么；猜不出或猜偏就是命名失败。
3. 改名时卡面摘要、limitations、速查目录、文件名四处要同步；本地文件改名会使工作流引用失效，须单独获得授权并输出引用清单。

## 二、NSFW 样图分级目视协议

Civitai 给每张样图打 `nsfwLevel`：1=正常、2=轻微暗示、4=成熟裸露、8=露骨裸露、16=性交行为。默认分工（库主管可调整授权）：

- **level ≤4：AI 目视**（核对风格/方向/档位与卡面声明）
- **level ≥8（露骨/性交）：用户自查**，AI 只做元数据文字核对

执行顺序：先按卡统计分级分布（`工具/sfw_strip.py <vid> <key> [宽] [高] [maxlv]`），明确「AI 看 N 张 / 用户看 M 张」再开工；逐卡目视后逐卡落卡发布；≥8 部分在卡上写「由用户自查」，不算漏项。

## 三、不看图也能核：样图元数据文字全量核对

样图的嵌入 meta 是文字，与是否 NSFW 无关，必须全量核对：

- **A1111 格式**：强度在 `meta.resources`（name+weight），另看 `hashes` 里的 lora hash；
- **ComfyUI 格式**：`meta.comfy` 内嵌工作流，强度在 LoraLoader 节点 `strength_model`；**rgthree Power Lora Loader 是嵌套 dict（`lora_N: {on, lora, strength}`），按普通节点扫会漏**；
- 顶层 `steps/cfgScale/sampler/scheduler/Model` 与卡面作者建议对照；
- **触发词出现率**：数样图 prompt 含触发词的比例（0/10 仍出画风 = 触发词非必需的实证；8/8 含 = 印证）。

## 四、截断纪律与常见误读

- **Civitai 会截断超长 comfy 字符串**：`json.loads` 失败 = 截断，卡面必须写「工作流被截断、强度不可判」，**禁止写成「确认无强度」**。
- KSampler 输入里的 `["128", 0]` 是**节点链接元组**（来自节点128），不是数值 0——"0步/CFG0"乌龙就是这么来的。
- A1111 与 ComfyUI 两格式的资源字段不同（`resources` vs `additionalResources`），两个字段都要扫。
- 作者正文给的参数与样图 meta 给的参数**分开记录**：正文值=作者建议；meta 值=示例记录；两者冲突时（如作者 beta、样图 Simple）如实并列，不改作者建议。
- **CFG 后端语义**：diffusers `guidance_scale=0` ≠ ComfyUI `CFG=0`。ComfyUI 路线的卡必须按官方 workflow_templates 实抓核对（Krea2 Turbo 官方模板实值 CFG=1）。

## 五、阶梯/对照图是最强实证

作者样图常含自制强度阶梯（红字标注档位）：用 PowerShell/Pillow 裁剪放大读出档位数字，再对照各档画面差异方向。实例：Detail V2 的 -6/-3/0/+3/+6/+8、锐度滑块 -2/0/+1.5/+2、肤色 V1 的 -2/+2 与 -4/+4 双海报、湿润滑块 ±1 三联。读出的档位范围/方向与卡面声明对照，是范围端点和方向性的直接实证；NO LORA 基准面板与副作用声明（如"锐化同时影响背景人物"）也可由此验证。

## 六、来源 URL 与发布器纪律

- author_recommendations 的 `source_url` 必须已存在于 `sources`，否则校验失败——发布前自动补源。
- **坏链检测**：`civitai.com/models/?modelVersionId=xxx`（缺 model id）是坏链；版本 API 顶层有 `modelId` 字段，可一键补全。
- 来源 URL 指向的版本必须与文件 SHA 定位的版本一致（曾发现 src 指向同作者另一产品线的版本）。
- **request-id 不可复用**：同 ID 不同载荷会被发布器正确拒绝；换载荷必须换新 ID。长流程中同一张卡可能被自己多次发布，**每次发布前实时重读当前 revision**。
- 薄卡可能缺 `origin` 结构，按标准结构补建。
- 修卡要修到源头：正文、limitations、`origin.known_hints.usage_record` 三处都要同步（Melancholy 强度 0.75→0.5 教训：正文改了，usage_record 里"旧段落0.5不采用"的错误判断残留，等于没修干净）。

## 七、同型排查三分法（退役前必做）

退役一张卡前，按其退役理由扫全库同类：

- **A 类 裁剪/Light 冗余**：第三方 stripped/Light/裁剪版与完整版并存（文件名特征：裁剪/stripped/Light/nostrip）；
- **B 类 代际更替**：同作者同页的旧代卡与新代卡并存（按 civitai model id 分组；⚠️来源坏链会让 TSV 的 civitai_model 列为空而漏分组，Moody V7 即此类）；
- **C 类 预览相撞**：早期 preview/预览版与后续正式版并存（文件名特征：preview/预览）。

区分两组易混概念：**平行风格变体 ≠ 取代关系**（Kreamania V1-V8 是不同风格取向）；**官方双发行 ≠ 冗余**（Z-Image ControlNet 轻量+完整，轻量给低显存）。退役标注模板：`【退役标注-日期，用户确认】原因；取代者：<库内卡ID>；文件处置状态；组合引用检查结果`。退役/改名前必须 grep 组合推荐与速查目录的引用。退役**必须同时改结构化状态**：`model.status` 置为 `deprecated`（发布器合法值：candidate/partial/verified/conflict/deprecated）并重新发布——发布器会同步索引；只在 limitations 里写文字标注，速查与筛选仍会把它当正常卡（2026-09-10 实际漏过、后补 16 张）。

## 八、图片工具链

- `工具/sfw_strip.py <vid> <key> [宽] [高] [maxlv]`：按缓存版本 JSON 拼可看样图条带；自动跳过 mp4 等非位图、坏图 try/catch 跳过并报告；
- **WebP 伪装 .jpg 很常见**：System.Drawing 打不开，装 Pillow（`pip install Pillow`）批量按文件头识别转真 JPEG；
- 图内小字（阶梯红字、海报角标配方）：Pillow/PowerShell 高倍裁剪后 Read；
- 作者主页描述与版本页描述是两层，**都要读**（V4.3_EXP 的 Prompt Guide 藏在版本页描述里）。

## 九、改名前旧结论残留（第三轮逐卡自查新沉淀）

一张卡的身份段与限制段是两次不同时间的写入。**改名前/同步前**写下的限制段结论（如 `local_binding_status=not_checked`、"已查清单中未定位此精确文件"）在身份段已更新为 `verified` 之后往往没有同步，于是同一张卡自相矛盾。第三轮逐卡读图发现同一模式命中 4 张：`ae-local-afc8e28272cd`、`qwen3-local-72450b197581`、`z-image-local-5c3fe190f662`、`seedvr2-vae-fp16`。

- 判读法：身份段 `本地路径登记状态=verified` ⟺ 限制段不得再出现 `not_checked`／"未定位此精确文件"／"未复查历史路径"；
- 修法：改写限制段为当前绑定事实，并显式标注"此前旧结论已失效"，不改身份段；
- 同类信号：限制段出现"旧库存结论已失效"字样后又紧跟一条与之矛盾的句子（本轮的 `krea2-textfusion-v1` 即路径值含损坏字节）。

## 十、伪来源与来源归类（本轮命中 1 张）

`h3-weapon-combat-v1` 曾把作者页 URL 同时登记为 `repository` 与 `community` 两条来源，community 条的 publisher 写"社区用户"、`version_or_revision` 直接填时间戳，`community_feedback` 又引用该条——这是**没有独立社区证据却造出社区层**。发布器校验会拦"community_feedback 必须引用 community 类型来源"，但拦不住"同一 URL 自封 community"。

- 判读法：来源条 `kind=community` 时，其 URL 必须与 repository 条不同，且 `version_or_revision` 应是可核的帖文标识而非抓取时间戳；
- 修法：删除伪 community 来源与对应 community_feedback；确有作者页数值的，改记到 author_recommendations 的参数里（本轮 0.45 权重即如此）。
