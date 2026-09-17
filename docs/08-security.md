# 08 · 安全规范

---

## 1. 威胁模型

| 资产 | 威胁 | 缓解 |
|---|---|---|
| API Key | 明文落盘、日志泄漏、诊断包外泄 | 密钥库存储；日志脱敏；诊断包强制剔除 |
| 会议录音 | 被上传到未知服务 | **绝不上传**；仅在用户主动配置服务商时发送**文本**（转写结果），不发送音频 |
| 转写文本 / 纪要 | 被第三方读取 | 仅本地存储；导出由用户选择路径 |
| 应用二进制 | 被篡改 | sha256 校验和自验（SHA256SUMS.txt 随 Release 分发）+ Release 页面标注 git commit SHA。**不做代码签名**（ADR-012，不商用场景） |
| 依赖包 | 恶意或漏洞依赖 | pip-audit + 哈希锁定 + 仅官方源 |
| 本机其他进程 | 读取配置文件 | 配置文件不含密钥；密钥库受系统保护 |

### 1.1 数据流边界（重要）

```text
录音音频 ──(本地)──▶ ASR 转写 ──(本地)──▶ 关键词校正 ──(本地)──▶ 文本
                                                                    │
                                                    用户主动点击「生成纪要」
                                                                    ▼
                                                        仅发送 Prompt 文本到用户配置的服务商
                                                                    │
                                                                    ▼
                                                        服务商返回纪要 Markdown（本地保存）
```

**明确**：音频与原始录音**永不**离开本机；网络请求内容仅为 Prompt 文本（含转写内容）与配置的服务商地址。

---

## 2. API Key 存储

### 2.1 首选方案：系统密钥库（keyring）

| 平台 | 后端 |
|---|---|
| macOS | Keychain（keyring backend: macOS-keychain） |
| Windows | Credential Manager（DPAPI 保护） |
| Linux | Secret Service / GKeyring |

- 存储键名：service = MeetRecMaster，account = provider:{provider_id}。
- providers.json 中只写占位符 __vault__:{secret_id}。
- 读取时按需取，不常驻内存；退出前清空内存副本。

### 2.2 降级方案：本地加密文件

当 keyring 不可用（CI、精简 Windows、无桌面会话）时降级到本地文件：

```text
文件：vault.enc（权限 0600 / Windows 仅当前用户）
格式：version | salt(32B) | nonce(12B) | ciphertext(AES-256-GCM)

主密钥派生：
  material = machine_fingerprint + 随机盐
  key = scrypt(password=material, salt=salt, n=2^17, r=8, p=1, dklen=32)

machine_fingerprint = 操作系统账号名 + 机器唯一标识（hostname + 稳定 UUID）
```

- 使用 cryptography 的 AESGCM 实现。
- 文件首次创建时提示用户「当前使用本地加密存储，安全性低于系统钥匙串」。
- 密钥库可用后提供「迁移到钥匙串」按钮，迁移成功后删除 vault.enc。

### 2.3 禁止事项

| 禁止 | 说明 |
|---|---|
| 明文写入 config.json / providers.json | 一律占位符 |
| 写入日志、异常消息、堆栈 | 见 3 章脱敏 |
| 写入 URL query | 校验时阻断 |
| 写入崩溃转储 / 诊断包 | 强制剔除 |
| 通过剪贴板复制 Key | 不提供该功能 |
| 通过 URL scheme / IPC 暴露 Key | 不实现 |

---

## 3. 日志脱敏

### 3.1 过滤规则（logging.Filter 全局挂载）

| 规则 | 处理 |
|---|---|
| 形如 sk- 开头的连续字符串 | 替换为 sk-**** |
| 连续 ≥ 32 字符且熵 > 4.0 bit/char | 替换为 ***REDACTED*** |
| Header 名包含 Authorization / x-api-key / api-key / token | 值整体替换为 [REDACTED] |
| JSON 字段名为 api_key / apiKey / access_token / secret | 值替换为 [REDACTED] |
| 请求体 | 只记长度 + sha256 前 12 位 |
| 响应体 | 记前 2000 字符，再套上述规则 |

### 3.2 日志配置

| 项 | 值 |
|---|---|
| 默认级别 | INFO（可配置 DEBUG / WARNING / ERROR） |
| 滚动 | 单文件 1 MB，保留 5 份 |
| 编码 | UTF-8 |
| 敏感信息 | 由 Filter 拦截，任何级别都不输出 |
| 崩溃 | 记录堆栈（脱敏后）+ 触发诊断提示 |

---

## 4. 传输安全

| 项 | 要求 |
|---|---|
| 协议 | 仅允许 https（localhost / 127.0.0.1 / .local 例外，用于本地 Ollama / LM Studio） |
| 明文 http | 默认禁止；仅在用户显式勾选「允许非加密连接（仅本地测试）」时放开，并在配置中标注风险 |
| 证书校验 | **必须开启**，禁止关闭 verify=False |
| 自签名证书 | 不允许（避免供应链绕过）；本地网关请用反向代理配证书或走 localhost 例外 |
| 超时 | 连接 15 s / 读取可配置，默认 120 s |
| 重定向 | 允许，但跳转后重新校验协议与证书；最多 3 次 |
| TLS 版本 | 依赖库默认（TLS 1.2+） |

---

## 5. 诊断包脱敏

诊断包用于报障，**必须默认安全**：

