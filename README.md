# 企业文档 RAG 系统

基于 FastAPI 的文档检索示例，包含用户注册、登录、JWT 鉴权、用户管理和文件上传。

## 运行

```bash
pip install -r requirements.txt
$env:JWT_SECRET="请替换为随机长字符串"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问 `http://localhost:8000/` 使用 Web 管理界面。前端由 FastAPI 直接托管，
不需要额外启动 Node 服务；`http://localhost:8000/docs` 仍可查看和调试 OpenAPI 接口。
生产环境必须设置 `JWT_SECRET`；可通过 `JWT_EXPIRE_MINUTES` 调整令牌有效期（默认 60 分钟）。

Web 界面采用统一的浅蓝色响应式设计，覆盖注册登录、AI 多轮对话、模型选择、知识检索、
文档录入与查看、个人文件、Prompt/模型管理、用户管理和个人设置。管理入口仅对管理员显示。

用户数据通过 SQLAlchemy ORM 存储在 SQLite，默认数据库是 `app/data/users.db`；上传文件
默认保存在 `app/uploads/`。可以通过 `DATABASE_URL`（例如
`sqlite:///D:/data/enterprise-rag.db`）或 `RAG_DATABASE_PATH` 修改数据库位置，并通过
`RAG_UPLOAD_DIR` 和 `MAX_UPLOAD_BYTES` 修改上传目录与上限。

## AI 模型配置

Chat 使用 OpenAI-compatible `chat/completions` 协议。可以在启动前通过环境变量自动创建
第一个平台和模型：

```powershell
$env:AI_BASE_URL="https://your-provider.example/v1"
$env:AI_API_KEY="your-api-key"
$env:AI_MODEL="provider-model-id"
$env:AI_PROVIDER_NAME="OpenCode Zen"
$env:AI_MODEL_NAME="对用户展示的模型名"
```

也可以由管理员进入“模型管理”添加或编辑平台，填写 Base URL、API Key，并为同一平台
继续添加多个模型。API Key 使用 Fernet 加密后保存，接口只返回“是否已配置”，不会向浏览器
回传明文。生产环境建议设置稳定的加密主密钥：

```powershell
$env:MODEL_CONFIG_SECRET="请替换为随机长字符串并安全保管"
```

未设置时，应用会在 `app/data/model_config.key` 生成本机密钥。该文件丢失后将无法解密已保存的
模型 API Key。环境变量方式仍然兼容：如果页面没有保存密钥，系统会读取平台配置中的变量名。

AI 每轮回答都会先检索知识库：有效命中时将知识片段交给所选模型并返回引用，未命中时
继续使用模型的通用能力回答。首轮回答完成后，系统会使用当前模型生成简短的会话标题；
标题生成失败时自动使用首条问题摘要。独立的“知识检索”页面仍保留用于直接核对文档内容。

主要接口：

- `GET /ai/models`：获取当前用户可选的平台和模型
- `POST /chat/completions`：非流式 AI 对话
- `POST /chat/completions/stream`：SSE 流式 AI 对话
- `/conversations`：会话和消息历史
- `/prompts`：Prompt 列表及管理员版本管理
- `/admin/model-providers`：管理员配置平台和模型

## 认证与用户接口

- `POST /auth/register`：注册；空数据库中的首个用户自动成为管理员
- `POST /auth/login`：登录并获取 Bearer JWT
- `GET /auth/me`：获取当前用户
- `PATCH /users/me`：修改自己的姓名或密码
- `GET /users`：管理员查看用户列表
- `GET /users/{user_id}`：管理员或本人查看用户
- `PATCH /users/{user_id}`：管理员修改用户、角色或启用状态
- `DELETE /users/{user_id}`：管理员删除用户

需要登录的接口使用请求头：

```text
Authorization: Bearer <access_token>
```

## 文件接口

- `POST /files/upload`：上传文件，默认最大 10 MiB
- `GET /files`：列出当前用户上传的文件
- `GET /files/{filename}`：下载自己的文件
- `DELETE /files/{filename}`：删除自己的文件

每个用户的文件独立存储，不能访问其他用户的上传内容。

## 原有文档接口

- `POST /docs/upload`：提交文档文本并建立索引
- `GET /docs/list`：文档列表
- `GET /docs/{doc_id}`：文档详情
- `POST /query/search`：检索文档

## 测试

```bash
uv run python -m pytest -q
```
