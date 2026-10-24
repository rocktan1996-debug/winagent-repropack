# WinAgent ReproPack｜中文快速开始

目前已有公开预览版 [v0.1.0rc1](https://github.com/rocktan1996-debug/winagent-repropack/releases/tag/v0.1.0rc1)。它是一个离线 Python 命令行工具，帮助把用户主动选择的 AI 编程工具日志整理为 Markdown 或 JSON 格式的故障报告。项目独立于 OpenAI，并非官方产品。

**第一次使用，请只运行项目自带的合成日志。不要公开真实 Codex 日志、凭据、Doctor 诊断数据或未经审查的报告。**

## 1. 下载与安装

需要 Python **3.11 或更高版本**。在上面的 Release 页面下载 `Source code (zip)` 并解压；在包含 `pyproject.toml` 与 `examples/` 的目录里打开终端。

### Windows（PowerShell）

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
New-Item -ItemType Directory -Force artifacts | Out-Null
.\.venv\Scripts\repropack.exe --version
.\.venv\Scripts\repropack.exe analyze --log examples/synthetic.log --output artifacts/first-run.md
```

### Ubuntu / Linux（终端）

```bash
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install .
mkdir -p artifacts
.venv/bin/repropack --version
.venv/bin/repropack analyze --log examples/synthetic.log --output artifacts/first-run.md
```

安装依赖可能需要网络，但分析日志本身不联网，也不会自动上传数据。若系统中 Python 版本低于 3.11，请使用你已安装的 3.11+ 解释器。

## 2. 查看结果

成功时应显示 `Report created; matched event lines: 6. MANUAL REVIEW REQUIRED before sharing.`，然后打开 `artifacts/first-run.md`。示例共有 6 条匹配事件，是纯合成数据，不代表发生过真实故障。

工具不会覆盖已存在的报告，因此再次运行请改用新的输出文件名。

如需体验 JSON 输出，可将 `analyze` 命令改为：

```text
analyze --log examples/synthetic.log --doctor-json examples/synthetic-doctor-v1.json --format json --output artifacts/first-run.json
```

在上述命令前加上当前平台对应的可执行文件路径：Windows 是 `.\.venv\Scripts\repropack.exe`，Linux 是 `.venv/bin/repropack`。这里的 Doctor JSON 同样是虚构测试数据。

## 3. 安全反馈

可以自愿提交真实的试用体验：阅读 [安全试用反馈说明](USER_FEEDBACK.md)，然后在 [GitHub Issues](https://github.com/rocktan1996-debug/winagent-repropack/issues/new/choose) 提交遇到的安装问题或改进建议。

请只使用合成测试内容，**不要上传私密日志、访问令牌、私人文件路径、账号信息或未复核的截图**。安全漏洞请使用 [私密漏洞报告渠道](../SECURITY.md)，不要公开到 Issues。

## 4. 使用边界

默认输出包含类别、次数、行号、部分时间和经过限制的 Doctor 状态数据，不包含原始完整日志，但**人工检查报告仍然必需**。工具并不能保证识别所有敏感信息，也不会自动运行 Doctor 或证明根因。

日志上限为 10 MiB、50,000 行及每行 64 KiB；Doctor JSON 上限为 1 MiB。已有输出文件不会被覆盖；分析期间应使用稳定的本地普通文件和目录。详细限制见 [README](../README.md)、[安全说明](../SECURITY.md) 与 [报告字段结构](REPORT_SCHEMA_V1.md)。

[Windows 和 Ubuntu，Python 3.11/3.12 CI 通过记录](https://github.com/rocktan1996-debug/winagent-repropack/actions/runs/39994953117)。这不代表已单独验证所有 Windows 11 配置或所有 AI 编程日志格式。