| 包含 | 说明 |
|---|---|
| 日志（脱敏） | logs/*.log |
| 配置（脱敏） | config.json（原文）、providers.json（api_key 字段替换为 __redacted__） |
| 环境信息 | 平台、架构、Python 版本、依赖版本、PySide6 版本、faster-whisper 版本 |
| 系统信息 | 操作系统版本、CPU 型号、内存大小、可用磁盘 |
| 应用版本 | SemVer + Git commit |

| 明确排除 | 原因 |
|---|---|
| meetings/ 全部内容 | 用户数据 |
| models/ | 体积过大 |
| vault.enc | 密钥 |
| 任何含真实 Key 的字符串 | 再次全量正则扫描一遍 |

生成流程：打包 → 全量正则复检（若命中疑似 Key 则中止并提示）→ 输出 zip。

---

## 6. 本地文件权限

| 平台 | 要求 |
|---|---|
| macOS | 数据目录 0700；vault.enc 0600；不使用 group / other 权限 |
| Windows | 目录 ACL 仅当前用户；vault.enc 仅当前用户可读 |
| Linux | 0700 / 0600，遵循 umask |

- 启动时检查数据目录权限；若为过宽（如 0777）→ 尝试修正并在 UI 提示。
- 会议目录不支持软链接指向外部（防路径穿越）。

---

## 7. 依赖与供应链安全

| 措施 | 说明 |
|---|---|
| 包源 | 仅 PyPI 官方；禁用第三方镜像 |
| 漏洞扫描 | CI 每 commit 跑 pip-audit；high / critical 阻断发布 |
| 版本锁定 | requirements.lock 由 pip-compile 生成并入库 |
| 哈希校验 | v1.1 后启用 --require-hashes |
| 二进制依赖 | 对 ctranslate2 / onnxruntime / cryptography / PyAV 记录版本与来源 |
| 许可证 | 全部依赖须为宽松许可证（BSD / MIT / Apache-2.0）；GPL 系禁止（避免传染） |
| 提交扫描 | CI 跑 gitleaks / detect-secrets，命中即失败 |

### 7.1 许可证注意（与打包强相关）

| 依赖 | 许可证 | 说明 |
|---|---|---|
| PySide6 | LGPL-3.0 | **动态链接 + 提供替换库入口**，不违反；不得静态链接后不开放插件机制 |
| faster-whisper / ctranslate2 | MIT / Apache-2.0 | 可自由分发 |
| 模型权重 | 各模型自有许可 | **必须逐模型核对**；部分模型禁止商用，需在用户界面标注 |
| 字体 / 图标 | 需 MIT / OFL / CC-BY | 见 09 章 |

> **模型许可是发布前必查项**：打包发布前须生成「模型许可清单」并在应用内「关于」页可查。

---

## 8. 隐私与合规

| 项 | 说明 |
|---|---|
| 录音同意 | 首次录音时若系统需要授权则触发系统权限；不额外弹窗（避免重复打扰） |
| 用户数据外发 | 唯一外发场景：用户主动点击「生成纪要」，内容为 Prompt 文本 |
| 明确告知 | 首次使用纪要功能时提示「将把转写文本发送到 {服务商名}」，并显示服务商名称与 Base URL |
| 遥测 | **默认关闭**；不采集任何用户内容；仅可选上报匿名崩溃计数 |
| 应用内说明 | 「关于 / 隐私」页说明数据存储位置与删除方式 |
| 删除 | 会议删除进回收站，30 天后真实删除；提供「永久删除全部数据」入口 |
| 数据导出 | 支持一键导出全部会议数据（zip），便于用户迁移与行使删除权 |

---

## 9. 异常与崩溃安全

1. 未捕获异常由全局 excepthook 处理：脱敏 → 记日志 → 中文提示「发生未预期错误，建议导出诊断信息」。
2. 异常消息**不得**包含请求体、Key、完整 URL query。
3. HTTP 客户端自定义异常类时覆写 __str__，只输出状态码与错误类型。
4. 第三方库异常（openai / anthropic SDK）需包装为内部异常后再向上抛。

---

## 10. 安全测试清单（CI 必跑）

| # | 检查 | 方式 |
|---|---|---|
| S1 | 仓库无明文 Key | gitleaks / detect-secrets 零命中 |
| S2 | 日志不含 Key | 单测：注入含 Key 的日志调用，断言输出被脱敏 |
| S3 | 诊断包不含 Key | 单测：构造含 Key 的配置，导出诊断包，全量扫描断言无命中 |
| S4 | providers.json 无真实 Key | 单测：保存服务商后读文件断言为占位符 |
| S5 | 明文 http 被拒绝 | 单测：base_url 为 http 时校验失败（除 localhost 例外） |
| S6 | 证书校验未被关闭 | 代码扫描：禁止出现 verify=False / check_hostname=False |
| S7 | 密钥库降级路径可用 | 单测：mock keyring 失败，验证 AES-GCM 加解密往返 |
| S8 | 模型权重许可核对 | 发布前人工 + 清单文件存在性检查 |
| S9 | 依赖漏洞 | pip-audit 无 high / critical |
| S10 | 文件权限 | 单测：创建 vault.enc 后断言 mode 为 0600 |

---

## 11. 相关文档

- [06 · AI 服务商集成契约](06-ai-providers.md)
- [07 · 数据模型与持久化](07-data-model.md)
- [10 · 打包 · CI · 完整性校验](10-packaging-ci-signing.md)
- [11 · 测试策略](11-testing.md)

