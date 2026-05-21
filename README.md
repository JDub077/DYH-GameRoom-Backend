# 明舟北渡 · 后端架构文档

> 角色智能体对话系统的后端服务，基于 FastAPI + SQLAlchemy + SQLite 构建。

---

## 技术栈

| 组件 | 选型 | 版本 |
|------|------|------|
| Web 框架 | FastAPI | >=0.115.0 |
| ORM | SQLAlchemy | >=2.0.0 |
| 数据库 | SQLite（本地文件） | — |
| 异步 HTTP | httpx | >=0.27.0 |
| 配置管理 | pydantic-settings | >=2.0.0 |
| LLM | 通义千问（DashScope）| qwen-turbo |
| 服务器 | uvicorn | >=0.30.0 |

---

## 目录结构

```
├── app/
│   ├── main.py              # FastAPI 入口，lifespan 初始化角色数据
│   ├── core/                # 基础设施层
│   │   ├── config.py        # Pydantic Settings，读取 .env
│   │   └── database.py      # SQLAlchemy engine + SessionLocal + get_db
│   ├── models/              # ORM 模型层
│   │   ├── character.py     # 角色表
│   │   ├── session.py       # 会话表（含跨数据库 GUID 兼容处理）
│   │   └── message.py       # 消息表
│   ├── schemas/             # Pydantic 序列化/校验层
│   │   ├── character.py     # 角色输出 Schema
│   │   ├── session.py       # 会话创建/输出 Schema
│   │   ├── chat.py          # 聊天请求/消息/历史 Schema
│   │   └── common.py        # 统一响应包装 ResponseWrapper
│   ├── routers/             # API 路由层
│   │   ├── characters.py    # GET /characters, GET /characters/{id}
│   │   ├── sessions.py      # POST /sessions
│   │   └── chat.py          # POST /chat, GET /chat/history
│   ├── services/            # 业务逻辑/外部服务层
│   │   └── llm_client.py    # DashScope API 异步调用封装
│   └── prompts/             # 角色人格卡（YAML 格式）
│       ├── lin-wenqi.yaml
│       ├── su-xiuyun.yaml
│       ├── wang-huaiyuan.yaml
│       ├── zhao-bingfeng.yaml
│       └── zheng-chaosheng.yaml
├── requirements.txt         # Python 依赖
├── .env.example             # 环境变量模板
└── canal_mind.db            # SQLite 数据库（运行后自动生成）
```

---

## 核心数据流

```
用户发送消息
    ↓
POST /chat
    ↓
1. 校验 session 存在性
2. 读取角色 system_prompt + few_shots
3. 保存用户消息到 Message 表
4. 读取最近 20 条历史消息
5. 组装 messages 数组：
   [system] + [few_shots*最多3组] + [history...] + [user]
    ↓
调用 DashScope API (llm_client.py)
    ↓
保存 assistant 回复到 Message 表
    ↓
返回 ResponseWrapper 包装的消息对象
```

---

## 关键模块说明

### 1. 配置层 `app/core/config.py`

使用 `pydantic-settings` 管理环境变量，自动读取 `.env` 文件。

```python
DASHSCOPE_API_KEY=sk-xxxx     # LLM API 密钥
LLM_MODEL=qwen-turbo          # 模型名（默认）
REQUEST_TIMEOUT=30.0          # API 超时秒数
DATABASE_URL=sqlite:///./canal_mind.db  # 数据库连接串
```

**注意**：`get_settings()` 使用 `@lru_cache()` 缓存。若修改 `.env` 后未生效，需**重启服务**。

### 2. 数据库层 `app/core/database.py`

- `engine`：SQLite 本地文件，开发环境开启 SQL 语句回显（`echo=True`）
- `SessionLocal`：线程安全的 session 工厂
- `get_db()`：FastAPI Dependency，每次请求独立 session，请求结束后自动关闭

**生产迁移提示**：SQLite 的 `check_same_thread=False` 仅为开发方便。迁移到 PostgreSQL 时，替换 `DATABASE_URL` 即可，SQLAlchemy 2.0 兼容。

### 3. ORM 模型

