# 阿里云智能验证码逆向分析指南

## 目标
分析阿里云点击验证码的工作原理，找到API接口和参数生成逻辑，尝试绕过前端UI直接调用验证接口。

---

## 步骤1: 打开浏览器开发者工具

**操作：**
1. 在已打开验证码的页面，按 `F12` 打开开发者工具
2. 切换到 **Network（网络）** 标签
3. 确保 **Preserve log（保留日志）** 已勾选
4. 清空当前记录（点击禁止图标）

---

## 步骤2: 监控网络请求

**操作：**
1. 在 Network 标签中，添加过滤器：输入 `aliyun` 或 `captcha`
2. 手动点击验证码 checkbox 一次
3. 观察捕获到的网络请求

**需要找到的关键请求：**

### 2.1 初始化请求
- URL 可能包含：`initialize`、`init`、`scene`
- 返回验证码配置和 token
- 示例：`https://sg.captcha.aliyuncs.com/initialize.jsonp`

### 2.2 验证请求
- URL 可能包含：`verify`、`check`、`validate`
- 发送验证参数
- 返回验证结果
- 示例：`https://sg.captcha.aliyuncs.com/verify.jsonp`

**记录下来：**
```
请求URL: _____________________
请求方法: GET / POST
请求参数: _____________________
响应数据: _____________________
```

---

## 步骤3: 分析JavaScript代码

### 3.1 查找阿里云SDK文件

**操作：**
1. 切换到 **Sources（源代码）** 标签
2. 搜索文件名（Ctrl+P）：
   - `aliyun-captcha`
   - `awsc`
   - `nc.js`
   - `ic.js` (intelligent captcha)

### 3.2 设置断点调试

**在以下位置设置断点：**
1. 搜索关键函数（Ctrl+F）：
   ```javascript
   verify
   validate
   check
   callback
   success
   getCaptchaVerifyParam
   ```

2. 点击行号设置断点
3. 刷新页面或重新触发验证码
4. 当代码暂停时，查看：
   - 调用栈（Call Stack）
   - 作用域变量（Scope）
   - 本地变量（Local）

**重点关注的变量：**
```javascript
token / sessionId
scene / sceneId
sig / signature
captchaVerifyParam
```

---

## 步骤4: 使用Console注入分析代码

### 4.1 查找全局对象

在 Console 中执行：

```javascript
// 查找阿里云验证码实例
console.log(window.AWSC);
console.log(window.ic);
console.log(window.nc);
console.log(window._captcha_instance);

// 遍历所有全局变量
Object.keys(window).filter(key =>
  key.toLowerCase().includes('captcha') ||
  key.toLowerCase().includes('aliyun')
);
```

### 4.2 Hook关键函数

```javascript
// Hook XMLHttpRequest
(function() {
  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function(method, url) {
    this._url = url;
    this._method = method;
    return originalOpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function(data) {
    if (this._url && this._url.includes('aliyun')) {
      console.log('🔍 阿里云请求拦截:');
      console.log('  URL:', this._url);
      console.log('  Method:', this._method);
      console.log('  Data:', data);

      this.addEventListener('load', function() {
        console.log('  Response:', this.responseText);
      });
    }
    return originalSend.apply(this, arguments);
  };
})();

console.log('✅ XHR Hook 已安装，现在点击验证码...');
```

### 4.3 Hook Fetch API

```javascript
(function() {
  const originalFetch = window.fetch;

  window.fetch = function(...args) {
    const url = args[0];
    if (url && url.includes && url.includes('aliyun')) {
      console.log('🔍 Fetch请求拦截:');
      console.log('  URL:', url);
      console.log('  Options:', args[1]);
    }

    return originalFetch.apply(this, args).then(response => {
      if (url && url.includes && url.includes('aliyun')) {
        response.clone().text().then(text => {
          console.log('  Response:', text);
        });
      }
      return response;
    });
  };
})();

console.log('✅ Fetch Hook 已安装');
```

