# 问卷自动化 API 服务

将问卷自动化系统改造为REST API后端服务，提供问卷分析、批量提交和反向题检测功能。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

#### Windows
双击运行 `start_api.bat`

#### Linux/Mac
```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 访问API文档

服务启动后，访问以下地址：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **根路径**: http://localhost:8000/

## API接口说明

### 1. 问卷分析接口

**端点**: `POST /api/questionnaire/analyze`

**功能**: 根据问卷URL获取问卷结构，包括题目列表、题型统计、反向题识别等。

**请求示例**:
```json
{
  "url": "https://v.wjx.cn/vm/eLeS3jD.aspx"
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "问卷分析成功",
  "data": {
    "activity_id": "eLeS3jD",
    "url": "https://v.wjx.cn/vm/eLeS3jD.aspx",
    "total_questions": 14,
    "question_types": {
      "radio": 5,
      "rating": 1,
      "matrix": 9
    },
    "scale_questions": 10,
    "reverse_items": ["q7", "q8"]
  }
}
```

### 2. 问卷提交接口

**端点**: `POST /api/questionnaire/submit`

**功能**: 批量提交问卷，支持随机模式和高信度模式。

**请求示例**:
```json
{
  "url": "https://v.wjx.cn/vm/eLeS3jD.aspx",
  "count": 10,
  "mode": "high_reliability",
  "config": {
    "attitude": "positive",
    "add_variation": false,
    "variation_ratio": 0.05
  }
}
```

**参数说明**:
- `url`: 问卷URL（必填）
- `count`: 提交份数（必填，1-1000）
- `mode`: 提交模式
  - `random`: 随机模式
  - `high_reliability`: 高信度模式
- `config`: 模式配置（high_reliability模式必填）
  - `attitude`: 态度（`positive`积极 / `negative`消极）
  - `add_variation`: 是否穿插变化
  - `variation_ratio`: 变化比例（0.01-0.30）

**响应示例**:
```json
{
  "success": true,
  "message": "任务已创建，正在后台处理",
  "data": {
    "task_id": "task_20260802_153045_abc123",
    "status": "processing",
    "submitted": 0,
    "total": 10
  }
}
```

### 3. 任务状态查询接口

**端点**: `GET /api/questionnaire/submit/{task_id}`

**功能**: 查询提交任务的进度和结果。

**响应示例**:
```json
{
  "success": true,
  "message": "获取任务状态成功",
  "data": {
    "task_id": "task_20260802_153045_abc123",
    "status": "completed",
    "submitted": 8,
    "failed": 2,
    "total": 10,
    "progress": 100,
    "start_time": "2026-08-02T15:30:45",
    "end_time": "2026-08-02T15:35:20"
  }
}
```

### 4. 反向题检测接口

**端点**: `POST /api/detection/reverse-items`

**功能**: 识别量表题中的反向题（负向题）。

**请求示例**:
```json
{
  "questions": [
    {
      "id": "q1",
      "label": "我对公司的福利待遇很满意"
    },
    {
      "id": "q2",
      "label": "我经常感到工作压力过大，无法承受"
    }
  ]
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "反向题检测成功",
  "data": {
    "total_questions": 2,
    "reverse_count": 1,
    "results": [
      {
        "id": "q1",
        "label": "我对公司的福利待遇很满意",
        "is_reverse": false,
        "confidence": 0.0,
        "matched_keywords": []
      },
      {
        "id": "q2",
        "label": "我经常感到工作压力过大，无法承受",
        "is_reverse": true,
        "confidence": 0.82,
        "matched_keywords": ["过大", "无法", "承受"]
      }
    ]
  }
}
```

## 使用示例

### 使用curl测试

```bash
# 1. 分析问卷
curl -X POST http://localhost:8000/api/questionnaire/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://v.wjx.cn/vm/eLeS3jD.aspx"}'

# 2. 提交问卷（随机模式）
curl -X POST http://localhost:8000/api/questionnaire/submit \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://v.wjx.cn/vm/eLeS3jD.aspx",
    "count": 5,
    "mode": "random"
  }'

# 3. 查询任务状态
curl http://localhost:8000/api/questionnaire/submit/task_20260802_153045_abc123

# 4. 检测反向题
curl -X POST http://localhost:8000/api/detection/reverse-items \
  -H "Content-Type: application/json" \
  -d '{
    "questions": [
      {"id": "q1", "label": "我对工作很满意"},
      {"id": "q2", "label": "工作压力过大难以承受"}
    ]
  }'
```

## 技术架构

- **框架**: FastAPI
- **异步支持**: Asyncio + Playwright
- **数据验证**: Pydantic
- **自动文档**: Swagger UI / ReDoc
- **核心模块**:
  - `core/rule_based_analyzer.py` - 问卷分析
  - `core/dynamic_answer_generator.py` - 答案生成
  - `core/dynamic_submitter.py` - 表单提交
  - `core/reverse_item_detector.py` - 反向题检测

## 项目结构

```
问卷星/
├── api/                      # API服务层
│   ├── main.py              # FastAPI入口
│   ├── models.py            # 数据模型
│   ├── dependencies.py      # 依赖注入
│   └── routers/             # 路由
│       ├── questionnaire.py # 问卷分析路由
│       ├── submission.py    # 问卷提交路由
│       └── detection.py     # 反向题检测路由
├── core/                     # 核心功能模块
│   ├── schema.py
│   ├── rule_based_analyzer.py
│   ├── dynamic_answer_generator.py
│   ├── dynamic_submitter.py
│   └── reverse_item_detector.py
├── requirements.txt
├── start_api.bat            # Windows启动脚本
└── API_README.md            # API文档
```

## 注意事项

1. **任务存储**: 当前使用内存字典存储任务状态，重启服务后任务信息会丢失。生产环境建议使用Redis。

2. **并发控制**: 批量提交时每份问卷之间有3-5秒延迟，避免请求过快被限制。

3. **浏览器资源**: 每次提交会启动浏览器实例，大量并发提交时注意系统资源。

4. **验证码**: 目前支持阿里云智能验证，其他验证码类型可能需要人工介入。

## 下一步扩展

- 使用Redis持久化任务状态
- 添加WebSocket支持实时推送进度
- 实现API密钥认证和访问控制
- 添加请求频率限制
- 集成日志系统

