# 快代理私密代理 API 对接文档（Python）

本文用于将“按指定地区提取私密代理并用于 HTTP/HTTPS 请求”的能力集成到其他 Python 项目。示例使用 `requests`，敏感凭据统一从环境变量读取。

> 接口文档：<https://www.kuaidaili.com/doc/api/getdps/>  
> 获取代理接口：`https://dps.kdlapi.com/api/getdps/`

## 1. 对接流程

完整调用链如下：

1. 准备订单 API 凭据：`SecretId` 和请求签名/令牌。
2. 准备私密代理认证信息：代理用户名和代理密码。
3. 调用 `getdps`，通过 `area` 传入目标地区中文名称。
4. 从 `data.proxy_list` 读取代理地址。
5. 组装 `http://用户名:密码@IP:端口`。
6. 将代理配置传给业务请求的 `proxies` 参数。
7. 根据过期时间、连接错误或业务状态切换代理。

## 2. 凭据说明

对接涉及两组不同凭据：

| 配置 | 用途 | 发送位置 |
|---|---|---|
| `KDL_SECRET_ID` | 标识订单 | 获取代理 API 的 `secret_id` 参数 |
| `KDL_SIGNATURE` | API 请求签名或密钥令牌 | 获取代理 API 的 `signature` 参数 |
| `KDL_PROXY_USERNAME` | 私密代理认证用户名 | 代理 URL |
| `KDL_PROXY_PASSWORD` | 私密代理认证密码 | 代理 URL |

`SecretKey` 与 `signature` 并非在所有认证模式下都表示同一个值：

- `sign_type=token`：`signature` 应传密钥令牌，接口默认使用该模式。
- `sign_type=hmacsha1`：使用 `SecretKey` 按官方规则计算签名，同时携带 `timestamp`，可选携带 `nonce`。

如果会员中心生成的完整 API 地址已经能够成功调用，应按该地址中实际提供的 `signature` 值配置。

## 3. 环境变量

推荐使用 `.env`：

```dotenv
KDL_SECRET_ID=YOUR_SECRET_ID
KDL_SIGNATURE=YOUR_SECRET_TOKEN_OR_SIGNATURE
KDL_PROXY_USERNAME=YOUR_PROXY_USERNAME
KDL_PROXY_PASSWORD=YOUR_PROXY_PASSWORD
KDL_API_URL=https://dps.kdlapi.com/api/getdps/
KDL_REQUEST_TIMEOUT=12
```

安装依赖：

```bash
pip install requests python-dotenv
```

`.gitignore` 至少包含：

```gitignore
.env
```

生产环境建议通过容器 Secret、CI/CD Secret 或服务器环境变量注入，不把凭据写入代码、日志和 CSV。

## 4. 获取代理 API

### 4.1 请求方式

```http
GET https://dps.kdlapi.com/api/getdps/
```

### 4.2 推荐参数

| 参数 | 必填 | 示例 | 说明 |
|---|---:|---|---|
| `secret_id` | 是 | `YOUR_SECRET_ID` | 订单 SecretId |
| `signature` | 是 | `YOUR_SIGNATURE` | API 签名或令牌 |
| `num` | 是 | `1` | 本次提取数量 |
| `area` | 否 | `宁德` | 按省、市或地区编码筛选；多个地区用英文逗号分隔 |
| `format` | 否 | `json` | 推荐 JSON |
| `f_auth` | 否 | `1` | 返回鉴权信息 |
| `generateType` | 否 | `1` | 返回 `IP:端口:用户名:密码` 格式 |
| `f_loc` | 否 | `1` | 返回地区信息 |
| `f_citycode` | 否 | `1` | 返回地区编码 |
| `f_et` | 否 | `1` | 返回从提取时起的剩余可用秒数 |
| `f_carrier` | 否 | `1` | 返回运营商 |
| `dedup` | 否 | `1` | 过滤当天已提取过的 IP |
| `carrier` | 否 | `0` | `0`不限、`1`联通、`2`电信、`3`移动 |

`area` 直接传中文即可，`requests` 会自动进行 URL 编码：

```python
params = {"area": "宁德"}
requests.get(API_URL, params=params)
```

不要手工拼接未经转义的查询字符串。

### 4.3 调用频率

文档标注的接口频率为：

- 最快 `10次/秒`
- 最多 `120次/分钟`

持续运行时应实施本地限速、失败退避，并避免多个进程共同突破订单限制。

## 5. API 返回结果

成功响应核心结构：

```json
{
  "code": 0,
  "msg": "",
  "data": {
    "count": 1,
    "proxy_list": [
      "PROXY_IP:PROXY_PORT:PROXY_USER:PROXY_PASSWORD,地区,地区编码,剩余秒数,运营商"
    ],
    "dedup_count": 1,
    "order_left_count": 999
  }
}
```

实际 `proxy_list` 项的形态可能随返回参数或订单配置变化。集成层应兼容：

