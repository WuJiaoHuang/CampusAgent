# CampusAgent

CampusAgent 是独立的 Python 智能课程客服 Agent 项目。CampusTrain 是已有的 Java
微服务业务平台，负责课程、报名和学习进度等真实业务；CampusAgent 后续通过 MCP
与 HTTP API 使用其能力，负责 RAG、工具调用、多轮对话和业务操作编排。
两个项目独立管理代码、依赖及 Git 历史，不复制 Java 实现。

当前仅完成第一步：Python 工程初始化。首页可离线启动，无需模型密钥、JWT 或
CampusTrain 在线。尚未实现 RAG、MCP 服务、LangGraph 工作流、业务接口调用和数据库操作。

## 技术方案与目录

Python 3.12、uv、Streamlit、pydantic-settings、httpx；为后续阶段安装 LangGraph、
LangChain（含 OpenAI 兼容模型适配）、Chroma、MCP Python SDK。SQLite 使用 Python 标准库。
pytest 和 Ruff 用于测试及代码检查。本项目不依赖额外的 Docker、MySQL、Redis 或 RabbitMQ。

```text
CampusAgent/
├── app.py                       # Streamlit 首页
├── pyproject.toml               # 项目、依赖和检查配置
├── uv.lock                      # 可复现的依赖锁文件
├── .python-version              # Python 3.12
├── .env.example                 # 环境变量示例
├── .gitignore
├── src/campus_agent/
│   ├── __init__.py
│   ├── config.py                # 环境配置
│   ├── agent/__init__.py        # 后续工作流和记忆
│   ├── rag/__init__.py          # 后续检索
│   ├── mcp_server/__init__.py   # 后续 MCP Server
│   └── campus_client/__init__.py # 后续 Java HTTP 客户端
├── knowledge/.gitkeep          # 后续规则知识文件
├── evals/.gitkeep              # 后续效果评估
└── tests/
    ├── test_config.py
    └── test_app.py
```

## 安装与启动（Windows PowerShell）

在项目根目录执行。下列命令使用 uv 管理项目独立的 `.venv`。

```powershell
python --version
# 缺少 Python 3.12 时，先安装 Python 3.12；缺少 uv 时执行：
python -m pip install --user uv
uv --version
uv sync --locked
Copy-Item .env.example .env
uv run --locked streamlit run app.py
```

浏览器访问 <http://localhost:8501>，在终端按 Ctrl+C 停止。uv 在项目内创建 `.venv`，
默认安装开发依赖。无需手动激活虚拟环境；`uv.lock` 应提交 Git。

本次本机安装中，Codex 桌面环境将部分 `C:` 用户路径重定向到 `D:`，导致
`pip install --user uv` 和默认 uv 缓存发生跨盘文件移动错误。已将 uv 成功安装到
`D:\Tools\CampusAgent\uv`，其 `bin` 目录已加入用户 PATH；重新打开终端后生效。
当前终端若找不到 uv，可执行：

```powershell
$env:Path = "D:\Tools\CampusAgent\uv\bin;$env:Path"
uv --version
```

项目通过 `pyproject.toml` 将 uv 缓存放在已忽略的 `.uv-cache/` 中，避免重定向问题。
其他机器可正常安装 uv，无需使用上述本机专用路径。

## 配置与安全

`src/campus_agent/config.py` 的 `Settings()` 按“进程环境变量 > 当前工作目录的
`.env` > 默认值”读取配置，因此启动命令应在项目根目录运行。初始化页面不实例化模型或
客户端，也不发出外部请求。

| 环境变量 | 用途 |
| --- | --- |
| `CAMPUS_AGENT_LLM_API_KEY` | 后续模型 API Key，当前可留空 |
| `CAMPUS_AGENT_LLM_BASE_URL` | 后续 OpenAI 兼容接口地址 |
| `CAMPUS_AGENT_LLM_MODEL` | 后续模型名称，当前可留空 |
| `CAMPUS_AGENT_GATEWAY_URL` | 业务入口，默认 `http://localhost:8080` |
| `CAMPUS_AGENT_JWT_TOKEN` | 后续用户 JWT，当前可留空 |
| `CAMPUS_AGENT_SQLITE_PATH` | 预留本地 SQLite 路径 |
| `CAMPUS_AGENT_CHROMA_PATH` | 预留本地向量数据目录 |

