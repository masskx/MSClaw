# MSClaw 面试项目实现计划（自学版）

> 这份文件是唯一计划源。**代码全部由你自己实现**；每阶段完成后可找 AI 检查优化。
> 目的：通过动手搞懂 LLM Agent 应用的关键技术，并在简历/面试中讲出深度。

---

## 0. 怎么用这份计划

- 按 Phase 顺序执行，一个 Phase 内按步骤做，**每完成一小步就 commit**（养成习惯）。
- 每阶段先读「要理解的原理」→ 再看「实现步骤」→ 最后跑「验收」。
- 卡住时：把「该步骤的提示词 + 你的代码 + 报错」发给 AI 让它检查/讲解。
- 本机命令注意：
  - 没有 `uv` 命令 → 测试用 `.venv\Scripts\python.exe -m pytest`，lint 用 `.venv\Scripts\python.exe -m ruff check src/ tests/`
  - venv 里已引导好 pip（26.0.1），装包用 `.venv\Scripts\python.exe -m pip install <包>`
  - 你有 uv（项目用 uv.lock 管理），记得把 uv 加到 PATH 或用绝对路径，后续 Phase 0 需要 `uv sync`

---

## 1. 项目现状快照（已调研确认，写代码前先读）

### 现有代码结构
```
src/msclaw/
├── config.py        # Settings 数据类：env → 类型化配置，fail-fast 校验
├── agent.py         # AgentService：Claude Agent SDK 封装（核心）
├── telegram_app.py  # Telegram 轮询入口、owner 鉴权、消息分片、/start /clear
├── storage.py       # FileStorage：session_id 存 data/state.json、对话归档为 Markdown
tests/               # 13 个测试全绿
```

### AgentService 现状（P1 需要重构它，先读懂）
- `run(prompt, bot, chat_id)`：异步迭代 `query()` 返回的消息流，遇到 `ResultMessage` 时保存 session_id 并返回 `result`。
- `_build_options(bot, chat_id)`：
  - `allowed_tools` 白名单：Read/Write/Edit/Glob/Grep/WebSearch/WebFetch/Bash + MCP `send_message`
  - `permission_mode="acceptEdits"`
  - `agents={"coder": ...}` 子代理
  - `mcp_servers={"assistant": create_sdk_mcp_server(...)}` → 让 agent 能主动发进度消息给用户
  - `system_prompt` 从 `workspace/CLAUDE.md` 读
- `_lock = asyncio.Lock()`：全局串行执行（单用户所以够用）。
- 关键 API：`query(prompt, options)` 返回**异步迭代器**；`ClaudeAgentOptions(resume=session_id)` 续接会话。

### 依赖现状（已装好，别再装）
已装：`claude-agent-sdk 0.2.128`、`python-telegram-bot 22.6`、`langgraph 1.2.9`、
`langgraph-checkpoint-sqlite`（提供 aio 后端）、`langchain`、`langchain-openai`、
`fastapi 0.141.1`、`uvicorn 0.51.0`、`httpx`、`httpx-sse`、`aiosqlite`、
`apscheduler`、`croniter`、`openai`。

未装（需要时再装）：`chromadb`（Phase 4）、`langfuse`（Phase 5 可选）。

### 已验证的 API 细节（省得你踩坑）
- `from langgraph.graph import StateGraph, START, END` ✅
- `from langgraph.types import interrupt, Command` ✅（HITL 用）
- `from langgraph.checkpoint.memory import InMemorySaver` ✅（测试用）
- `from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver` ✅
  - `AsyncSqliteSaver.from_conn_string(path)` 是**异步上下文管理器**（async with）
  - 也可 `AsyncSqliteSaver(await aiosqlite.connect(path))` 后 `await saver.setup()`
  - **注意：`langgraph.checkpoint.sqlite`（同步版）未安装**，不要用 `SqliteSaver`
