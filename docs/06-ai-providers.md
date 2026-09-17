# 06 · AI 服务商集成契约

> 覆盖两类协议：**OpenAI 兼容 API**（OpenAI / DeepSeek / 通义 / 智谱 / Ollama / vLLM 等）与 **Anthropic 原生 API**（Claude 及其兼容网关）。

---

## 1. 目标与硬约束

| # | 约束 |
|---|---|
| A1 | **必须**支持两类协议，且用户可自由增删服务商，不锁定任何厂商 |
| A2 | 每个服务商配置**必须**包含三字段：Base URL、API Key、模型名（缺一不可保存） |
| A3 | Temperature / Max Tokens 为**可选**字段，缺失时用服务商默认值 |
| A4 | API Key 永不写入配置文件、日志、异常消息、诊断包 |
| A5 | 所有网络错误必须映射为**明确中文提示**，网络 / 鉴权 / 限流类**必须支持重试** |
| A6 | 请求不得在 URL 中携带密钥（即使部分网关支持 query key 也一律拒绝） |

---

## 2. ProviderProfile 数据契约

```python
class ProviderType(str, Enum):
    OPENAI_COMPATIBLE = "openai_compatible"  # POST /chat/completions
    ANTHROPIC_NATIVE = "anthropic_native"  # POST /v1/messages


@dataclass
class ProviderProfile:
    id: str  # UUIDv4
    name: str  # 用户命名，如「DeepSeek 主账号」
    type: ProviderType
    base_url: str  # 必填；自动补全尾随斜杠，校验为合法 URL
    api_key: str  # 必填；仅存内存，持久化走密钥库
    model: str  # 必填，非空
    temperature: float | None = None  # 可选，0.0–2.0
    max_tokens: int | None = None  # 可选；Anthropic 缺失时强制默认 4096
    timeout_seconds: float = 120.0
    max_retries: int = 3
    # 兼容开关（不同网关差异）
    use_max_completion_tokens: bool = False  # OpenAI o 系列等新字段
    api_version_header: str | None = None  # 如 2023-06-01
    extra_headers: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    is_default: bool = False
    created_at: str
    updated_at: str
```

### 2.1 校验规则

| 字段 | 校验 |
|---|---|
| base_url | 必须是 http / https；不得包含 @ 或用户名密码；不得以 query 参数携带 key；Anthropic 类型必须以 /v1 结尾（否则自动补 /v1 并提示） |
| api_key | 非空；去除首尾空白；长度 ≥ 8 |
| model | 非空；仅允许字母数字与点号、下划线、连字符、冒号 |
| temperature | None 或 [0.0, 2.0] |
| max_tokens | None 或 [1, 65536] |
| 连接测试 | 保存时可选执行「测试连接」（发送 1 token 请求），失败不阻断保存但给出提示 |

---

## 3. 统一接口

```python
@dataclass(frozen=True)
class SummaryRequest:
    prompt: str  # 已渲染完整 Prompt
    transcript: str  # 用于分片统计
    max_input_tokens: int | None = None


@dataclass(frozen=True)
class SummaryResponse:
    markdown: str  # 原始返回正文
    provider_id: str
    model: str
    usage: Usage | None
    raw: dict  # 原始响应（脱敏后落盘用于排查）
    latency_ms: int
    attempts: int


class SummaryProvider(Protocol):
    def build(self, profile, req) -> HttpRequest: ...
    def parse(self, profile, resp) -> SummaryResponse: ...
```

客户端统一入口为 SummaryClient 的 call 方法，签名为 call(profile, req) → SummaryResponse。它负责：超时、重试、限流、错误映射、日志脱敏。

---

## 4. OpenAI 兼容适配器

### 4.1 请求构造

**URL**：{base_url} 拼接 /chat/completions（base_url 末尾斜杠去重；若 base_url 已含 /chat/completions 则直接使用）

**Headers**：

| Header | 值 |
|---|---|
| Authorization | Bearer 后接 api_key |
| Content-Type | application/json |
| User-Agent | MeetRecMaster/{version} (python; {platform}) |
| 额外 header | 用户自定义（如网关联机 token），仅允许白名单 header 名 |

**Body**：

```json
{
  "model": "deepseek-chat",
  "messages": [
    {"role": "system", "content": "你是专业的会议纪要助手。"},
    {"role": "user",   "content": "<已渲染的完整 Prompt>"}
  ],
  "temperature": 0.2,
  "max_tokens": 4096,
  "stream": false
}
```

### 4.2 字段兼容差异（不同网关）