密钥和 JWT 使用 `SecretStr`，不在配置 repr 或 JSON 序列化中明文显示。
不要把真实凭据写入源码、日志、知识文件或评估样本；不要输出完整配置。
`.env`、本地密钥文件、数据库及其 WAL/SHM 文件、向量数据、虚拟环境和运行缓存已忽略。
不要用 `git add -f` 绕过忽略规则；向量数据应存放在默认 `data/` 或其他已忽略目录。
当前仅预留路径，不创建或连接数据库。

## CampusTrain 只读勘查记录

本次检查的本地项目为 `D:\HuaweiMoveData\Users\HW\Desktop\CampusTrain`，
分支 `master`，基线提交 `9b38337`。只读查看模块、路由、鉴权及必要配置；未修改源码，
未启动或停止 Java 服务，未连接虚拟机或操作 Docker。

- 根 Maven 工程包含 `campus-gateway`、`training-service`、`enrollment-service`、
  `learning-service`、`user-service`、`auth-service`、`growth-service` 和 `community-service`。
- Gateway 本地配置端口为 `8080`，通过 `lb://` 路由到各服务，保留业务路径。
  课程相关路径包括 `/training/**`、`/course/**`、`/chapter/**`、`/lesson/**`、`/video/**`；
  报名与学习路径分别为 `/enrollment/**`、`/learning/**`。
- Gateway 校验 Bearer JWT；登录 `POST /auth/login` 和健康检查 `GET /actuator/health`
  在白名单中。后续业务调用必须遵守真实鉴权规则。
- 服务通过本地 `application.yml` 和 Nacos 环境配置组合加载，使用 `CAMPUS_ENV`、
  Nacos 地址及 namespace 等环境变量；配置组为 `CAMPUS_TRAIN`。
- 现有部署说明的虚拟机 Nginx 外部入口为 `http://192.168.10.102`（80 端口），
  可在后续联调时设置为 `CAMPUS_AGENT_GATEWAY_URL`。本阶段未验证其运行状态和连通性。

## 检查命令

```powershell
uv sync --locked
uv run --locked python --version
uv pip check
uv run --locked pytest
uv run --locked ruff check .
git diff --check
git status --short
```

测试覆盖离线默认配置、环境变量优先级、密钥隐藏、URL 校验与 Streamlit 首页渲染。
首页使用 Streamlit AppTest 执行实际脚本；服务启动验收还应启动 Streamlit 并检查
`/_stcore/health` 和首页 HTTP 响应。以上检查不证明模型、MCP、RAG 或真实业务接口可用，
这些能力属于后续阶段。

## 本次验收记录（2026-11-05）

| 检查 | 实际结果 |
| --- | --- |
| Python / uv | Python 3.12.1 / uv 0.13.7 |
| `uv sync --locked` | 成功，锁定环境已同步 |
| `uv pip check` | 132 个已安装包兼容性检查通过 |
| 核心依赖导入 | 上述 8 个运行依赖及 pytest、Ruff 均导入成功，标准库 SQLite 可用 |
| `uv run --locked pytest` | 6 passed，包含首页实际脚本渲染 |
| `uv run --locked ruff check .` | All checks passed |
| Streamlit 实际服务 | 在本机临时端口启动；健康检查为 HTTP 200 / ok，首页为 HTTP 200 / HTML；验收后已关闭 |
| Git | 忽略规则检查通过；暂存内容无密钥、数据库或缓存；空白检查通过 |

CampusTrain 工作区在勘查前后均干净；本次未验证虚拟机、模型或业务接口。
