# 问卷系统前端架构设计方案

## 目录
1. [需求概述](#需求概述)
2. [API数据结构规范](#api数据结构规范)
3. [技术栈选择](#技术栈选择)
4. [项目结构](#项目结构)
5. [核心功能设计](#核心功能设计)
6. [实施步骤](#实施步骤)

---

## API数据结构规范

### QuestionnaireSchema 结构定义

后端返回的问卷结构遵循以下格式规范：

#### 顶层响应结构
```typescript
interface ApiResponse<T> {
  success: boolean          // 请求是否成功
  message: string           // 响应消息
  data: T                   // 实际数据
}
```

#### 问卷分析响应（AnalyzeResponse）
```typescript
interface AnalyzeResponse {
  activity_id: string                    // 问卷活动ID，如 "eLeS3jD"
  url: string                            // 问卷完整URL
  total_questions: number                // 题目总数
  question_types: Record<string, number> // 题型统计，如 {"radio": 5, "matrix": 9}
  questions: Question[]                  // 题目列表
  scale_questions: number                // 量表题数量（rating/nps/matrix）
  reverse_items: string[]                // 反向题ID列表，如 ["q7", "q8"]
}
```

#### 题目结构（Question）
```typescript
interface Question {
  id: string                   // 题目ID，如 "q1", "q7_0"（矩阵题行）
  type: QuestionType           // 题型枚举
  label: string                // 题目文本
  options: OptionItem[]        // 选项列表（包含值和真实标签）
  required: boolean            // 是否必填
  is_scale: boolean            // 是否为量表题（rating/nps/matrix）
  is_reverse: boolean          // 是否为反向题
  reverse_confidence: number | null  // 反向题识别置信度（0-1）
}

// 选项项目
interface OptionItem {
  value: string | number       // 选项值/序号
  label: string | null         // 选项真实文本标签
}

// 题型枚举
type QuestionType =
  | "radio"              // 单选题
  | "checkbox"           // 多选题
  | "select"             // 下拉选择
  | "text"               // 单行文本
  | "textarea"           // 多行文本
  | "matrix"             // 矩阵评分
  | "rating"             // 评分题（1-5星）
  | "nps"                // NPS推荐度（0-10分）
  | "sort"               // 排序题
  | "weight_allocation"  // 权重分配（总和100%）
  | "unknown"            // 未识别题型
```

### 各题型 options 格式规范

#### 1. 单选题（radio）
```typescript
{
  id: "q1",
  type: "radio",
  label: "*1.您的性别",
  options: [
    { value: 1, label: "男" },
    { value: 2, label: "女" }
  ],
  required: true,
  is_scale: false,
  is_reverse: false,
  reverse_confidence: null
}
```

#### 2. 多选题（checkbox）
```typescript
{
  id: "q3",
  type: "checkbox",
  label: "*3.您常购买的商品类别",
  options: [
    { value: 1, label: "食品" },
    { value: 2, label: "服装" },
    { value: 3, label: "电子产品" },
    { value: 4, label: "家居" },
    { value: 5, label: "其他" }
  ],
  required: true,
  is_scale: false,
  is_reverse: false,
  reverse_confidence: null
}
```

#### 3. 下拉选择（select）
```typescript
{
  id: "q2",
  type: "select",
  label: "*2.您的年龄段",
  options: [
    { value: 1, label: "18-25岁" },
    { value: 2, label: "26-35岁" },
    { value: 3, label: "36-45岁" },
    { value: 4, label: "46-55岁" },
    { value: 5, label: "55岁以上" }
  ],
  required: true,
  is_scale: false,
  is_reverse: false,
  reverse_confidence: null
}
```

#### 4. 单行文本（text）
```typescript
{
  id: "q5",
  type: "text",
  label: "5.您所在的城市",
  options: [],
  required: false,
  is_scale: false,
  is_reverse: false,
  reverse_confidence: null
}
```

#### 5. 多行文本（textarea）
```typescript
{
  id: "q14",
  type: "textarea",
  label: "14.您的建议和意见",
  options: [],
  required: false,
  is_scale: false,
  is_reverse: false,
  reverse_confidence: null
}
```

#### 6. 评分题（rating）
```typescript
{
  id: "q7",
  type: "rating",
  label: "*7.员工餐厅的菜品价格偏高，我觉得难以接受",
  options: [
    { value: 1, label: "非常不同意" },
    { value: 2, label: "不同意" },
    { value: 3, label: "一般" },
    { value: 4, label: "同意" },
    { value: 5, label: "非常同意" }
  ],
  required: true,
  is_scale: true,
  is_reverse: true,
  reverse_confidence: 0.85
}
```

#### 7. 矩阵评分题（matrix）
```typescript
{
  id: "q10_1",
  type: "matrix",
  label: "*10.请您对员工餐厅的以下方面进行评价 - 菜品口味",
  options: [
    { value: "1", label: "非常不同意" },
    { value: "2", label: "不同意" },
    { value: "3", label: "一般" },
    { value: "4", label: "同意" },
    { value: "5", label: "非常同意" }
  ],
  required: true,
  is_scale: true,
  is_reverse: false,
  reverse_confidence: null
}
```

#### 8. NPS推荐度（nps）
```typescript
{
  id: "q12",
  type: "nps",
  label: "*12.您向朋友推荐我们公司的可能性有多大？",
  options: [
    { value: 0, label: "0 - 完全不可能" },
    { value: 1, label: "1" },
    { value: 2, label: "2" },
    { value: 3, label: "3" },
    // ... 4-9
    { value: 10, label: "10 - 非常可能" }
  ],
  required: true,
  is_scale: true,
  is_reverse: false,
  reverse_confidence: null
}
```

#### 9. 排序题（sort）
```typescript
{
  id: "q8",
  type: "sort",
  label: "*8.请对以下因素按重要性排序",
  options: [
    { value: 1, label: "价格" },
    { value: 2, label: "质量" },
    { value: 3, label: "服务" },
    { value: 4, label: "品牌" },
    { value: 5, label: "位置" },
    { value: 6, label: "口碑" }
  ],
  required: true,
  is_scale: false,
  is_reverse: false,
  reverse_confidence: null
}
```

#### 10. 权重分配题（weight_allocation）
```typescript
{
  id: "q13",
  type: "weight_allocation",
  label: "*13.请分配您认为重要的因素权重（总和100%）",
  options: [
    { value: 1, label: "菜品口味", rowid: 1 },
    { value: 2, label: "价格", rowid: 2 },
    { value: 3, label: "卫生环境", rowid: 3 },
    { value: 4, label: "服务态度", rowid: 4 },
    { value: 5, label: "就餐环境", rowid: 5 },
    { value: 6, label: "菜品种类", rowid: 6 }
  ],
  required: true,
  is_scale: false,
  is_reverse: false,
  reverse_confidence: null
}
```

### 完整示例：问卷分析响应

```json
{
  "success": true,
  "message": "Questionnaire analyzed successfully",
  "data": {
    "activity_id": "eLeS3jD",
    "url": "https://v.wjx.cn/vm/eLeS3jD.aspx",
    "total_questions": 14,
    "question_types": {
      "radio": 2,
      "checkbox": 1,
      "select": 1,
      "text": 1,
      "rating": 1,
      "matrix": 3,
      "nps": 1,
      "sort": 1,
      "weight_allocation": 1,
      "textarea": 1
    },
    "questions": [
      {
        "id": "q1",
        "type": "radio",
        "label": "*1.您的性别",
        "options": [1, 2],
        "required": true,
        "is_reverse": false,
        "reverse_confidence": null
      },
      {
        "id": "q7",
        "type": "rating",
        "label": "*7.员工餐厅的菜品价格偏高，我觉得难以接受",
        "options": [1, 2, 3, 4, 5],
        "required": true,
        "is_reverse": true,
        "reverse_confidence": 0.85
      },
      {
        "id": "q10_1",
        "type": "matrix",
        "label": "*10.请您对员工餐厅的以下方面进行评价 - 菜品口味",
        "options": ["1", "2", "3", "4", "5"],
        "required": true,
        "is_reverse": false,
        "reverse_confidence": null
      },
      {
        "id": "q13",
        "type": "weight_allocation",
        "label": "*13.请分配各因素权重（总和100%）",
        "options": [
          { "rowid": 1, "title": "菜品口味" },
          { "rowid": 2, "title": "价格" },
          { "rowid": 3, "title": "卫生环境" }
        ],
        "required": true,
        "is_reverse": false,
        "reverse_confidence": null
      }
    ],
    "scale_questions": 11,
    "reverse_items": ["q7", "q8_2", "q9_1"]
  }
}
```

---

## 需求概述

基于已有的FastAPI后端服务，设计并实现前端Web应用，包含两个核心模块：

### 模块1：用户登录系统
- 账号密码登录
- 登录状态管理
- 权限验证

### 模块2：问卷任务管理系统
- **任务列表**：查看所有已创建的问卷任务
- **删除任务**：删除指定的问卷任务
- **创建任务**：
  1. 输入问卷URL
  2. 系统自动解析问卷结构
  3. 展示问卷内容（题目、题型、选项等）
  4. 配置提交参数（模式、数量、态度等）
  5. 提交任务并监控进度

---

## 技术栈选择

### 前端框架：Vue 3 + TypeScript
**理由**：
- 渐进式框架，易于上手和集成
- Composition API提供更好的类型推断
- 丰富的生态系统和组件库
- 良好的开发体验（Vite构建工具）

### UI组件库：Element Plus
**理由**：
- Vue 3官方推荐的企业级UI库
- 组件完善，风格统一
- 中文文档完善
- 适合后台管理系统

### 状态管理：Pinia
**理由**：
- Vue 3官方推荐的状态管理工具
- TypeScript支持优秀
- API简洁，易于理解
- 自动代码分割

### HTTP客户端：Axios
**理由**：
- 功能强大，支持拦截器
- 自动转换JSON数据
- 请求/响应拦截（统一处理token、错误）

### 路由管理：Vue Router 4
**理由**：
- Vue官方路由库
- 支持路由守卫（权限验证）
- 支持懒加载

### 构建工具：Vite
**理由**：
- 极速的开发服务器启动
- 热模块替换（HMR）
- 优化的生产构建

---

## 项目结构

```
frontend/
├── public/                          # 静态资源
│   └── favicon.ico
├── src/
│   ├── api/                         # API接口层
│   │   ├── index.ts                 # API统一导出
│   │   ├── request.ts               # Axios封装配置
│   │   ├── auth.ts                  # 登录/认证接口
│   │   ├── questionnaire.ts         # 问卷分析接口
│   │   ├── task.ts                  # 任务管理接口
│   │   └── types.ts                 # API类型定义
│   ├── assets/                      # 静态资源
│   │   ├── logo.png
│   │   └── styles/
│   │       ├── global.css           # 全局样式
│   │       └── variables.css        # CSS变量
│   ├── components/                  # 通用组件
│   │   ├── Layout/
│   │   │   ├── AppHeader.vue        # 顶部导航栏
│   │   │   ├── AppSidebar.vue       # 侧边栏
│   │   │   └── AppLayout.vue        # 布局容器
│   │   ├── Task/
│   │   │   ├── TaskCard.vue         # 任务卡片
│   │   │   ├── TaskList.vue         # 任务列表
│   │   │   └── TaskProgress.vue     # 任务进度条
│   │   └── Questionnaire/
│   │       ├── QuestionItem.vue     # 单个题目展示
│   │       ├── QuestionList.vue     # 题目列表
│   │       └── QuestionnairePreview.vue  # 问卷预览
│   ├── router/                      # 路由配置
│   │   └── index.ts
│   ├── stores/                      # Pinia状态管理
│   │   ├── user.ts                  # 用户状态（登录信息）
│   │   ├── task.ts                  # 任务状态（任务列表）
│   │   └── questionnaire.ts         # 问卷状态（当前问卷）
│   ├── types/                       # TypeScript类型定义
│   │   ├── user.ts
│   │   ├── task.ts
│   │   └── questionnaire.ts
│   ├── utils/                       # 工具函数
│   │   ├── storage.ts               # 本地存储封装
│   │   ├── validator.ts             # 表单验证
│   │   └── format.ts                # 格式化工具
│   ├── views/                       # 页面组件
│   │   ├── Login/
│   │   │   └── index.vue            # 登录页
│   │   ├── Dashboard/
│   │   │   └── index.vue            # 任务仪表板
│   │   ├── Task/
│   │   │   ├── List.vue             # 任务列表页
│   │   │   ├── Create.vue           # 创建任务页
│   │   │   └── Detail.vue           # 任务详情页
│   │   └── NotFound/
│   │       └── index.vue            # 404页面
│   ├── App.vue                      # 根组件
│   └── main.ts                      # 入口文件
├── .env.development                 # 开发环境变量
├── .env.production                  # 生产环境变量
├── .gitignore
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```

---

## 核心功能设计

### 1. 登录模块设计

#### 1.1 登录页面（Login/index.vue）

**UI布局**：
```
┌─────────────────────────────────────────────┐
│                                             │
│              问卷自动化系统                  │
│                                             │
│         ┌─────────────────────┐            │
│         │   用户名              │            │
│         │  [___________]      │            │
│         │                     │            │
│         │   密码                │            │
│         │  [___________]      │            │
│         │                     │            │
│         │  [ 记住密码 ]        │            │
│         │                     │            │
│         │  [   登录   ]       │            │
│         └─────────────────────┘            │
│                                             │
└─────────────────────────────────────────────┘
```

**功能要点**：
- 表单验证（用户名、密码非空）
- 记住密码（localStorage保存）
- 登录loading状态
- 错误提示
- 登录成功后跳转到任务列表页

**API调用**：
```typescript
// POST /api/auth/login
{
  "username": "admin",
  "password": "password123"
}

// 响应
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": 1,
      "username": "admin",
      "email": "admin@example.com"
    }
  }
}
```

#### 1.2 状态管理（stores/user.ts）

```typescript
import { defineStore } from 'pinia'
import { login, logout, getUserInfo } from '@/api/auth'
import type { User, LoginRequest } from '@/types/user'
import { getToken, setToken, removeToken } from '@/utils/storage'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: getToken() || '',
    user: null as User | null,
    isLoggedIn: false
  }),

  getters: {
    username: (state) => state.user?.username || '',
    userId: (state) => state.user?.id || null
  },

  actions: {
    async login(loginData: LoginRequest) {
      try {
        const response = await login(loginData)
        this.token = response.data.token
        this.user = response.data.user
        this.isLoggedIn = true

        // 保存token到localStorage
        setToken(this.token)

        return true
      } catch (error) {
        console.error('Login failed:', error)
        return false
      }
    },

    async logout() {
      try {
        await logout()
      } finally {
        this.token = ''
        this.user = null
        this.isLoggedIn = false
        removeToken()
      }
    },

    async fetchUserInfo() {
      if (!this.token) return false

      try {
        const response = await getUserInfo()
        this.user = response.data
        this.isLoggedIn = true
        return true
      } catch (error) {
        console.error('Fetch user info failed:', error)
        // Token可能已过期，清除登录状态
        await this.logout()
        return false
      }
    }
  }
})
```

#### 1.3 路由守卫（router/index.ts）

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login/index.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      redirect: '/tasks'
    },
    {
      path: '/tasks',
      name: 'TaskList',
      component: () => import('@/views/Task/List.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/tasks/create',
      name: 'TaskCreate',
      component: () => import('@/views/Task/Create.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/tasks/:id',
      name: 'TaskDetail',
      component: () => import('@/views/Task/Detail.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/NotFound/index.vue')
    }
  ]
})

// 全局前置守卫
router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()

  // 如果路由需要认证
  if (to.meta.requiresAuth) {
    if (!userStore.token) {
      // 未登录，重定向到登录页
      next({ name: 'Login', query: { redirect: to.fullPath } })
      return
    }

    // 有token但没有用户信息，尝试获取
    if (!userStore.user) {
      const success = await userStore.fetchUserInfo()
      if (!success) {
        next({ name: 'Login', query: { redirect: to.fullPath } })
        return
      }
    }
  }

  // 已登录用户访问登录页，重定向到首页
  if (to.name === 'Login' && userStore.token) {
    next({ name: 'TaskList' })
    return
  }

  next()
})

export default router
```

---

### 2. 问卷任务管理模块设计

#### 2.1 任务列表页（Task/List.vue）

**UI布局**：
```
┌─────────────────────────────────────────────────────────────┐
│  问卷自动化系统                       admin ▼  [退出登录]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  任务管理                        [+ 创建新任务]              │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 🔍 搜索任务  [_____________]          筛选: [全部▼]    │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 任务 #1                              [查看] [删除]    │ │
│  │ 问卷URL: https://v.wjx.cn/vm/eLeS3jD.aspx            │ │
│  │ 创建时间: 2026-08-02 15:30:45                         │ │
│  │ 状态: ✅ 已完成  进度: 10/10  成功率: 80%             │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 任务 #2                              [查看] [删除]    │ │
│  │ 问卷URL: https://v.wjx.cn/vm/heiw7uL.aspx            │ │
│  │ 创建时间: 2026-08-02 14:20:15                         │ │
│  │ 状态: ⏳ 进行中  进度: 5/20  成功率: 100%             │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 任务 #3                              [查看] [删除]    │ │
│  │ 问卷URL: https://v.wjx.cn/vm/rqKTYry.aspx            │ │
│  │ 创建时间: 2026-08-02 10:15:30                         │ │
│  │ 状态: ❌ 失败  进度: 0/50  错误: 问卷不存在            │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│                      [1] 2 3 4 5 ... 10                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**功能要点**：
- 任务列表展示（卡片或表格形式）
- 搜索和筛选（按状态、日期）
- 分页加载
- 实时状态更新（轮询或WebSocket）
- 删除确认对话框
- 跳转到任务详情页

**数据类型**：
```typescript
// types/task.ts
export interface Task {
  id: string
  url: string
  questionnaire_title?: string
  create_time: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  config: {
    mode: 'random' | 'high_reliability'
    count: number
    attitude?: 'positive' | 'negative'
    add_variation?: boolean
  }
  progress: {
    submitted: number
    failed: number
    total: number
    percentage: number
  }
  results?: SubmissionResult[]
  error?: string
}

export interface SubmissionResult {
  index: number
  status: 'success' | 'failed'
  error?: string
  timestamp: string
}
```

#### 2.2 创建任务页（Task/Create.vue）

**UI布局（分步骤）**：

**步骤1：输入问卷URL**
```
┌─────────────────────────────────────────────────────────────┐
│  创建新任务                                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  步骤 1/3：输入问卷URL                                       │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
│                                                             │
│  问卷URL *                                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ https://v.wjx.cn/vm/eLeS3jD.aspx                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  提示: 请输入问卷星(wjx.cn)的问卷URL                        │
│                                                             │
│                          [取消]  [下一步：解析问卷]         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**步骤2：展示问卷结构**
```
┌─────────────────────────────────────────────────────────────┐
│  创建新任务                                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  步骤 2/3：预览问卷结构                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
│                                                             │
│  问卷标题: 员工餐厅就餐满意度调查                            │
│  活动ID: eLeS3jD                                            │
│  题目数量: 14题                                              │
│  量表题: 11题  反向题: 3题                                   │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 题目列表                                   [展开全部]   │ │
│  ├───────────────────────────────────────────────────────┤ │
│  │ 1. 您的性别 (单选题)                                  │ │
│  │    ○ 男  ○ 女                                        │ │
│  │                                                       │ │
│  │ 2. 您的年龄 (单选题)                                  │ │
│  │    ○ 18-25岁  ○ 26-35岁  ○ 36-45岁  ○ 46岁以上      │ │
│  │                                                       │ │
│  │ 7. 员工餐厅的菜品价格偏高... (评分题) 🔴反向题        │ │
│  │    1分 ━ 2分 ━ 3分 ━ 4分 ━ 5分                        │ │
│  │                                                       │ │
│  │ ... (更多题目)                                        │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│                          [上一步]  [下一步：配置参数]       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**步骤3：配置提交参数**
```
┌─────────────────────────────────────────────────────────────┐
│  创建新任务                                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  步骤 3/3：配置提交参数                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
│                                                             │
│  提交模式 *                                                  │
│  ○ 随机模式  ● 高信度模式                                   │
│                                                             │
│  回答态度 (仅高信度模式)                                     │
│  ● 积极态度 (正向题高分，反向题低分)                         │
│  ○ 消极态度 (正向题低分，反向题高分)                         │
│                                                             │
│  穿插变化                                                    │
│  ☑ 启用穿插变化 (约5%题目会选择中立或相反趋势)              │
│                                                             │
│  提交数量 *                                                  │
│  ┌─────────┐                                               │
│  │   10    │  (建议: 10-100份)                              │
│  └─────────┘                                               │
│                                                             │
│  预估耗时: 约2-5分钟                                         │
│                                                             │
│                          [上一步]  [创建并开始任务]         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**功能要点**：
- 三步创建流程（URL输入 → 问卷预览 → 参数配置）
- URL格式验证
- 调用`/api/questionnaire/analyze`解析问卷
- 展示问卷结构（题目列表、题型统计、反向题标识）
- 配置提交模式、态度、数量
- 创建后跳转到任务详情页

**API调用流程**：
```typescript
// 步骤1 → 步骤2: 解析问卷
POST /api/questionnaire/analyze
Request: { "url": "https://v.wjx.cn/vm/eLeS3jD.aspx" }
Response: { "success": true, "data": { "activity_id": "...", "questions": [...] } }

// 步骤3 → 创建任务: 提交问卷任务
POST /api/questionnaire/submit
Request: {
  "url": "https://v.wjx.cn/vm/eLeS3jD.aspx",
  "count": 10,
  "mode": "high_reliability",
  "config": {
    "attitude": "positive",
    "add_variation": true
  }
}
Response: { "success": true, "data": { "task_id": "task_xxx", "status": "processing" } }
```

#### 2.3 任务详情页（Task/Detail.vue）

**UI布局**：
```
┌─────────────────────────────────────────────────────────────┐
│  任务详情 #task_20260802_153045_abc123              [返回]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  基本信息                                                    │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 任务ID: task_20260802_153045_abc123                   │ │
│  │ 问卷URL: https://v.wjx.cn/vm/eLeS3jD.aspx            │ │
│  │ 创建时间: 2026-08-02 15:30:45                         │ │
│  │ 提交模式: 高信度模式 (积极态度)                       │ │
│  │ 穿插变化: 是                                          │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  执行进度                                                    │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 状态: ⏳ 进行中                                        │ │
│  │                                                       │ │
│  │ ████████████████████░░░░░░░░░░  65%                  │ │
│  │                                                       │ │
│  │ 已提交: 65/100                                        │ │
│  │ 成功: 62  失败: 3                                     │ │
│  │ 成功率: 95.4%                                         │ │
│  │                                                       │ │
│  │ 开始时间: 2026-08-02 15:30:50                         │ │
│  │ 预计剩余: 约2分钟                                     │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  提交记录                                                    │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ #1  ✅ 成功  15:31:02                                 │ │
│  │ #2  ✅ 成功  15:31:08                                 │ │
│  │ #3  ❌ 失败  15:31:14  错误: 验证码失败                │ │
│  │ #4  ✅ 成功  15:31:20                                 │ │
│  │ ... (更多记录)                                        │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│                          [暂停任务]  [导出结果]            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**功能要点**：
- 显示任务基本信息
- 实时进度展示（进度条、百分比）
- 提交记录列表（成功/失败状态、时间戳）
- 定时轮询更新状态（每3秒）
- 任务完成后显示统计信息
- 导出结果功能

**API调用**：
```typescript
// 轮询任务状态
GET /api/questionnaire/submit/{task_id}
Response: {
  "success": true,
  "data": {
    "task_id": "task_xxx",
    "status": "processing",
    "submitted": 65,
    "failed": 3,
    "total": 100,
    "progress": 65,
    "results": [...]
  }
}
```

---

## API接口封装设计

### api/request.ts - Axios配置

```typescript
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import router from '@/router'

// 创建axios实例
const service: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
service.interceptors.request.use(
  (config: AxiosRequestConfig) => {
    const userStore = useUserStore()

    // 添加token到请求头
    if (userStore.token) {
      config.headers = config.headers || {}
      config.headers['Authorization'] = `Bearer ${userStore.token}`
    }

    return config
  },
  (error) => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => {
    const res = response.data

    // 后端返回格式: { success: true/false, data: {...}, message: '...' }
    if (res.success) {
      return res
    } else {
      // 业务错误
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
  },
  (error) => {
    console.error('Response error:', error)

    // HTTP错误处理
    if (error.response) {
      const { status, data } = error.response

      switch (status) {
        case 401:
          // 未授权，清除登录状态并跳转到登录页
          ElMessage.error('登录已过期，请重新登录')
          const userStore = useUserStore()
          userStore.logout()
          router.push({ name: 'Login' })
          break
        case 403:
          ElMessage.error('没有权限访问')
          break
        case 404:
          ElMessage.error('请求的资源不存在')
          break
        case 500:
          ElMessage.error('服务器错误')
          break
        default:
          ElMessage.error(data.message || '请求失败')
      }
    } else if (error.request) {
      // 请求已发送但没有收到响应
      ElMessage.error('网络错误，请检查网络连接')
    } else {
      // 其他错误
      ElMessage.error(error.message || '未知错误')
    }

    return Promise.reject(error)
  }
)

export default service
```

### api/auth.ts - 认证接口

```typescript
import request from './request'
import type { LoginRequest, LoginResponse, User } from '@/types/user'

// 登录
export function login(data: LoginRequest) {
  return request<LoginResponse>({
    url: '/auth/login',
    method: 'post',
    data
  })
}

// 登出
export function logout() {
  return request({
    url: '/auth/logout',
    method: 'post'
  })
}

// 获取用户信息
export function getUserInfo() {
  return request<{ data: User }>({
    url: '/auth/user',
    method: 'get'
  })
}
```

### api/questionnaire.ts - 问卷接口

```typescript
import request from './request'
import type { QuestionnaireSchema } from '@/types/questionnaire'

// 分析问卷
export function analyzeQuestionnaire(url: string) {
  return request<{ data: QuestionnaireSchema }>({
    url: '/questionnaire/analyze',
    method: 'post',
    data: { url }
  })
}

// 反向题检测
export function detectReverseItems(questions: Array<{ id: string; label: string }>) {
  return request({
    url: '/detection/reverse-items',
    method: 'post',
    data: { questions }
  })
}
```

### api/task.ts - 任务接口

```typescript
import request from './request'
import type { Task, CreateTaskRequest, TaskListQuery } from '@/types/task'

// 获取任务列表
export function getTaskList(params: TaskListQuery) {
  return request<{ data: { tasks: Task[]; total: number } }>({
    url: '/questionnaire/tasks',
    method: 'get',
    params
  })
}

// 获取任务详情
export function getTaskDetail(taskId: string) {
  return request<{ data: Task }>({
    url: `/questionnaire/submit/${taskId}`,
    method: 'get'
  })
}

// 创建任务
export function createTask(data: CreateTaskRequest) {
  return request<{ data: { task_id: string } }>({
    url: '/questionnaire/submit',
    method: 'post',
    data
  })
}

// 删除任务
export function deleteTask(taskId: string) {
  return request({
    url: `/questionnaire/tasks/${taskId}`,
    method: 'delete'
  })
}

// 暂停任务
export function pauseTask(taskId: string) {
  return request({
    url: `/questionnaire/tasks/${taskId}/pause`,
    method: 'post'
  })
}

// 导出任务结果
export function exportTaskResult(taskId: string) {
  return request({
    url: `/questionnaire/tasks/${taskId}/export`,
    method: 'get',
    responseType: 'blob'
  })
}
```

---

## 核心组件设计

### components/Task/TaskCard.vue

```vue
<template>
  <el-card class="task-card" :class="statusClass" shadow="hover">
    <div class="task-header">
      <div class="task-id">任务 #{{ task.id }}</div>
      <div class="task-actions">
        <el-button size="small" @click="handleView">查看</el-button>
        <el-button size="small" type="danger" @click="handleDelete">删除</el-button>
      </div>
    </div>

    <div class="task-body">
      <div class="task-url">
        <el-icon><Link /></el-icon>
        <span>{{ task.url }}</span>
      </div>

      <div class="task-info">
        <div class="info-item">
          <span class="label">创建时间:</span>
          <span class="value">{{ formatTime(task.create_time) }}</span>
        </div>
        <div class="info-item">
          <span class="label">状态:</span>
          <el-tag :type="statusTagType" size="small">
            {{ statusText }}
          </el-tag>
        </div>
      </div>

      <div class="task-progress" v-if="task.status !== 'failed'">
        <el-progress
          :percentage="task.progress.percentage"
          :status="progressStatus"
          :stroke-width="16"
        />
        <div class="progress-text">
          {{ task.progress.submitted }}/{{ task.progress.total }}
          (成功率: {{ successRate }}%)
        </div>
      </div>

      <div class="task-error" v-if="task.error">
        <el-alert :title="task.error" type="error" :closable="false" />
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { Task } from '@/types/task'
import { formatTime } from '@/utils/format'

interface Props {
  task: Task
}

const props = defineProps<Props>()
const emit = defineEmits<{
  delete: [taskId: string]
}>()

const router = useRouter()

// 状态相关计算属性
const statusClass = computed(() => `status-${props.task.status}`)

const statusText = computed(() => {
  const statusMap = {
    pending: '待处理',
    processing: '进行中',
    completed: '已完成',
    failed: '失败'
  }
  return statusMap[props.task.status] || '未知'
})

const statusTagType = computed(() => {
  const typeMap = {
    pending: 'info',
    processing: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return typeMap[props.task.status] as any
})

const progressStatus = computed(() => {
  if (props.task.status === 'completed') return 'success'
  if (props.task.status === 'failed') return 'exception'
  return undefined
})

const successRate = computed(() => {
  const { submitted, failed } = props.task.progress
  if (submitted === 0) return 0
  return ((submitted - failed) / submitted * 100).toFixed(1)
})

// 事件处理
function handleView() {
  router.push({ name: 'TaskDetail', params: { id: props.task.id } })
}

function handleDelete() {
  emit('delete', props.task.id)
}
</script>

<style scoped lang="scss">
.task-card {
  margin-bottom: 16px;

  .task-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    .task-id {
      font-size: 16px;
      font-weight: 600;
    }
  }

  .task-body {
    .task-url {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
      color: #606266;

      span {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .task-info {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-bottom: 12px;

      .info-item {
        .label {
          color: #909399;
          margin-right: 4px;
        }
      }
    }

    .task-progress {
      .progress-text {
        margin-top: 8px;
        text-align: center;
        color: #606266;
        font-size: 13px;
      }
    }

    .task-error {
      margin-top: 12px;
    }
  }
}

.status-completed {
  border-color: #67c23a;
}

.status-failed {
  border-color: #f56c6c;
}

.status-processing {
  border-color: #e6a23c;
}
</style>
```

---

## 状态管理设计

### stores/task.ts

```typescript
import { defineStore } from 'pinia'
import { getTaskList, getTaskDetail, createTask, deleteTask } from '@/api/task'
import type { Task, TaskListQuery, CreateTaskRequest } from '@/types/task'

export const useTaskStore = defineStore('task', {
  state: () => ({
    tasks: [] as Task[],
    currentTask: null as Task | null,
    total: 0,
    loading: false,
    query: {
      page: 1,
      pageSize: 20,
      status: undefined,
      keyword: ''
    } as TaskListQuery
  }),

  getters: {
    taskById: (state) => (id: string) => {
      return state.tasks.find(task => task.id === id)
    },

    processingTasks: (state) => {
      return state.tasks.filter(task => task.status === 'processing')
    }
  },

  actions: {
    async fetchTasks(query?: Partial<TaskListQuery>) {
      this.loading = true

      try {
        if (query) {
          this.query = { ...this.query, ...query }
        }

        const response = await getTaskList(this.query)
        this.tasks = response.data.tasks
        this.total = response.data.total

        return true
      } catch (error) {
        console.error('Fetch tasks failed:', error)
        return false
      } finally {
        this.loading = false
      }
    },

    async fetchTaskDetail(taskId: string) {
      try {
        const response = await getTaskDetail(taskId)
        this.currentTask = response.data

        // 同时更新任务列表中的对应项
        const index = this.tasks.findIndex(t => t.id === taskId)
        if (index !== -1) {
          this.tasks[index] = response.data
        }

        return response.data
      } catch (error) {
        console.error('Fetch task detail failed:', error)
        return null
      }
    },

    async createTask(data: CreateTaskRequest) {
      try {
        const response = await createTask(data)
        const taskId = response.data.task_id

        // 刷新任务列表
        await this.fetchTasks()

        return taskId
      } catch (error) {
        console.error('Create task failed:', error)
        return null
      }
    },

    async deleteTask(taskId: string) {
      try {
        await deleteTask(taskId)

        // 从列表中移除
        this.tasks = this.tasks.filter(task => task.id !== taskId)
        this.total -= 1

        return true
      } catch (error) {
        console.error('Delete task failed:', error)
        return false
      }
    },

    clearCurrentTask() {
      this.currentTask = null
    }
  }
})
```

---

## 实施步骤

### 步骤1：初始化项目（30分钟）

```bash
# 创建Vite + Vue3 + TypeScript项目
npm create vite@latest frontend -- --template vue-ts
cd frontend

# 安装依赖
npm install vue-router@4 pinia axios element-plus
npm install @element-plus/icons-vue
npm install -D sass

# 配置Element Plus自动导入（可选）
npm install -D unplugin-vue-components unplugin-auto-import
```

**配置文件**：
- `vite.config.ts` - Vite配置
- `tsconfig.json` - TypeScript配置
- `.env.development` - 开发环境变量
- `.env.production` - 生产环境变量

### 步骤2：创建基础结构（1小时）

1. 创建目录结构（按上述项目结构）
2. 配置路由（`router/index.ts`）
3. 配置Pinia（`main.ts`）
4. 创建Axios封装（`api/request.ts`）
5. 创建工具函数（`utils/`）

### 步骤3：实现登录模块（2小时）

1. 创建登录页面（`views/Login/index.vue`）
2. 实现用户Store（`stores/user.ts`）
3. 实现认证API（`api/auth.ts`）
4. 配置路由守卫
5. 测试登录流程

### 步骤4：实现任务列表页（3小时）

1. 创建任务列表页（`views/Task/List.vue`）
2. 创建任务卡片组件（`components/Task/TaskCard.vue`）
3. 实现任务Store（`stores/task.ts`）
4. 实现任务API（`api/task.ts`）
5. 添加搜索、筛选、分页功能
6. 测试任务列表展示

### 步骤5：实现创建任务页（4小时）

1. 创建任务创建页（`views/Task/Create.vue`）
2. 实现步骤1：URL输入表单
3. 实现步骤2：调用分析API并展示问卷结构
4. 创建问卷预览组件（`components/Questionnaire/`）
5. 实现步骤3：配置提交参数
6. 实现创建任务逻辑
7. 测试完整创建流程

### 步骤6：实现任务详情页（3小时）

1. 创建任务详情页（`views/Task/Detail.vue`）
2. 创建进度条组件（`components/Task/TaskProgress.vue`）
3. 实现实时状态轮询（每3秒）
4. 实现提交记录展示
5. 测试状态更新和进度展示

### 步骤7：布局和样式优化（2小时）

1. 创建全局布局组件（`components/Layout/`）
2. 实现顶部导航栏（用户信息、退出登录）
3. 优化全局样式（`assets/styles/`）
4. 响应式布局调整
5. 暗色模式支持（可选）

### 步骤8：测试和优化（2小时）

1. 端到端功能测试
2. 错误处理完善
3. Loading状态优化
4. 性能优化（懒加载、防抖、节流）
5. 打包和部署配置

---

## 环境变量配置

### .env.development
```
VITE_API_BASE_URL=http://localhost:8000/api
VITE_APP_TITLE=问卷自动化系统
```

### .env.production
```
VITE_API_BASE_URL=https://api.example.com/api
VITE_APP_TITLE=问卷自动化系统
```

---

## package.json（依赖清单）

```json
{
  "name": "questionnaire-automation-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.2.0",
    "pinia": "^2.1.0",
    "axios": "^1.6.0",
    "element-plus": "^2.5.0",
    "@element-plus/icons-vue": "^2.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vue-tsc": "^1.8.0",
    "sass": "^1.69.0",
    "unplugin-vue-components": "^0.26.0",
    "unplugin-auto-import": "^0.17.0"
  }
}
```

---

## 启动命令

```bash
# 开发模式
npm run dev
# 访问: http://localhost:5173

# 生产构建
npm run build

# 预览生产构建
npm run preview
```

---

## 后续扩展建议

1. **WebSocket实时通信**：替代轮询，实时推送任务进度
2. **数据可视化**：任务统计图表（ECharts）
3. **批量操作**：批量删除、批量暂停任务
4. **任务模板**：保存常用配置为模板
5. **结果分析**：提交成功率趋势、失败原因分析
6. **权限管理**：多用户角色、任务权限控制
7. **日志查看**：详细的任务执行日志
8. **移动端适配**：响应式设计优化

---

## 总结

本设计方案提供了完整的前端架构，包括：

1. ✅ **技术选型**：Vue 3 + TypeScript + Element Plus
2. ✅ **项目结构**：清晰的目录组织
3. ✅ **登录模块**：完整的认证流程和路由守卫
4. ✅ **任务管理**：列表、创建、详情三个核心页面
5. ✅ **API集成**：统一的请求封装和错误处理
6. ✅ **状态管理**：Pinia管理用户和任务状态
7. ✅ **组件设计**：可复用的任务卡片、进度条等组件
8. ✅ **实施计划**：详细的开发步骤和时间估算

**预计总工作量**：约17小时

现在可以开始实施开发了！