# 企业文档RAG系统

这个项目实现了一个简单的企业文档检索增强生成（RAG）系统。

## 功能

- 上传文档并自动按段落与长度分片
- 列表展示已上传文档
- 基于 TF-IDF 简单检索文档片段
- 返回检索结果与参考回答文本

## 运行

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 启动服务
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. 访问文档
- 上传文档: `POST /docs/upload`
- 文档列表: `GET /docs/list`
- 查询检索: `POST /query/search`

## 示例

上传文档请求体:
```json
{
  "name": "企业制度",
  "content": "这是企业内部管理制度的内容..."
}
```

查询请求体:
```json
{
  "query": "请说明休假制度",
  "top_k": 3
}
```