| 差异点 | 处理方式 |
|---|---|
| max_tokens 与 max_completion_tokens | 默认发 max_tokens；开启 use_max_completion_tokens 后改发 max_completion_tokens（OpenAI o 系列、部分新网关） |
| 不支持 temperature | 部分网关返回 400 → 自动降级重试一次（去掉 temperature），并在 UI 提示该服务商不支持自定义 temperature |
| 不支持 n / top_p | 一律不发送（避免兼容性问题） |
| 需要 api-key header 而非 Bearer | 通过额外 header 配置 Authorization，并在 base_url 校验时提醒 |
| 返回 content 为数组（多模态网关） | 解析时兼容字符串与数组两种形态，取 text 字段拼接 |
| 无 usage 字段 | usage 记为 None，UI 不显示 token 用量 |

### 4.3 响应解析

```python
choices[0].message.content  # 正文
usage.prompt_tokens / completion_tokens / total_tokens
```

解析失败（结构不符）→ 抛 ProviderResponseError（原文保留）。

---

## 5. Anthropic 原生适配器

### 5.1 与 OpenAI 协议的关键差异

| 项 | OpenAI 兼容 | Anthropic 原生 |
|---|---|---|
| 端点 | /chat/completions | /v1/messages |
| 认证 | Authorization: Bearer | x-api-key |
| 版本头 | 无 | **anthropic-version: 2023-06-01（必填）** |
| 系统提示 | messages 中的 system 角色 | **顶层 system 字段（必填，字符串或 content 数组）** |
| max_tokens | 可选 | **必填**，缺失直接 400 |
| messages 内容 | content 为字符串 | content 为**字符串或 content block 数组** |
| 角色 | system / user / assistant | **只有 user / assistant**（无 system 角色） |
| 流式 | stream: true | stream: true + SSE event 结构不同 |

### 5.2 请求构造

**URL**：{base_url} 拼接 /messages（base_url 以 /v1 结尾）

**Headers**：

| Header | 值 |
|---|---|
| x-api-key | api_key |
| anthropic-version | 2023-06-01（可由 api_version_header 覆盖） |
| Content-Type | application/json |
| User-Agent | MeetRecMaster/{version} (python; {platform}) |

**Body**：

```json
{
  "model": "claude-sonnet-4-20250514",
  "max_tokens": 4096,
  "temperature": 0.2,
  "system": "你是专业的会议纪要助手。",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "<已渲染的完整 Prompt>"}
      ]
    }
  ]
}
```

### 5.3 强制规则

1. **max_tokens 必填**：用户未配置时强制填 4096，并在设置中标注「使用默认值」。
2. **system 不可省**：即使 Prompt 内含角色说明，也必须提供非空 system 字段。
3. **不使用 system 角色消息**：把角色说明一律提升到顶层 system。
4. **content 用 block 数组**：便于后续扩展（附件、缓存控制块）。
5. **响应解析**：取 content 数组中所有 type=text 的 text 拼接；usage 取 input_tokens / output_tokens。
6. **停止原因**：stop_reason 为 max_tokens → 提示「输出被截断，请调大 Max Tokens 或分段总结」。

---

## 6. 重试与退避策略

### 6.1 可重试判定

| 场景 | 判定 | 重试 |
|---|---|---|
| DNS 解析失败 / 连接被拒 / TLS 握手失败 | 网络错误 | ✅ 重试 |
| 连接超时 / 读取超时 | 超时 | ✅ 重试 |
| HTTP 408 | 网关超时 | ✅ 重试 |
| HTTP 409 | 冲突（部分网关表示队列满） | ✅ 重试 |
| HTTP 425 | Too Early（gRPC 网关） | ✅ 重试 |
| HTTP 429 | 限流 | ✅ 重试，优先遵循 Retry-After |
| HTTP 500 / 502 / 503 / 504 | 服务端错误 | ✅ 重试 |
| HTTP 401 / 403 | 鉴权失败 | ❌ 不重试（引导用户改 Key） |
| HTTP 400 / 404 | 参数或模型错误 | ❌ 不重试 |
| HTTP 413 | 请求体过大 | ❌ 不重试（提示缩短或分段） |
| 响应结构无法解析 | 解析失败 | ❌ 不重试（保留原文） |

### 6.2 退避算法

```text
delay = min(base * 2^attempt + jitter, cap)
base = 1.0s, cap = 30s, jitter = uniform(0, 0.3 * delay)
最多重试 max_retries（默认 3）次
若响应含 Retry-After（秒或 HTTP 日期），delay = max(delay, Retry-After)
总等待时间超过 timeout_seconds * 2 时中止
```

### 6.3 UI 反馈

- 第 1 次重试起显示「第 N / M 次重试，{delay} 秒后继续」，并提供「取消」按钮。
- 全部失败后弹中文提示（见 6.4）+ 「重新尝试」按钮。
- 每次尝试记录到日志（脱敏）。