- 挂起判断：`snapshot = await graph.aget_state(config)`，`snapshot.next` 为空 = 跑完了；`["wait_approval"]` = 等人审批；`snapshot.interrupts[0].value` 拿 interrupt 载荷
- 恢复：`await graph.ainvoke(Command(resume=True/False), config)`，`config={"configurable": {"thread_id": "..."}}`
- python-telegram-bot 22.6：`CallbackQueryHandler` + `InlineKeyboardButton(text, callback_data=...)`，callback_data **≤64 字节**

### 已完成的 P0（commit f83dced，保留作为参考）
- 删除了 ep1~ep6.py 教程快照
- 新增 `.gitignore` 更新（忽略 data/ workspace/）、`Dockerfile`、`.dockerignore`、`docker-compose.yml`（bot + web 两个服务）、`.github/workflows/ci.yml`
- `pyproject.toml` 已声明 `fastapi`、`uvicorn`、`langgraph-checkpoint-sqlite`

> ⚠️ **遗留问题（你要做的第一件事）**：pyproject 加了新依赖但 **uv.lock 没同步**，
> Dockerfile 里 `uv sync --frozen` 会失败。跑一次 `uv sync`（会更新 uv.lock）解决。

---

## 2. 已确认的设计决策（面试也会问，先想明白）

1. **岗位方向：AI 应用 / LLM 工程师**。简历主线一句话：把单机个人助手演进为带
   LangGraph 多步工作流、人工审批（HITL）、RAG 记忆、SSE 流式 Web API 的 AI Agent 平台。
2. **部署在境内服务器** → 线上演示以 **Web 通道为主**（Telegram 在境内连不上
   `api.telegram.org`；如要 bot 上服务器，需在 `.env` 配 `HTTP_PROXY`/`HTTPS_PROXY`）。
3. **架构**：Claude Agent SDK 仍是执行引擎；**LangGraph 只做审批式工作流编排**
   （`/task` 命令），普通对话仍走原 `AgentService` 路径 → 避免两套 agent 循环打架。
4. **不做**：多用户、Redis 缓存、SDK 权限钩子改造（时间预算不够，且不是面试重点）。

---

## Phase 1 — LangGraph 多步工作流 + 人工审批（核心故事，最重要）

目标：`/task 写一篇周报草稿` → agent 起草 → Telegram 内联键盘「批准/拒绝」→ 批准后执行。
进程重启后，挂起的审批仍能通过旧按钮恢复（checkpoint 的卖点）。

### 要理解的原理
- **StateGraph**：节点 = 函数（吃 state 吐增量），边 = 路由。`add_conditional_edges` 做分支。
- **interrupt()**：langgraph 的官方 HITL 原语。节点内 `interrupt(payload)` 会让图暂停并持久化；
  外部用 `Command(resume=value)` 恢复。比自建等待机制优雅，面试必讲。
- **Checkpointer**：把每个节点的 state 快照落库（SQLite）。有了它才能跨进程恢复。
- **thread_id**：LangGraph 用 config 里的 `thread_id` 区分多个并行图实例。

### 实现步骤

**1.1 新建 `src/msclaw/transport.py`**（P2 也用它，先做）
- `ProgressReporter` Protocol：`async def send(self, text: str) -> None`
- 三个实现：`NoopProgressReporter`（测试）、`TelegramProgressReporter(bot, chat_id)`、
  `QueueProgressReporter`（P2 SSE 用，内部 `asyncio.Queue`）

**1.2 重构 `src/msclaw/agent.py`**
- `AgentService.run(prompt, reporter)`，替换现在的 `run(prompt, bot, chat_id)`
- `_build_options(reporter)`，MCP 的 `send_message` 工具改为调用 `reporter.send(text)`
- `_telegram_tools(bot, chat_id)` 改名 `_messaging_tools(reporter)`
- 同步更新 `telegram_app.py` 的 `handle_message`：构造 `TelegramProgressReporter(context.bot, chat.id)` 传入