#### Character（角色）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String(32) | 主键，如 `lin-wenqi` |
| name | String(64) | 角色名 |
| title | String(64) | 身份头衔 |
| era | String(32) | 年代 |
| system_prompt | Text | **核心**：LLM system 角色设定 |
| few_shots | JSON | 对话示例数组 |
| knowledge_nodes | JSON | 知识点节点（预留） |
| secrets | JSON | 角色秘密（预留） |
| status | String(16) | `active` / `disabled` |

#### Session（会话）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | GUID | UUID 主键（兼容 SQLite/PostgreSQL） |
| character_id | FK | 关联角色 |
| user_id | String(64) | 用户标识（当前固定 `anonymous`） |
| status | String(16) | `active` / `closed` |

#### Message（消息）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | GUID | UUID 主键 |
| session_id | FK | 关联会话 |
| role | String(16) | `user` / `assistant` / `system` |
| content | Text | 消息内容 |
| emotion_tag | String(32) | 情感标签（当前固定 `calm`，预留扩展） |
| extra | JSON | 扩展字段（原 `metadata`，因 SQLAlchemy 保留字冲突更名） |

### 4. 路由层

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/characters` | 列出所有活跃角色（卡片信息，不含 system_prompt） |
| GET | `/api/v1/characters/{id}` | 获取单个角色详情（含背景预览、秘密数量等） |
| POST | `/api/v1/sessions` | 创建新会话，返回 session_id |
| POST | `/api/v1/chat` | 发送消息，调 LLM，保存并返回回复 |
| GET | `/api/v1/chat/history` | 分页获取会话历史消息 |

所有成功响应统一包装为：

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

### 5. LLM 调用层 `app/services/llm_client.py`

封装 DashScope（通义千问）HTTP 异步调用：

- 请求地址：`https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation`
- 参数：`max_tokens=800`, `temperature=0.8`, `result_format=message`
- **降级策略**：超时或任何异常时，返回兜底文案 `（角色望着河水，一时陷入沉思……）`，不抛异常到上层路由

### 6. 角色初始化 `app/main.py`

服务启动时（`lifespan`），自动遍历 `app/prompts/` 目录下所有 `.yaml` 文件，解析后写入 `characters` 表。

**规则**：若表中已有角色数据，则跳过初始化。因此：
- 新增/修改角色 YAML 后，需**删除 `canal_mind.db`** 并重启服务
- 或手动在数据库中修改对应记录

---

## 开发启动

```bash
cd /Users/jdub/Code/2026-DYH-Agent-Backend/DYH-Agent--Backend

# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY

# 4. 启动服务
uvicorn app.main:app --reload

# 5. 验证
open http://localhost:8000/docs   # Swagger UI
```

---

## 后续扩展方向

| 功能 | 建议实现位置 | 说明 |
|------|-------------|------|
| 输出校验 | `services/output_validator.py` | 检测 LLM 回复是否违反角色禁忌（如使用现代词汇） |
| 剧情钩子 | `services/plot_hooks.py` | 关键词匹配触发剧情事件，写入 `message.plot_hook_triggered` |
| 记忆摘要 | `services/memory_summarizer.py` | 对话超过 N 轮后，对历史消息做 LLM 摘要，压缩上下文 |
| 情感识别 | `services/emotion_detector.py` | 分析用户输入情绪，动态调整角色回复风格 |
| 用户系统 | `models/user.py` + JWT | 替换 `anonymous`，支持注册登录 |
| 生产数据库 | 修改 `DATABASE_URL` | 直接切 PostgreSQL，零代码改动 |
| 多 LLM 支持 | `services/llm_client.py` | 抽象 LLMProvider 接口，支持切换 OpenAI/Claude 等 |

---

## 常见问题

**Q：修改了角色 Prompt，前端没有变化？**
A：删除 `canal_mind.db` 并重启后端。因为 `init_characters()` 只在表为空时初始化。

**Q：LLM 调用返回 401？**
A：检查 `.env` 中 `DASHSCOPE_API_KEY` 是否已填。修改后需重启服务（`get_settings()` 有缓存）。

**Q：前端跨域报错？**
A：后端 `main.py` 已配置 `CORSMiddleware(allow_origins=["*"])`。若仍报错，检查前端请求地址是否正确。
