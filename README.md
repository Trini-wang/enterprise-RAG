# 企业文档 RAG 系统

基于 FastAPI 的文档检索示例，包含用户注册、登录、JWT 鉴权、用户管理和文件上传。

## 运行

```bash
pip install -r requirements.txt
$env:JWT_SECRET="请替换为随机长字符串"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问 `http://localhost:8000/docs` 查看并调试 OpenAPI 接口。生产环境必须设置
`JWT_SECRET`；可通过 `JWT_EXPIRE_MINUTES` 调整令牌有效期（默认 60 分钟）。

用户数据通过 SQLAlchemy ORM 存储在 SQLite，默认数据库是 `app/data/users.db`；上传文件
默认保存在 `app/uploads/`。可以通过 `DATABASE_URL`（例如
`sqlite:///D:/data/enterprise-rag.db`）或 `RAG_DATABASE_PATH` 修改数据库位置，并通过
`RAG_UPLOAD_DIR` 和 `MAX_UPLOAD_BYTES` 修改上传目录与上限。

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