---

## 步骤5: 分析验证流程

### 5.1 典型的阿里云验证流程

```
1. 页面加载 → 初始化验证码
   ↓
   调用: initialize API
   返回: { token, scene, config }

2. 用户点击 checkbox
   ↓
   触发: 智能风控分析
   收集: 浏览器指纹、行为数据

3. 生成验证参数
   ↓
   函数: getCaptchaVerifyParam() 或类似
   生成: sig (签名), sessionId, 其他参数

4. 调用验证接口
   ↓
   发送: verify API + 参数
   返回: { success: true/false, token }

5. 回调处理
   ↓
   成功: onSuccess(token)
   失败: onFail() → 显示滑块/点选
```

### 5.2 查找验证参数生成逻辑

在 Console 执行：

```javascript
// 查找包含特定字符串的所有函数
function findFunctions(keyword) {
  for (let key in window) {
    try {
      if (typeof window[key] === 'function') {
        const funcStr = window[key].toString();
        if (funcStr.includes(keyword)) {
          console.log(`找到函数: ${key}`);
          console.log(funcStr.substring(0, 200) + '...');
        }
      } else if (typeof window[key] === 'object' && window[key] !== null) {
        for (let subKey in window[key]) {
          if (typeof window[key][subKey] === 'function') {
            const funcStr = window[key][subKey].toString();
            if (funcStr.includes(keyword)) {
              console.log(`找到函数: ${key}.${subKey}`);
              console.log(funcStr.substring(0, 200) + '...');
            }
          }
        }
      }
    } catch (e) {}
  }
}

// 搜索关键词
findFunctions('captchaVerifyParam');
findFunctions('verify');
findFunctions('signature');
```

---

## 步骤6: 提取关键参数

### 6.1 iframe分析

阿里云验证码通常在 iframe 中，需要访问 iframe 内容：

```javascript
// 查找验证码 iframe
const frames = document.querySelectorAll('iframe');
frames.forEach((frame, index) => {
  console.log(`Frame ${index}:`, frame.src);
  try {
    console.log('  Content:', frame.contentWindow);
  } catch (e) {
    console.log('  跨域限制');
  }
});

// 如果不跨域，可以访问
const captchaFrame = document.querySelector('#aliyunCaptcha-window-popup iframe');
if (captchaFrame) {
  const frameDoc = captchaFrame.contentDocument;
  const frameWindow = captchaFrame.contentWindow;

  console.log('Iframe window:', frameWindow);
  console.log('Iframe window keys:', Object.keys(frameWindow));
}
```

### 6.2 查找验证配置

```javascript
// 在主窗口和iframe中查找配置对象
function findConfig() {
  const windows = [window];

  // 添加所有可访问的iframe
  document.querySelectorAll('iframe').forEach(frame => {
    try {
      windows.push(frame.contentWindow);
    } catch (e) {}
  });

  windows.forEach((win, index) => {
    console.log(`\n=== Window ${index} ===`);

    // 查找配置对象
    ['_config', '_captchaConfig', 'config', '__aliyun_captcha_config'].forEach(key => {
      if (win[key]) {
        console.log(`${key}:`, win[key]);
      }
    });
  });
}

findConfig();
```

---

## 步骤7: 尝试直接调用验证接口

### 7.1 从network请求中提取参数模板

假设你捕获到的验证请求是：
```
https://sg.captcha.aliyuncs.com/verify.jsonp?
  a=scene&
  s=token_value&
  sig=signature_value&
  sessionId=session_value&
  callback=jsonp_callback
```

### 7.2 在Console中模拟请求