- `IP:端口`
- `IP:端口:用户名:密码`
- 带地区、地区编码、剩余时间和运营商的扩展字符串
- 数组或对象形式

判断成功必须使用：

```python
payload.get("code") == 0
```

不能只依赖 HTTP 200。

## 6. 可复用 Python 客户端

下面的客户端适合复制到其他项目，例如保存为 `kuaidaili_client.py`。

```python
from __future__ import annotations

import os
from dataclasses import dataclass

import requests
from dotenv import load_dotenv


class KdlApiError(RuntimeError):
    pass


@dataclass
class ProxyEndpoint:
    host: str
    port: int
    username: str = ""
    password: str = ""

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def url(self) -> str:
        if self.username:
            return f"http://{self.username}:{self.password}@{self.address}"
        return f"http://{self.address}"

    @property
    def requests_proxies(self) -> dict[str, str]:
        return {"http": self.url, "https": self.url}


class KdlClient:
    def __init__(
        self,
        secret_id: str,
        signature: str,
        proxy_username: str = "",
        proxy_password: str = "",
        api_url: str = "https://dps.kdlapi.com/api/getdps/",
        timeout: float = 12,
    ) -> None:
        self.secret_id = secret_id
        self.signature = signature
        self.proxy_username = proxy_username
        self.proxy_password = proxy_password
        self.api_url = api_url
        self.timeout = timeout
        self.session = requests.Session()

    @classmethod
    def from_env(cls) -> "KdlClient":
        load_dotenv()
        return cls(
            secret_id=os.environ["KDL_SECRET_ID"],
            signature=os.environ["KDL_SIGNATURE"],
            proxy_username=os.getenv("KDL_PROXY_USERNAME", ""),
            proxy_password=os.getenv("KDL_PROXY_PASSWORD", ""),
            api_url=os.getenv("KDL_API_URL", "https://dps.kdlapi.com/api/getdps/"),
            timeout=float(os.getenv("KDL_REQUEST_TIMEOUT", "12")),
        )

    def acquire(self, area: str, num: int = 1) -> list[ProxyEndpoint]:
        params = {
            "secret_id": self.secret_id,
            "signature": self.signature,
            "num": num,
            "area": area,
            "format": "json",
            "sep": 1,
            "f_auth": 1,
            "generateType": 1,
            "f_loc": 1,
            "f_citycode": 1,
            "f_et": 1,
            "f_carrier": 1,
        }
        response = self.session.get(self.api_url, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise KdlApiError(
                f"getdps failed: code={payload.get('code')}, msg={payload.get('msg', '')}"
            )

        items = (payload.get("data") or {}).get("proxy_list") or []
        return [self._parse_proxy(item) for item in items]

    def _parse_proxy(self, item) -> ProxyEndpoint:
        if isinstance(item, dict):
            host = str(item.get("ip") or item.get("host") or "")
            port = int(item.get("port") or 0)
            username = str(item.get("username") or self.proxy_username)
            password = str(item.get("password") or self.proxy_password)
            return ProxyEndpoint(host, port, username, password)

        # 先去除逗号后的地区等扩展字段。
        address_and_auth = str(item).split(",", 1)[0].strip()
        parts = address_and_auth.split(":")
        if len(parts) < 2:
            raise KdlApiError(f"invalid proxy item: {item!r}")

        host, port = parts[0], int(parts[1])
        username = parts[2] if len(parts) >= 4 else self.proxy_username
        password = ":".join(parts[3:]) if len(parts) >= 4 else self.proxy_password

        # 配置的订单固定账密优先，便于统一管理。
        if self.proxy_username:
            username = self.proxy_username
            password = self.proxy_password
        return ProxyEndpoint(host, port, username, password)
```

## 7. 在业务项目中使用

### 7.1 单次请求

```python
import requests

from kuaidaili_client import KdlClient

client = KdlClient.from_env()
proxy = client.acquire(area="宁德", num=1)[0]

response = requests.get(
    "https://myip.ipip.net/",
    proxies=proxy.requests_proxies,
    timeout=12,
)
response.raise_for_status()
print(response.text)
```

### 7.2 复用 Session

```python
import requests

from kuaidaili_client import KdlClient

client = KdlClient.from_env()
proxy = client.acquire(area="宁德")[0]

session = requests.Session()
session.proxies.update(proxy.requests_proxies)
session.headers.update({"User-Agent": "your-project/1.0"})

response = session.get("https://TARGET.example/api", timeout=12)
response.raise_for_status()
```

### 7.3 HTTP 与 HTTPS 的配置方式

即使目标地址是 HTTPS，私密代理 URL 通常仍使用 `http://`：

```python
proxy_url = "http://USERNAME:PASSWORD@PROXY_IP:PROXY_PORT"
proxies = {
    "http": proxy_url,
    "https": proxy_url,
}
```

