# CampusAgent

CampusAgent 是独立的 Python 智能课程客服 Agent 项目。CampusTrain 是已有的 Java
微服务业务平台，负责课程、报名和学习进度等真实业务；CampusAgent 后续通过 MCP
与 HTTP API 使用其能力，负责 RAG、工具调用、多轮对话和业务操作编排。
两个项目独立管理代码、依赖及 Git 历史，不复制 Java 实现。

当前已完成工程初始化、第二步运行环境核查和第三步知识库资料整理。首页可离线启动；第二步增加了异步
CampusTrain Gateway 客户端和真实只读接口联调。尚未实现 RAG、MCP 服务、LangGraph
工作流和数据库操作。

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
│   └── campus_client/            # 异步 Java Gateway HTTP 客户端
├── knowledge/                  # 基于 CampusTrain 源码的规则文档
│   ├── faq.md
│   ├── enrollment_rules.md
│   ├── cancellation_rules.md
│   └── learning_rules.md
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
| `CAMPUS_AGENT_KNOWLEDGE_DIR` | Markdown 知识目录，默认 `knowledge` |
| `CAMPUS_AGENT_VECTOR_DB_PATH` | Chroma 持久化目录，默认 `data/chroma` |
| `CAMPUS_AGENT_EMBEDDING_MODEL` | 本地模型，默认 `BAAI/bge-small-zh-v1.5` |
| `CAMPUS_AGENT_MODEL_CACHE_DIR` | 模型缓存目录，默认 `data/models` |
| `CAMPUS_AGENT_EMBEDDING_BATCH_SIZE` | 批量向量化大小，默认 `16` |

密钥和 JWT 使用 `SecretStr`，不在配置 repr 或 JSON 序列化中明文显示。
不要把真实凭据写入源码、日志、知识文件或评估样本；不要输出完整配置。
`.env`、本地密钥文件、数据库及其 WAL/SHM 文件、向量数据、虚拟环境和运行缓存已忽略。
不要用 `git add -f` 绕过忽略规则；向量数据应存放在默认 `data/` 或其他已忽略目录。
当前仅预留路径，不创建或连接数据库。

## 第 3 步：RAG 知识库资料

`knowledge/` 当前只存放面向后续检索的 Markdown 资料，不执行向量化、Embedding、
Chroma、Retriever、MCP 或 Agent 工作流。四份文档分别覆盖 FAQ、报名、取消报名和学习进度。
每条业务规则都带有 `CampusTrain/<模块>/<Java 文件>#<类或方法>` 来源引用；文档中明确
标注了源码没有规定的政策，避免把推测写成业务规则。

更新方式：先在 CampusTrain 实际源码中确认 Controller、Service、DTO/VO、枚举和配置的行为，
再更新对应 Markdown，并运行 `uv run --locked pytest tests/test_knowledge.py`。该检查会验证四个
必需文件、统一的 `#`/`##`/`###` 标题层级，以及每条 Source 引用的 Java/YAML 文件和符号仍存在。
CampusTrain 目录只读，不复制 Java 实现，也不在本项目中修改它。

## CampusTrain 客户端与真实联调

`CampusTrainClient` 使用 `httpx.AsyncClient`，默认关闭环境代理，支持 Gateway 地址、
Bearer JWT、请求超时、JSON 响应 envelope（`code`/`message`/`data`）解析，并将网络错误、
HTTP 错误和业务错误分别转换为客户端异常。异常文本会截断并清理常见 token、password、
secret 内容；客户端没有日志输出，也不会持久化 JWT。当前只实现读取和登录能力：

- `login`：`POST /auth/login`
- `get_training_detail`：`GET /training/get/{trainingId}`
- `get_training_catalog`：`GET /training/get/catalog/{trainingId}`
- `get_my_enrollments`：`GET /enrollment/list/mine`
- `get_training_progress`：`GET /learning/get/training-progress/{trainingId}`
- `get_lesson_progress`：`GET /learning/get-progress/{lessonId}`
- `get_chapter_progress`：`GET /learning/get/chapter-progress/{chapterId}`

取消报名 `POST /enrollment/cancel/{enrollmentId}` 本阶段只完成源码核查，没有客户端方法，
也没有执行真实取消操作。

真实联调需要将凭据仅放在当前 PowerShell 进程环境中，不写入 `.env`、测试代码或日志：