```javascript
// 方法1: 使用fetch
async function testVerifyAPI() {
  const params = {
    scene: 'YOUR_SCENE_ID',  // 从初始化响应中获取
    token: 'YOUR_TOKEN',      // 从初始化响应中获取
    sig: 'YOUR_SIGNATURE',    // 需要分析生成逻辑
    sessionId: 'YOUR_SESSION',
    // 其他必要参数
  };

  const url = 'https://sg.captcha.aliyuncs.com/verify.jsonp?' +
              new URLSearchParams(params).toString();

  const response = await fetch(url);
  const text = await response.text();
  console.log('验证结果:', text);
}

testVerifyAPI();
```

```javascript
// 方法2: 调用页面已有的验证函数
// 需要先找到验证实例
if (window._captcha_instance) {
  // 假设有这样的方法
  window._captcha_instance.verify({
    // 参数
  }).then(result => {
    console.log('验证结果:', result);
  });
}
```

---

## 步骤8: 分析签名/参数生成算法

### 8.1 常见的参数生成方式

```javascript
// 签名通常基于：
sig = hash(token + sessionId + timestamp + secret)

// 或者：
sig = encrypt(userAgent + screenInfo + mouseTrack)
```

### 8.2 在源码中查找加密函数

搜索关键词：
- `md5`、`sha1`、`sha256`
- `encrypt`、`decrypt`
- `sign`、`signature`
- `hmac`
- `base64`

### 8.3 使用debugger追踪

```javascript
// 在生成签名的地方设置断点
// 查看调用栈，找到参数来源

// 或者重写关键函数来记录参数
if (window.btoa) {
  const originalBtoa = window.btoa;
  window.btoa = function(str) {
    console.log('base64编码:', str);
    console.trace(); // 打印调用栈
    return originalBtoa(str);
  };
}
```

---

## 步骤9: Python自动化实现

一旦找到了API接口和参数生成逻辑，可以在Python中实现：

```python
import requests
import hashlib
import time

class AliyunCaptchaSolver:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.scene_id = None

    def initialize(self, scene_id):
        """初始化验证码"""
        url = f"https://sg.captcha.aliyuncs.com/initialize.jsonp"
        params = {
            'a': scene_id,
            't': int(time.time() * 1000),
        }
        response = self.session.get(url, params=params)
        # 解析JSONP响应
        # 提取 token
        return self.token

    def generate_signature(self, token, session_id):
        """生成签名（需要根据实际逻辑实现）"""
        # 这里的逻辑需要根据逆向结果来写
        data = f"{token}{session_id}{int(time.time())}"
        return hashlib.md5(data.encode()).hexdigest()

    def verify(self):
        """调用验证接口"""
        sig = self.generate_signature(self.token, self.session_id)

        url = "https://sg.captcha.aliyuncs.com/verify.jsonp"
        params = {
            's': self.token,
            'sig': sig,
            'sessionId': self.session_id,
            # 其他参数
        }

        response = self.session.get(url, params=params)
        return response.text

# 使用
solver = AliyunCaptchaSolver()
solver.initialize('YOUR_SCENE_ID')
result = solver.verify()
print(result)
```

---

## 重要提示

### 可能遇到的障碍：

1. **混淆代码**: 阿里云SDK通常经过混淆，变量名类似 `_0x1a2b3c`
2. **动态加载**: 某些代码可能动态生成或远程加载
3. **环境检测**: 可能检测 DevTools 是否打开
4. **签名算法复杂**: 可能使用私有加密算法
5. **服务端验证**: 即使绕过前端，服务端仍会验证行为特征

### 如果遇到困难：

1. 使用 **webpack/uglify 反混淆工具**
2. 使用 **控制台 Overrides** 修改源码调试
3. 分析 **wasm** 文件（如果使用了WebAssembly）
4. 考虑使用 **代理工具**（Charles、Fiddler）分析HTTPS流量

---

## 下一步

完成上述分析后，请提供：
1. 捕获到的网络请求（URL、参数、响应）
2. 找到的关键JavaScript代码片段
3. 验证流程图
4. 遇到的具体问题

我会帮你进一步分析和编写自动化代码。