**1.3 新建 `src/msclaw/workflows/` 包**
- `state.py`：`AgentWorkflowState`（TypedDict，total=False）：`task, plan, result, approved,
  needs_approval, attempts, error, status`
- `graph.py`：`build_workflow(agent_runner) -> StateGraph`，节点与路由：
  ```
  START → plan → act → check ──(有结果)──→ wait_approval ──(批准)──→ execute → done
                        ↑        │                                            │
                        └─(空结果重试, 最多2次)─┘             (拒绝) → rejected → END
                                       (超过次数) → failed → END
  ```
  - 节点提示词（你的设计，可优化）：
    - plan：让 agent 只输出执行计划，不执行
    - act：输出方案**草稿**，明确禁止写文件/副作用
    - execute：告知"方案已获批准，正式执行（可写文件）"
  - `wait_approval` 节点核心（三行）：
    ```python
    def wait_approval(state):
        approved = interrupt({"task": state["task"], "preview": state["result"]})
        return {"approved": bool(approved)}
    ```
  - 条件路由函数：`route_after_check`（成功→wait_approval / 重试→act / 超限→failed）、
    `route_after_approval`（approved→execute / 否则→rejected）
- `service.py`：`WorkflowService`（见 1.4）
- `__init__.py`：导出 WorkflowService

**1.4 `WorkflowService` 设计**
- 构造：`WorkflowService(agent_runner, storage, db_path, timeout_seconds=300)`
  - `agent_runner`：`Callable[[str], Awaitable[str]]`，由调用方 `partial(agent.run, reporter=...)` 构造 → 测试时注入假 runner
- 懒初始化（build_application 是同步的，不能在构造里 async）：
  `async def _ensure_graph()`：打开 aiosqlite 连接 → `AsyncSqliteSaver(conn)` → `await saver.setup()` →
  `build_workflow(runner).compile(checkpointer=saver)`，缓存 `self._graph`
- `async def start(task, chat_id, *, now=None) -> dict`：
  生成 thread_id（uuid4）→ 记 `workflows.json`（含 task、chat_id、created_at、expires_at、status）→
  `ainvoke({...}, config)` → 读 `aget_state(config)`：
  - `next == ["wait_approval"]` → 返回 `{"status": "pending_approval", "preview": ...}`
  - 否则返回终态（done/failed/rejected + result/error）
- `async def decide(thread_id, approved, *, now=None) -> dict`：
  校验存在 → 校验 `expires_at`（**惰性超时**：过期直接标 expired 不恢复图）→
  `ainvoke(Command(resume=approved), config)` → 返回终态 → 清理 workflows.json 记录
- `pending_workflows()`：列出挂起记录（后续 /tasks 命令或定时清理用）

**1.5 `storage.py` 加方法**
- `workflows_file` 属性：`data/workflows.json`
- `load_workflows() -> dict[str, dict]`（文件缺失/损坏返回 {}）
- `save_workflow(thread_id, record)`、`delete_workflow(thread_id) -> bool`
- 顺手重构：把 state.json 的「写临时文件 + os.replace」抽成 `_atomic_write_json(path, payload)`

**1.6 `telegram_app.py` 集成**
- `build_application`：创建 `WorkflowService`（runner 用 `partial(agent.run, reporter=...)`，
  reporter 需要 bot → 用工厂 `lambda chat_id: TelegramProgressReporter(bot, chat_id)`，
  在 handler 里才有 bot，自己想办法传，比如 handler 方法内构造并赋给 service 的 `current_reporter`）
- `CommandHandler("task", ...)`：解析描述 → `start()` → 若 pending_approval：
  发送「预览（截断 200 字符）+ 内联键盘」；`InlineKeyboardButton("✅ 批准", callback_data=f"wf:{tid}:approve")` / 拒绝同理