### 6.4 错误码 → 异常 → 中文提示映射

| 来源 | 异常 | 中文提示 | 可重试 |
|---|---|---|---|
| 连接失败 / DNS / TLS | ProviderNetworkError | 无法连接到服务商：网络不可用或 Base URL 填写有误，请检查后重试 | ✅ |
| 超时 | ProviderNetworkError | 请求超时（{timeout} 秒），服务商可能繁忙，请稍后重试 | ✅ |
| 401 | ProviderAuthError | API Key 无效或已过期，请在设置中重新填写 | ❌ 引导 |
| 403 | ProviderAuthError | 该 API Key 无权限访问模型 {model}，请确认账号权限 | ❌ 引导 |
| 404 | ProviderResponseError | 模型 {model} 不存在或 Base URL 不正确，请核对服务商文档 | ❌ |
| 400 | ProviderResponseError | 请求参数不被该服务商支持：{detail}。可尝试关闭 temperature 后重试 | ✅ 降级 |
| 413 | ProviderResponseError | 转写内容过长，超出服务商请求限制，请分段总结或更换模型 | ❌ |
| 429 | ProviderRateLimitError | 服务商限流，请等待 {retry_after} 秒后重试 | ✅ 自动 |
| 5xx | ProviderNetworkError | 服务商暂时不可用（{status}），将自动重试 | ✅ 自动 |
| 结构解析失败 | ProviderResponseError | 服务商返回内容无法解析，已保留原始文本，可手动整理 | ❌ |
| 缺少 5 个章节 | ProviderSectionMissing | AI 返回内容缺少必要章节（{missing}），请更换模型或调整 Prompt 模板后重试 | ✅ |
| stop_reason=max_tokens | ProviderResponseError | 输出被截断，请调大 Max Tokens 或分段总结 | ❌ 引导 |

---

## 7. 超时与取消

| 项 | 值 |
|---|---|
| 连接超时 | 15 秒 |
| 读取超时 | profile.timeout_seconds（默认 120 秒） |
| 取消 | 用户点「取消」→ 中断 HTTP 连接；已完成的分片结果保留，可「继续」 |
| 幂等 | 请求不带幂等键；重试可能重复计费，UI 在重试前提示 |

---

## 8. 上下文窗口与分片（map-reduce）

1. 估算输入 token：中文按 字符数 × 0.6，英文按 字符数 / 4，取较大值。
2. 单片上限 = min(服务商声明窗口 × 0.8, 用户配置的 max_input_tokens)。
3. 超限时按段落边界分片，每片独立总结（map），再用同一模板汇总（reduce）。
4. 分片数 > 4 时在开始前列出分片计划并让用户确认（避免意外计费）。
5. 每片单独记录 latency / usage，汇总到 usage 总计。

---

## 9. 日志与脱敏

| 内容 | 记录方式 |
|---|---|
| base_url | 记录（不含 query） |
| api_key | **永不记录** |
| Authorization / x-api-key | **永不记录** |
| 请求体 | 只记录长度与 sha256 前 12 位 |
| 响应体 | 记录前 2000 字符（不含密钥），完整原文落盘到会话目录 |
| 错误 detail | 记录，但过滤疑似密钥的连续长 token（≥32 字符且高熵） |

---

## 10. 契约测试与 Mock

| 测试 | 内容 |
|---|---|
| 请求构造单测 | 每类协议：headers、URL 拼接（含 base_url 已带路径）、字段兼容开关、system 提升、content block 形态 |
| 响应解析单测 | 正常 / content 为数组 / 缺 usage / 结构异常 / stop_reason=max_tokens |
| 重试单测 | 429 + Retry-After、500 三次、401 不重试、400 降级去 temperature |
| 契约测试（可选，需网络） | 对真实 OpenAI 兼容与 Anthropic 端点各跑 1 条最小请求；默认 skip，用环境变量开启 |
| 脱敏单测 | 断言日志中不含 Key 子串 |
| Mock | 用 responses / respx 拦截 HTTP；ASR 用假引擎（固定返回 segments） |

---

## 11. 安全补充

1. Key 只在内存中短暂持有，持久化走密钥库（见 [08 章](08-security.md)）。
2. 禁止在 URL 中携带 Key；校验时若发现 query 参数疑似 Key → 阻断保存。
3. 诊断包导出时强制剔除 Authorization / x-api-key / api_key 字段。
4. 支持「清除全部服务商凭据」一键操作。
5. 多服务商切换不缓存上一家的 Key 到全局变量。

---

## 12. 相关文档

- [04 · 核心模块规格](04-core-modules.md)
- [07 · 数据模型与持久化](07-data-model.md)
- [08 · 安全规范](08-security.md)


