# 中文快速开始

当前版本 `0.1.0rc1`，本地发布候选，等待独立审核。项目独立，未获 OpenAI 背书。只处理你主动指定的一份日志和可选的已有 Doctor JSON，不自动找日志、运行 Doctor、联网或上传。

在项目目录用 PowerShell 执行（已有 Python 3.11+）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --cache-dir .cache/pip -e '.[dev]'
.\.venv\Scripts\repropack.exe --version
New-Item -ItemType Directory -Force artifacts/zh-demo | Out-Null
.\.venv\Scripts\repropack.exe analyze --log examples/synthetic.log --output artifacts/zh-demo/issue.md
.\.venv\Scripts\repropack.exe analyze --log examples/synthetic.log --doctor-json examples/synthetic-doctor-v1.json --output artifacts/zh-demo/report.json --format json
```

成功提示为 `Report created; matched event lines: 6. MANUAL REVIEW REQUIRED before sharing.`。再次运行时换一个新输出名；工具不会覆盖已有文件。把 `--log` 换成你亲自选择的稳定本地文件即可分析自己的数据。没有 Doctor 文件就省略该参数，不需提供账号信息。

默认报告只保留统计、行号、可靠时间和白名单 Doctor 状态，不附原文、源文件名或路径。需要症状片段时明确加 `--include-redacted-excerpts`；当前只保留固定安全短语，每类最多 3 条、每条最多 200 字符，舍弃任意上下文。已知敏感模式的清洗不能保证识别所有秘密。发布前仍需人工检查版本、时间、业务信息和整个报告，并自行填写复现步骤。

日志限制：10 MiB / 50,000 行 / 每行原始字节 64 KiB（含 BOM 和换行）；Doctor JSON 限 1 MiB，`schemaVersion=1`，`checks` 必须是对象。仅支持严格 UTF-8 和可选初始 BOM，非法字节整份拒绝。没有明确时区不推断；一组中有不可靠时间就不输出该组绝对时间范围。

退出码：0 实际创建成功；2 参数/输入失败且无报告；3 输出不安全、冲突或已存在；5 内部或写入失败，检查选定输出位置再重试。失败尽力只清理可确认归属的本轮新文件，无法确认身份时保留。不要使用可能被并发改写、重定向的目录；路径检查并非原子快照。

完整选项、限制和实测证据见 [README](../README.md)、[验收矩阵](RC_VERIFICATION_MATRIX.md) 和 [独立审阅交接](../REVIEW_HANDOFF.md)。Windows 11、本地 Ubuntu 和远端 CI 尚未验证；正式版权、名称核对和公开发布仍待所有者处理。