- `CallbackQueryHandler(pattern="^wf:")`：解析 thread_id 和决定 → owner 校验 →
  `decide()` → 发送结果 → `answer_callback_query` 消掉按钮转圈
- 超时语义：decide 时惰性判断过期 → 回「已超时，任务自动取消」

**1.7 测试（`tests/workflow/`）**
- `test_graph.py`：用 `InMemorySaver` + 假 runner（返回固定字符串），断言：
  - happy path：start → `aget_state` 停在 wait_approval → `Command(resume=True)` → 终态 done，result 是 execute 的输出
  - reject：resume=False → 终态 rejected
  - 重试：runner 先返回两次空 → 终态 failed（attempts==2）
- `test_workflow_service.py`：tmp 目录建 service，测 start/decide/过期/记录清理

### 验收
- Telegram 发 `/task 写一篇周报草稿保存到 workspace` → 收到预览+键盘 → 批准后文件生成；
- **杀掉进程重启**，点旧的批准按钮 → 任务继续完成（checkpoint 恢复）；
- `pytest` 全绿、`ruff` 干净。

### 面试要点
为什么审批节点放图内而不是 SDK 权限钩子？超时/拒绝/重试的状态语义？重启恢复的原理？

---

## Phase 2 — FastAPI + SSE Web 通道

目标：同一个 AgentService 暴露 Web API：`/health`、`/chat`、`/chat/stream`（SSE 流式），
带一个单文件聊天页。这是部署后的 live demo。

### 要理解的原理
- **SSE vs WebSocket**：SSE 单向服务器推送、基于 HTTP、EventSource 自动重连；WebSocket 全双工。
  LLM 流式输出用 SSE 足够且简单。面试必被问对比。
- **StreamingResponse**：FastAPI 返回 `StreamingResponse(generator, media_type="text/event-stream")`。
- **EventSource 只支持 GET** → `/chat/stream` 用 GET（消息放 query 参数），鉴权放 header 或 query。

### 实现步骤
1. `src/msclaw/web/__init__.py`、`app.py`：
   - `create_app(settings, storage, agent) -> FastAPI`（工厂，方便测试注入）
   - `GET /health`：bot 状态 + workspace 路径 + 版本
   - `POST /chat`：`{"message": str}` → `agent.run(msg, NoopProgressReporter())` → 返回完整文本
   - `GET /chat/stream?message=...`：建 `QueueProgressReporter` → 后台任务跑 `agent.run` →
     generator 里 `queue.get()` 逐步 yield `data: {json}\n\n` → 结束 yield `data: [DONE]\n\n`
   - 鉴权：`WEB_TOKEN` env（Bearer header）；测试里可以直接关掉
2. `src/msclaw/web/static/index.html`：单文件，输入框 + 消息区 + `new EventSource(url)` 流式渲染。
   FastAPI `StaticFiles(html=True)` 挂载。
3. `config.py` 加 `web_token: str | None`（env `WEB_TOKEN`，可选）。
4. `tests/test_web.py`：`httpx.AsyncClient(transport=ASGITransport(app=create_app(...)))`；
   测 /health、/chat；SSE 用 `httpx_sse.aconnect_sse`（**已装**）测流式输出。
   假 agent：注入一个 fake（注意：agent.run 是 async 且需要 reporter——测试注入假 AgentService 或 monkeypatch）。
5. 可选：加 CORS 中间件（如果前端要跨域托管）。

### 验收
`uvicorn msclaw.web.app:app --port 8000` → 浏览器开 `http://127.0.0.1:8000` 流式对话；
pytest 全绿。

### 面试要点
SSE 选型、传输层抽象（Transport/Reporter 让 Telegram 与 Web 共用 AgentService）、
`AgentService._lock` 的全局串行语义。

---

## Phase 3 — 部署到境内服务器

