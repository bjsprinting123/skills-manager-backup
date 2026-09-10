# 官方只读核验后端（一期）

## 分工与入口

现有分析器继续负责 UI/API 区分、子图、原值、位置控件与证据文档。官方 `comfy-cli==1.20.0` 是补充核验，不替换解析结果，不完成节点研究或十章文档验收。

本机独立解释器：`E:\tools\comfyui-audit\.venv\Scripts\python.exe`。
工具不安装进 ComfyUI 环境，不注册 MCP，不安装其他 Skills，不下载模型。

统一入口（输出目录必须新建）：

```powershell
& 'E:\tools\Python312\python.exe' '<skill-dir>\scripts\prepare_run.py' '<workflow.json>' '<new-run-directory>'
```

默认尝试独立后端，执行版本核实和 UI 作者备注提取；未安装时保留 `tool_ready=false`，不能声明官方检查通过。`--no-official-cli` 明确禁用补充核验。

- 已取得与目标环境对应的 `/object_info` 文件：加 `--object-info '<snapshot.json>'` 才执行离线预检。未提供时记录 `NOT_VERIFIED`，不偷偷连默认服务器。
- 检查本机 Python 依赖：同时加 `--comfyui-root '<ComfyUI-dir>' --comfyui-python '<actual-python.exe>'`。先确认这两个路径属于同一安装，不猜 venv、不使用审计工具自己的 Python 代表生产环境。
- 其他 Windows 机器可用 `--cli-python '<isolated-python>'`；只接受已验收的 1.20.0，升级版本先重新测试。本期配置隔离只验收 Windows，其他系统拒绝调用后端。
- 后补证据可对已有输入快照调用 `scripts/collect_cli_evidence.py <snapshot.json> <run-directory> [同上参数]`。已有官方证据时拒绝覆盖，应使用新 run。

## 真正调用的内容

| 检查 | 后端与界限 |
|---|---|
| 版本 | 独立解释器的 `importlib.metadata.version('comfy-cli')`，不是运行 `comfy --version` |
| 作者 Notes | 官方 `comfy --json --skip-prompt --where local workflow notes <UI.json>`；API 缺少画布 Notes，记 `not_applicable`，不推断 API 中没有任何作者信息 |
| 校验 | 官方 `workflow validate --workflow <json> --input <object_info.json>`；读取 `data.valid/errors/warnings`，不只根据退出码或通用 error.code 猜原因 |
| Python 依赖 | 官方 `comfy_cli.command.node_deps.build_report(root, python=explicit_python, refresh=False)`；这是官方库接口，不声称执行过 `node deps` CLI |
| 节点包映射 | 本期 `not_verified`；不调用 Manager 委托型 `node deps-in-workflow`，继续按原 Skill 使用 properties、源码与权威资料交叉核实 |

依赖接口仅执行目标 Python 的 `-m pip list --format=json` 并读取声明文件，不导入 Torch/自定义节点、不安装依赖。目标 Python 的正常启动仍可能加载其 site 配置；这是一次本机只读诊断，不是完全不启动目标解释器。必须核对结果中的 `data.python`。条件 marker 未求值、`-r` 未递归、无效版本等限制须人工复核；`missing` 不自动证明当前故障。

## 隔离与证据

1. 固定子进程白名单：版本、Notes、离线 validate、显式目标依赖。没有运行、修复、安装、更新、云端或付费入口。
2. 1.20.0 没有官方配置目录参数。worker 在导入 `cmdline/ConfigManager` 前，在**子进程内存**中重定向 `constants.DEFAULT_CONFIG[constants.OS.WINDOWS]` 到该 run 的 `official-cli/state`；不修改官方包源码，也不修改现有用户配置。这是本地适配手段，不是官方 CLI 选项。
3. worker 设置 `DO_NOT_TRACK=1`、`COMFY_NO_TELEMETRY=1`、`COMFY_CLI_NO_REMOTE_REFRESH=1`、`COMFY_NO_CACHE=1`，禁遥测和附带注释刷新；审计 hook 拒绝 worker 网络连接。目标 pip 使用 `PIP_NO_INDEX=1` 与禁版本检查，不请求网络。
4. 官方校验可能把 UI 临时转成 API；该转换只作补充，不回写原 JSON，不把转换结果当作权威 widget 字段映射。
5. 输出 `02-机器解析/06-官方CLI核验.json`，并在 `05-外部查证/official-cli` 保存脱敏后的命令、返回、退出码和内容哈希，追加到 `03-证据台账.json`。不打印原始 stdout 或凭据。
6. `preflight_status=PASS` 仅是指定 schema 下静态预检；`runtime_execution` 始终为 `not_performed`。它不是文档 `99-验收报告.json`，也不是实际生成成功。
7. `node_types_absent_from_supplied_schema` 只证明不在**所提供快照**中；先核对快照来源、时间、版本，不能直接声称当前机器缺节点。测试用 synthetic schema 不得当本机库存。
8. `candidate_dangling_links` 保留 API 中指向缺失 ID 的二元素数组。未知节点时官方校验可能在类型错误处短路；这些项是待 schema 确认的疑似断链，也可能是字面量数组，不把它们强行计为已证实连线或普通执行参数。将该歧义带入节点查证矩阵。
9. 损坏的 object_info 标为 `invalid_input`，静态结论保持 `NOT_VERIFIED`；保留原 JSON 解析和 CLI 诊断，不伪造通过。

## 已核查的官方来源

- [PyPI 1.20.0](https://pypi.org/project/comfy-cli/1.20.0/)
- [官方 workflow 命令](https://github.com/Comfy-Org/comfy-cli/blob/v1.20.0/comfy_cli/command/workflow.py)
- [官方依赖报告接口](https://github.com/Comfy-Org/comfy-cli/blob/v1.20.0/comfy_cli/command/node_deps.py)
- [配置初始化](https://github.com/Comfy-Org/comfy-cli/blob/v1.20.0/comfy_cli/config_manager.py)
- [注释刷新控制](https://github.com/Comfy-Org/comfy-cli/blob/v1.20.0/comfy_cli/cql/annotations_source.py)

官方发布 commit：`00230f303cbbd8f801987146424e6c61f1f3254e`。主分支文档可能变化，运行判断以固定包和实际返回为准。
