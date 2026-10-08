# 队友测试说明

本压缩包包含项目源码、依赖清单、自动化测试，以及 `测试素材/` 下的演示图片。完整设计与接口说明见 [README.md](README.md)。请先按下列步骤在自己的电脑上启动。

## 1. 准备环境

- 安装 Python 3.11、3.12 或 3.13，并确保 `python`（Windows）或 `python3`（macOS/Linux）可在终端运行。
- 解压压缩包，进入 `pv-underwriting-ai` 目录。以下命令均在此目录执行。
- 安装依赖需要联网；模型识别还需要队友自己的、可用的视觉模型 API Key。

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
notepad .env
```

macOS/Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Python 3.12 只是示例；Windows 如果没有 3.12，可把第一条命令改成已安装的 3.11 或 3.13。PowerShell 禁止激活脚本时，可以直接使用 `.\.venv\Scripts\python.exe` 执行后续 Python 命令。

## 2. 配置模型

在本机 `.env` 中填写自己的 `PV_VLM_API_KEY`。默认模型地址和名称见 `.env.example`；如果你的账号使用其他兼容地址或模型，同步修改 `PV_VLM_BASE_URL` 和 `PV_VLM_MODEL`。不要把填好密钥的 `.env` 回传或放入共享压缩包。

没有 API Key 仍可查看页面、运行 Mock 接口和自动化测试；真实 OCR、图片自动分类和视觉风险识别需要可用的模型服务。

**不要使用 `python run_evaluation.py` 作为队友启动方式。**该脚本读取原作者电脑上的固定路径，其他电脑通常找不到密钥。请使用下面的通用命令。

## 3. 启动与测试

```bash
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

浏览器打开：

| 页面 | 地址 | 用途 |
| --- | --- | --- |
| 材料评测台 | http://127.0.0.1:8000/ | OCR、视觉及整条链路测试 |
| 风险识别实验室 | http://127.0.0.1:8000/vision-lab | 单图/批量视觉风险测试；**不调用 OCR** |
| 接口文档 | http://127.0.0.1:8000/docs | 手动调用接口 |
| 健康检查 | http://127.0.0.1:8000/health | 确认服务已启动 |

`测试素材/莘县厂房屋顶/` 包含 9 张现场照片和 1 张**模拟**备案信息单；`测试素材/三组样本/` 包含 A/B/C 三组材料。请先读每个素材目录中的说明。模拟备案信息单仅用于测试，不能当成真实备案证明。

在 `/vision-lab` 中，备案信息、并网许可等文件照可能被自动分类为“其他照片”，一键风险测评会停止；请到 `/evaluation` 测试其 OCR。照片或设备铭牌可在视觉实验室测试。出现“失败”时，选中图片并展开左侧“分类详情”，记录“上次测评失败”的完整文字。浏览器实验室的测试图片和记录保存在当前浏览器的 IndexedDB，换电脑或清理站点数据后不会自动同步。

## 4. 自动化检查与反馈

```bash
python -m pytest -q
```

反馈问题时请附：使用的 Python 版本、操作系统、页面地址、操作步骤、素材文件名、页面完整错误文字，以及服务终端中对应时段的报错。请不要附 API Key、`.env` 或其他人的真实投保资料。

已知边界：这些测试素材不能证明模型识别准确率或核保规则达到比赛验收指标；需要有标注真值的测试集再评估。