1. 服务器装 Docker + compose（国内可配镜像加速）。
2. `docker compose up -d --build`。**只起 web 服务**（`docker compose up -d web`）：
   Telegram bot 在境内连不上 api.telegram.org，除非 `.env` 里配好可用代理（httpx 自动读
   HTTP_PROXY/HTTPS_PROXY）。
3. 防火墙放行 8000，浏览器打开 `http://<服务器IP>:8000` 验证。
4. 有已备案域名可加 nginx 反代 + HTTPS（可选）。
5. 录 30 秒演示视频 + README 加截图和链接。

### 验收
手机流量/电脑浏览器都能打开链接完成一次流式对话。

---

## Phase 4 — RAG 记忆系统（时间不够可后置）

目标：把 `workspace/conversations/*.md` + `CLAUDE.md` 建成向量知识库，agent 运行前自动检索注入上下文。
面试第三亮点：问「我上次说过喜欢什么颜色」能答出来（靠检索而不是 session）。

### 要理解的原理
- RAG 链路：文档 → 切分(chunk) → embedding → 向量库 → 检索 top-k → 拼 prompt。
- 切分策略：按 Markdown 标题/长度混合；chunk 太小没上下文、太大检索不精准。
- 为什么不能只靠 CLAUDE.md：它是"手动记忆"，RAG 是"自动记忆"。

### 实现步骤
1. 安装 `chromadb`，pyproject 声明（版本问 AI 或装最新稳定）。
2. `src/msclaw/rag/`：
   - `embeddings.py`：OpenAI 兼容客户端，env 配置 `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` /
     `EMBEDDING_MODEL`（境内推荐 SiliconFlow/智谱/DashScope 的兼容端点；没 key 先用假 embedding 跑通链路）
   - `indexer.py`：扫描文档 → `RecursiveCharacterTextSplitter`（langchain）→ 写入 ChromaDB（持久化目录 `data/chroma`）
   - `retriever.py`：`search(query, k=4) -> list[str]`
   - `router.py` 或直接在 AgentService 里：`run()` 前检索 → 结果拼进 prompt 前缀
3. `/reindex` 命令（Telegram + Web 都能触发）；启动时若库为空自动建索引。
4. 测试：mock embedding 函数，断言「写入→检索命中」。

### 验收
问关于历史对话的问题能引用到正确内容；`/reindex` 后新对话立即可检索。

### 面试要点
切分策略取舍、检索注入时机（prompt 前缀 vs system prompt）、向量库选型理由、混合检索（关键词+向量，可选加分）。

---

## Phase 5 — 加分项（最后做，时间不够砍掉）

1. **定时任务**：apscheduler + croniter（已装）。`/schedule "每天9点 晨报"` → cron 解析 →
   到点让 agent 生成晨报推送到 Telegram。展示异步任务与 agent 结合。
2. **Langfuse 追踪**（可选）：装 langfuse，包一层 AgentService 记录 token 用量、延迟、
   工具调用链。面试关键词：可观测性。

---

## 风险与对策

| 风险 | 对策 |
|---|---|
| Telegram 在境内不可达 | 演示以 Web 为主；bot 走代理或本地跑 |
| LangGraph 与 Claude SDK 集成复杂度 | 工作流只做审批式任务；普通对话走原路径 |
| interrupt 恢复行为和你预期不同 | 先写 test_graph.py 验证再联调 Telegram |
| 境内 embedding 端点没有 | env 可配置；先用假 embedding 通链路 |
| uv.lock 未同步 | 开工前先 `uv sync` |

## 面试投递前清单

- [ ] `uv sync` 更新 uv.lock；pytest 全绿、ruff 干净；CI 绿
- [ ] README：架构图 + 技术亮点 5 行 + 演示链接 + 截图
- [ ] 能手画 Phase 1 的状态机图
- [ ] 三个故事：HITL（超时/拒绝/恢复）、SSE 与传输抽象、RAG 链路
- [ ] 仓库公开（workspace/data 已 gitignore，无个人信息泄漏）