```powershell
$env:CAMPUS_AGENT_INTEGRATION_GATEWAY = "http://192.168.10.102"
$env:CAMPUS_AGENT_INTEGRATION_USERNAME = "<开发测试账号>"
$env:CAMPUS_AGENT_INTEGRATION_PASSWORD = "<开发测试密码>"
$env:CAMPUS_AGENT_INTEGRATION_TRAINING_ID = "16001"
$env:CAMPUS_AGENT_INTEGRATION_LESSON_ID = "16001"
uv run --locked pytest tests/test_integration.py -m integration -vv
```

未提供这些变量时，集成测试会明确跳过，不会使用 Mock 结果冒充真实联调。

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
  在白名单中。已通过真实 Gateway 完成只读业务接口联调，后续调用仍必须遵守该鉴权规则。
- 服务通过本地 `application.yml` 和 Nacos 环境配置组合加载，使用 `CAMPUS_ENV`、
  Nacos 地址及 namespace 等环境变量；配置组为 `CAMPUS_TRAIN`。
- 现有部署说明的虚拟机 Nginx 外部入口为 `http://192.168.10.102`（80 端口），
  本次真实联调使用 `http://192.168.10.102` 并验证了登录及列出的只读接口；配置变量仍可在后续部署时覆盖。

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

测试覆盖离线默认配置、环境变量优先级、密钥隐藏、URL 校验、Streamlit 首页渲染、
CampusTrain 客户端异常处理和知识文档来源一致性。
首页使用 Streamlit AppTest 执行实际脚本；服务启动验收还应启动 Streamlit 并检查
`/_stcore/health` 和首页 HTTP 响应。模型、MCP、RAG 和未列出的业务接口仍属于后续阶段。

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

第二步真实环境核查：VM `192.168.10.102` 的 Nginx、Nacos 和 8 个 Java 服务容器均处于运行状态，
但 Docker health 状态显示为 unhealthy；本机 8080 未监听。通过真实 Gateway 登录后，使用已有有效
报名数据的 `student01` 读取培训 `16001`、课时 `16001` 的详情、目录、我的报名、培训进度和课时进度，
`tests/test_integration.py` 实际结果为 **1 passed**。未启动、停止、重建或修改任何 CampusTrain
Docker 容器；未执行取消报名。对无有效报名的培训 `199001` 读取进度时真实返回 HTTP 403，客户端正确
转换为 `CampusHttpError`，该结果没有被伪造成成功。

CampusTrain 工作区在勘查前后均干净。本次已验证 VM Gateway 的登录和上述只读业务接口；
未验证模型、RAG、MCP、取消报名写操作或其他未列出的业务接口。

## Stage 4：本地 RAG 知识库

本阶段使用 CPU 本地 `BAAI/bge-small-zh-v1.5`，不调用付费 Embedding API，也不调用 DeepSeek。
首次构建会下载模型到 `CAMPUS_AGENT_MODEL_CACHE_DIR`，后续复用缓存；下载或加载失败会直接报错。
Chroma 使用 `CAMPUS_AGENT_VECTOR_DB_PATH` 持久化，构建会按确定性 chunk ID upsert，并删除知识目录中
已不存在的 ID，因此支持重复构建、增量更新、删除同步和进程重启后的复用。

Markdown 按 `#`、`##`、`###` 标题边界切分，每个分块保留标题路径、原文、文件路径和 Source 引用。
检索返回文本、cosine distance、文件路径、标题路径和源码引用。

```powershell
# 项目根目录
uv sync
uv run --locked python -m campus_agent.rag.cli build
uv run --locked python -m campus_agent.rag.cli query "报名后如何查看学习进度？" --top-k 3
```

首次 `build` 需要下载模型并保持网络可用，模型文件和 `data/` 不提交 Git。Fake Embedding 的
单元测试覆盖分块、重复构建、增量更新、删除同步和持久化重启；真实 BGE 验证使用：

```powershell
uv run --locked python scripts/verify_real_rag.py
```

该脚本会构建临时 Chroma 索引，并用三个中文问题检查返回片段包含预期知识主题和 Source 引用，
不会写入仓库中的 `data/`。

## 第 3 步验收记录（2026-11-06）

- 已读取 training-service、enrollment-service、learning-service 的实际 Service、VO、枚举和配置。
- `knowledge/` 四份 Markdown 均包含统一的 `#`、`##`、`###` 标题、源码 Source 引用和明确的回答边界。
- `tests/test_knowledge.py` 会检查必需文件、标题结构以及每条 CampusTrain 源码引用的文件和符号。
- 未实现向量化、Embedding、Chroma、Retriever、MCP 或 Agent 工作流。
