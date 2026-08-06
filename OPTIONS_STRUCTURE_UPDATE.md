# FRONTEND_DESIGN.md 更新说明

## 核心改动：选项结构已包含真实标签

### 原数据结构（已过期）
```typescript
options: [1, 2, 3]  // 仅返回序号
```

### 新数据结构（当前有效）
```typescript
options: [
  { value: "1", label: "男" },
  { value: "2", label: "女" },
  { value: "3", label: "不愿透露" }
]
```

## 所有题型的选项格式统一

### 1. 单选题/多选题/下拉题
```typescript
options: [
  { value: "1", label: "选项文本" },
  { value: "2", label: "选项文本" }
]
```

### 2. 评分题/NPS题
```typescript
options: [
  { value: "1", label: "非常不同意" },
  { value: "2", label: "不同意" },
  { value: "3", label: "一般" },
  { value: "4", label: "同意" },
  { value: "5", label: "非常同意" }
]
```

### 3. 矩阵题
```typescript
options: [
  { value: "1", label: "非常不关注" },
  { value: "2", label: "不太关注" },
  { value: "3", label: "一般" },
  { value: "4", label: "比较关注" },
  { value: "5", label: "非常关注" }
]
```

### 4. 排序题
```typescript
options: [
  { value: "1", label: "直接降价" },
  { value: "2", label: "满减优惠" },
  { value: "3", label: "赠品活动" }
]
```

### 5. 权重分配题
```typescript
options: [
  { value: "1", label: "菜品口味", rowid: "1" },
  { value: "2", label: "价格", rowid: "2" },
  { value: "3", label: "卫生环境", rowid: "3" }
]
```

### 6. 文本题
```typescript
options: []  // 无选项
```

## 新增字段

所有问题现在都包含 `is_scale` 字段：
- `is_scale: true` - 量表题（rating/nps/matrix）
- `is_scale: false` - 非量表题

## 技术实现

- 后端使用 `ImprovedOptionExtractor` 从HTML中提取真实的选项标签
- 每个问卷的选项标签都会自动适配，无需手工配置
- 支持所有问卷星问卷的题型

## 前端使用建议

```typescript
// 显示选项标签
options.forEach(opt => {
  console.log(opt.value, opt.label)  // "1" "男"
})

// 保存回答时使用 value
submitAnswer(question.id, selectedOption.value)

// 显示用户选择时使用 label
displaySelection(selectedOption.label)  // "男"
```
