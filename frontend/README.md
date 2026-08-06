# 前端应用

基于 Vue 3、TypeScript、Vite、Element Plus、Pinia 和 Axios。启动：

```bash
npm install
npm run dev
```

默认 API 地址为 `http://localhost:8000`，可通过 `VITE_API_BASE_URL` 覆盖。

当前后端已提供问卷分析、提交和任务状态接口；设计文档中的认证、任务列表和删除接口尚未在 FastAPI 中实现。前端对登录和任务列表/删除提供了本地降级，接入对应后端路由后会自动使用服务端数据。