HTTPS 目标由客户端通过 HTTP 代理的 `CONNECT` 隧道访问。

## 8. 出口 IP 与地区验证

可通过代理请求：

```text
https://myip.ipip.net/
```

当前返回为 UTF-8 纯文本：

```text
当前 IP：EXIT_IP  来自于：中国 福建 宁德  电信
```

简单解析示例：

```python
import ipaddress
import re


def parse_ipip(text: str) -> dict[str, str]:
    value = " ".join(text.strip().split())
    match = re.search(r"当前\s*IP[：:]\s*(\S+)\s+来自于[：:]\s*(.+)$", value)
    if not match:
        raise ValueError(f"无法解析 IPIP 响应: {value[:200]}")

    ip = match.group(1)
    ipaddress.ip_address(ip)
    parts = match.group(2).split()
    return {
        "ip": ip,
        "country": parts[0] if len(parts) > 0 else "",
        "region": parts[1] if len(parts) > 1 else "",
        "city": parts[2] if len(parts) > 2 else "",
        "isp": " ".join(parts[3:]) if len(parts) > 3 else "",
    }
```

该地址不返回 ASN。若业务需要 ASN、风险评分或住宅/机房判定，应额外接入相应数据源。

## 9. 错误码与处理建议

| 错误码 | 含义 | 建议处理 |
|---:|---|---|
| `1` | 今日提取余额已用尽 | 停止提取并告警 |
| `2` | 订单提取余额已用尽 | 停止提取并检查订单 |
| `3` | 没有符合条件的代理 | 更换地区或稍后重试 |
| `4` | 账号尚未完成实名认证 | 检查账号状态 |
| `-1` | 无效请求 | 检查请求格式 |
| `-2` | 订单无效或尚未生效 | 新订单等待后重试 |
| `-3` | 参数错误 | 检查地区、数量、签名参数 |
| `-4` | 提取失败 | 记录消息并指数退避 |
| `-5` | 订单不能提取私密代理 | 检查订单类型 |
| `-6` | 调用 IP 不在白名单 | 更新 API 调用白名单 |
| `-51` | 调用来源或频率受限 | 降低并发及调用频率 |
| `-11` | 订单尚未支付 | 检查订单状态 |
| `-12` | 订单无效 | 停止调用并告警 |
| `-13/-15` | 订单已过期 | 续费或更换订单 |
| `-14` | 订单被封禁 | 检查订单状态 |
| `-16` | 订单已退款 | 更换有效订单 |

建议区分三类异常：

1. **API 获取异常**：HTTP 错误、JSON 解析错误、`code != 0`。
2. **代理连接异常**：连接超时、代理认证失败、TLS 错误。
3. **业务响应异常**：代理可连接，但目标业务返回非预期状态。

## 10. 重试与代理轮换

推荐策略：

- 获取代理 API：网络错误最多重试 2～3 次，使用指数退避。
- `code=1/2/-11/-12/-13/-14/-15/-16`：直接停止并告警。
- `code=3/-4/-51`：等待后重试，不进行高频循环。
- 代理连接失败：废弃当前代理并重新获取。
- 业务返回 403/429：根据业务规则切换代理，同时实施全局限流。
- 结合 `f_et=1` 返回的剩余秒数，在到期前主动刷新。

示例：

```python
import time
import requests


def get_with_rotation(client, url: str, area: str, attempts: int = 3):
    last_error = None
    for index in range(attempts):
        proxy = client.acquire(area=area, num=1)[0]
        try:
            response = requests.get(
                url,
                proxies=proxy.requests_proxies,
                timeout=(5, 15),
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(min(2 ** index, 8))
    raise RuntimeError(f"代理请求连续失败: {last_error}")
```

## 11. 安全与日志要求

- 不记录完整 API URL，因为查询字符串包含签名。
- 不记录带用户名、密码的代理 URL。
- 日志只保留代理 IP、端口、地区、错误类型和请求耗时。
- `.env`、运行日志、异常追踪和 CSV 均应检查是否泄露凭据。
- 定期更新 API 令牌及代理密码。
- 生产环境为不同项目分配独立配置，便于撤销和审计。

可使用下面的脱敏函数：

```python
def proxy_log_label(proxy) -> str:
    return f"{proxy.host}:{proxy.port}"
```

## 12. 集成检查清单

- [ ] 环境变量已配置且未提交到版本库
- [ ] API 调用使用 `params`，未手工拼接中文地区
- [ ] 同时检查 HTTP 状态和业务 `code`
- [ ] HTTP、HTTPS 均配置代理
- [ ] 请求设置连接和读取超时
- [ ] 已处理代理认证失败和过期切换
- [ ] 已实施 API 调用频率限制
- [ ] 日志中没有签名、用户名或密码
- [ ] 已用 `https://myip.ipip.net/` 验证实际出口与地区
- [ ] 已针对订单耗尽、过期和白名单错误配置告警

