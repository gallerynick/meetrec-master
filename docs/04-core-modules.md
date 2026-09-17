# 04 · 核心模块规格

> 本文定义各模块的**数据契约、公开接口与行为约束**。具体类实现由执行 Agent 规划，但不得改变契约。

---

## 1. 通用约定

- 所有时间戳使用 **ISO 8601 UTC 字符串**（形如 2026-09-16T11:20:33Z）落盘，UI 按系统时区显示。
- 所有音频时长、偏移量使用**秒（float64）**，不使用帧数。
- 所有 ID 使用 **UUIDv4 字符串**（会议、服务商、关键词组、纠错条目）。
- 所有文件大小单位为 **字节（int）**。
- 所有公开函数必须有类型注解与 docstring；跨层数据结构用 frozen dataclass。

---

## 2. audio.recorder — 麦克风实时录音

### 2.1 数据契约

```python
@dataclass(frozen=True)
class RecorderConfig:
    device_index: int | None  # None = 系统默认输入设备
    sample_rate: int = 16000
    channels: int = 1
    dtype: str = "float32"  # 输出统一 float32
    block_size: int = 4096  # 每块采样数（约 256 ms）
    input_format: str = "wav"  # 固定 wav（无损，ASR 直读）
```

### 2.2 状态机

```text
        start()            pause()            resume()           stop()
  idle ─────────▶ recording ─────────▶ paused ─────────▶ recording ─────────▶ stopped
    ▲                │                                              │
    └────────────────┴──────────────────────────────────────────────┘
                     (录音时长 = 0 时 stop() 直接回 idle 并报空录音错误)
```

### 2.3 行为约束

| 约束 | 说明 |
|---|---|
| 权限请求 | 首次录音必须在 UI 线程触发系统权限（macOS 需配置 Info.plist 的麦克风用途描述，否则系统直接拒绝） |
| 暂停实现 | 停止 InputStream，保留已写 buffer；resume 时重新打开并以追加模式续写 |
| 电平表 | 每块计算 RMS 并映射 dBFS（-60 到 0）→ 信号回 UI，更新频率降到 20 Hz |
| 输出文件 | 写入会议目录 audio/recording.wav；元数据含设备名、采样率、总时长 |
| 空录音 | 总时长 < 1 秒 → 抛 EmptyRecordingError（录音时间过短，请至少录制 1 秒） |
| 设备异常 | 中途拔出麦克风 → 捕获 PortAudio 异常，映射为 AudioDeviceLostError，自动停止并提示 |
| 退出保护 | 关闭窗口时若仍在录音 → 提示「录音仍在进行，确定退出？」 |

---

## 3. audio.importer — 音频导入

### 3.1 支持格式

| 格式 | 扩展名 | 解码器 | 备注 |
|---|---|---|---|
| WAV | .wav | PyAV | 无损，录音输出格式 |
| MP3 | .mp3 | PyAV (ffmpeg) | 常见录音导出格式 |
| M4A / AAC | .m4a / .aac | PyAV | 手机录音常见 |
| FLAC | .flac | PyAV | 无损 |
| OGG | .ogg | PyAV | 降级支持（非必需） |

不支持的格式 → 抛 UnsupportedAudioFormatError，中文提示列出支持的扩展名。

### 3.2 导入行为

| 约束 | 说明 |
|---|---|
| 不改动原文件 | 导入后**复制**一份到会议目录 audio/，保留原文件名（重名追加 -1） |
| 统一转码 | 复制后生成 audio/decoded.wav（16 kHz / mono / pcm_s16le）供 ASR 使用；原文件保留 |
| 大文件 | > 2 GB 拒绝导入（音频文件过大，请分段导入） |
| 加密 / 损坏 | 解码失败抛 AudioDecodeError（音频文件无法解码，可能已损坏或受保护） |
| 超长音频 | > 4 小时建议分块转写；UI 提示但不阻断 |
| 校验 | 记录 sha256 与时长到 meta.json，用于「换模型重跑」时判断是否需重新解码 |

---

## 4. asr.engine — 本地转写引擎

### 4.1 数据契约

```python
@dataclass(frozen=True)
class AsrParams:
    model_size: str = "large-v3-turbo"  # tiny/base/small/large-v3-turbo/large-v3
    language: str = "zh"  # zh / en，显式指定避免语言检测
    device: str = "cpu"  # cpu / cuda
    compute_type: str = "int8"  # int8 / float16 / float32
    beam_size: int = 5  # Stage 3 定向重解码时提高到 10
    best_of: int = 5
    temperature: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    vad_filter: bool = True  # Stage 3 短片段重解码时改为 False
    word_timestamps: bool = True  # 纠错需要词级概率
    initial_prompt: str | None = None
    initial_prompt_tokens: int = 0  # 注入预算统计
    condition_on_previous_text: bool = True  # Stage 3 短片段重解码时改为 False


@dataclass(frozen=True)
class AsrSegment:
    id: int
    start: float
    end: float
    text: str
    avg_logprob: float
    no_speech_prob: float
    words: tuple[AsrWord, ...]


@dataclass(frozen=True)
class AsrWord:
    start: float
    end: float
    word: str
    probability: float | None  # 纠错门控用
```

### 4.2 引擎约束

| 约束 | 说明 |
|---|---|
| 模型加载 | 用 WhisperModel(size, device=..., compute_type=..., download_root=MODEL_DIR) 加载；实例常驻，切换模型时释放旧实例 |
| 模型缓存 | 首次使用自动下载到 models/{size}/，带进度回调与取消；下载后校验 sha256 |
| 断网保护 | 模型已缓存时以 local_files_only=True 加载，绝不尝试联网（保证完全离线） |
| 模型缺失 | 未缓存且断网 → AsrModelMissingError（模型尚未下载且当前无网络） |
| 转写调用 | 以 AsrParams 展开为 transcribe 关键字参数，audio 为 numpy float32 数组 |
| 双模式调用 | **baseline()**：initial_prompt=None，跑完整音频，产出零污染基线；**redecode(clip)**：对短片段注入分组关键词 + beam_size=10 + condition_on_previous_text=False + vad_filter=False。两者共用同一模型实例 |
| 片段抽取 | Stage 3 按候选区域切 numpy 数组，±3 秒上下文扩展，音频起止边界截断不补零 |
| 进度回调 | 按已处理时长 / 总时长上报 0–100%，至少每 500 ms 一次 |
| 分块 | 音频 > 30 分钟时按 10 分钟 + 2 秒重叠分块，块间文本去重拼接 |
| 取消 | 提供取消令牌；取消后清理临时文件，返回 TaskCancelled |
| 显式语言 | 必须传 language，不依赖自动检测（降低中英混读误判与耗时） |
| VAD | 默认 vad_filter=True（Silero）过滤静音；连续静音 > 2 分钟提示用户 |

### 4.3 模型参数与预期性能（实测后回填）

| 模型 | 体积（int8） | 内存 | macOS arm64 预期吞吐 | 适用 |
|---|---|---|---|---|
| tiny | ~75 MB | ~250 MB | ~4× 实时 | 快速草稿 |
| base | ~145 MB | ~350 MB | ~2.5× 实时 | 一般会议 |
| small | ~480 MB | ~1.5 GB | ~0.5–1× 实时 | 快速档（低配机器） |
| **large-v3-turbo（默认）** | ~1.6 GB | ~2.5 GB | ~0.5–1× 实时 | **默认**：质量接近 large-v3，速度约为其 8 倍 |
| large-v3 | ~3 GB | ~6 GB | ~0.1× 实时 | 最高准确率；正式纪要 |

> 上表为规划值，M3 里程碑必须实测并回填本文档。许可信息见 [03 章 §4](03-tech-stack.md)（Whisper 全系列 MIT）。
> 含 Stage 3 重解码（约 10% 额外音频）后，总耗时约为上表的 1.10 倍。

## 5. keywords.store — 关键词库

### 5.1 数据契约

```python
@dataclass
class Keyword:
    id: str
    text: str  # 关键词正文（人名 / 产品名 / 术语）
    aliases: tuple[str, ...] = ()  # 已知错误写法，如（"章一鸣","张一明"）；精确匹配优先
    group_id: str | None = None
    priority: int = 50  # 1–100，用于 prompt 分组注入排序
    enabled: bool = True
    note: str = ""
    hit_count: int = 0  # 近 10 次会议命中统计（命中率反馈闭环）
    alias_hit_count: int = 0
    revert_count: int = 0  # 被用户撤销次数


@dataclass
class KeywordGroup:
    id: str
    name: str  # 如「产品名」「人名」「术语」
    color: str = "#4A90D9"  # UI 区分色
    enabled: bool = True
```

### 5.2 约束

| 约束 | 说明 |
|---|---|
| 规模上限 | 单库 ≤ 500 条；单组 ≤ 200 条。超量时 UI 告警（prompt 预算见 05 章） |
| 去重 | 同库内不区分大小写去重；中文按原文精确去重 |
| 非法字符 | 不得包含换行与首尾空白；长度 1–30 字符 |
| 导入 / 导出 | JSON：{"version":1,"groups":[...],"keywords":[...]}；导入时校验并告警未知字段 |
| 分组启停 | 组禁用 = 其下所有关键词不参与 prompt 与纠错；分组顺序参与 Stage 3 分组注入排序 |
| 预设 | 首次运行提供示例关键词库（约 50 条，覆盖人名 / 产品名 / 术语），便于理解与准确率测试 |
| 别名 | 每个关键词可登记多个已知错误写法；**库内唯一**（不得与其他关键词或别名冲突，冲突时阻断保存并指出冲突项）；长度 1–30 字符 |
| 别名匹配 | 精确匹配优先，置信度记 1.00，跳过所有相似度门控；英文别名默认大小写敏感，可配置忽略 |
| 不校正名单 | 可登记「不要自动改」的文本，Stage 4 直接跳过；同一 (关键词, 原文) 组合被撤销 2 次后自动建议加入 |
| 反馈闭环 | 统计每关键词命中 / 别名命中 / 撤销次数；连续 3 次会议未命中标记「疑似低召回」并提示添加别名，详见 05 章 §8 |

---

## 6. summary — AI 纪要生成

详见 [06 · AI 服务商集成契约](06-ai-providers.md)。本节只列纪要侧约束。

### 6.1 纪要输出章节（固定 5 节，顺序不变）

| 章节 | Markdown 标题 | 内容要求 |
|---|---|---|
| 会议概要 | `## 会议概要` | 3–5 句，说明会议主题、参与方、结论走向 |
| 关键讨论 | `## 关键讨论` | 要点列表，按讨论顺序 |
| 决定 | `## 决定` | 已达成结论，每条一句，避免模糊表述 |
| 行动项 | `## 行动项` | 表格：事项 / 负责人 / 截止时间（未知填「未定」） |
| 未决问题 | `## 未决问题` | 待定事项与阻塞点 |

### 6.2 纪要生成约束

| 约束 | 说明 |
|---|---|
| 输入上限 | 转写超过模型上下文时按段落分片 + 汇总（map-reduce），单片不超过模型窗口的 80% |
| 变量渲染 | `{transcript}` 转写全文（编辑后可重跑）、`{keywords}` 关键词清单、`{language}` 转写语言 |
| 未知变量 | 模板出现未定义变量 → 渲染前校验失败，中文提示并阻断 |
| 结构校验 | 结果必须包含 5 个章节标题；缺失时提示「AI 返回内容缺少必要章节」并支持重试 |
| 原文保留 | 每次生成保存原始返回文本，便于排查与手工整理 |
| 费用透明 | 显示本次请求 token 用量（服务商返回 usage 时） |
| 取消 | 生成中可取消（中断请求） |

---

## 7. prompts — Prompt 模板

### 7.1 默认模板（default-zh.md）

```markdown
你是一名专业的会议记录助手。请根据下面的会议转写内容，生成结构化的 Markdown 会议纪要。

## 要求
1. 严格按照「会议概要 / 关键讨论 / 决定 / 行动项 / 未决问题」五个章节输出，标题层级为 ##。
2. 只依据转写内容，不要编造未提及的信息；转写中没有的内容写「未提及」。
3. 行动项必须以 Markdown 表格输出，列为：事项 | 负责人 | 截止时间。
4. 语言为{language}，保持简洁，可直接作为正式纪要使用。

## 参考关键词（人名 / 产品名 / 术语，请保持写法一致）
{keywords}

## 会议转写
{transcript}
```

### 7.2 模板约束

| 约束 | 说明 |
|---|---|
| 变量白名单 | 仅 {transcript} / {keywords} / {language} |
| 模板数量 | 支持多套命名模板，可设为默认 |
| 校验 | 保存前校验变量合法性与模板非空 |
| 恢复默认 | 提供「恢复默认模板」入口 |
| 存储位置 | config/templates/{name}.md，不加密（模板不含密钥） |

---

## 8. export — 编辑与导出

### 8.1 导出矩阵

| 格式 | 仅纪要 | 仅转写 | 合集 |
|---|---|---|---|
| Markdown (.md) | 纪要正文 | 转写（含时间轴 + 关键词标记） | 会议信息 → 纪要 → 附录：转写 |
| TXT (.txt) | 纪要转纯文本（去 Markdown 标记） | 转写纯文本 | 同合集，纯文本分隔 |

### 8.2 约束

| 约束 | 说明 |
|---|---|
| 导出前编辑 | 纪要可编辑；「编辑后再总结」= 用编辑后的转写重新生成纪要 |
| 时间轴 | 转写导出包含 [mm:ss] 时间戳（词级聚合到句级） |
| 关键词标记 | 合集导出中关键词以 [K] 前缀标记，纠错位置标注（已校正） |
| 保存位置 | 默认上次导出目录；提供「打开所在目录」 |
| 覆盖 | 文件已存在时询问覆盖 / 另存 |
| 编码 | UTF-8，默认无 BOM；Windows 可开启 BOM 以兼容记事本 |

---

## 9. settings — 设置中心

| 分区 | 项 | 默认 |
|---|---|---|
| 通用 | 界面语言（中文 / English） | 中文 |
| 通用 | 主题（跟随系统 / 浅色 / 深色） | 跟随系统 |
| 通用 | 启动时自动检查新版本 | 开启 |
| ASR | 默认模型 | small |
| ASR | 默认语言 | 中文 |
| ASR | 计算类型 | int8 |
| ASR | 模型下载目录 | 应用数据目录/models |
| ASR | 启用 VAD 静音过滤 | 开启 |
| 关键词 | 关键词上限告警阈值 | 300 |
| 关键词 | 纠错强度（保守 / 平衡 / 激进） | 平衡 |
| 关键词 | 启用 initial_prompt 注入 | 开启 |
| 关键词 | 启用后处理纠错 | 开启 |
| AI | 默认服务商 | 用户首次配置 |
| AI | 默认 Temperature | 0.2 |
| AI | 默认 Max Tokens | 4096 |
| AI | 请求超时（秒） | 120 |
| AI | 最大重试次数 | 3 |
| 录音 | 输入设备 | 系统默认 |
| 录音 | 输出格式 | WAV |
| 数据 | 回收站保留天数 | 30 |
| 数据 | 日志级别 | INFO |

所有设置**立即生效**（无确定 / 取消按钮，遵循 macOS Preferences 与 Windows Settings 模式），写入 config.json。

---

## 10. library — 会议库

| 约束 | 说明 |
|---|---|
| 列表字段 | 标题、日期、时长、ASR 模型、服务商、纪要状态（未生成 / 已生成）、关键词数 |
| 检索 | 标题模糊搜索 + 日期范围过滤 |
| 排序 | 默认按更新时间倒序 |
| 删除 | 移入回收站；回收站可恢复 / 永久删除 |
| 打开 | 直接进入转写页，纪要页保留上次内容 |
| 重命名 | 支持，立即生效 |
| 容量提示 | 应用数据占用超 2 GB 时提示清理 |

---

## 11. i18n — 国际化

| 约束 | 说明 |
|---|---|
| 语言 | 中文（zh_CN，默认）、English（en_US） |
| 实现 | Qt .ts → .qm 编译产物随包分发；业务层错误文本走 i18n key，不硬编码中文 |
| 覆盖范围 | 全部 UI 文本、对话框、错误提示、日志级别名（日志正文为英文便于排查） |
| 切换 | 设置中切换后**立即生效**，无需重启 |
| 数字 / 时间 | 时间按系统区域格式；数字不本地化 |

---

## 12. errors — 错误类型与提示

| 异常 | 中文提示模板 | 可重试 |
|---|---|---|
| EmptyRecordingError | 录音时间过短（不足 1 秒），请重新录制 | 是 |
| AudioDeviceLostError | 麦克风设备已断开，请重新连接后再次录音 | 是 |
| MicPermissionDenied | 未获得麦克风权限。请在系统设置的隐私与安全中允许本应用访问麦克风 | 否（引导） |
| UnsupportedAudioFormatError | 不支持该音频格式，支持的格式为 WAV / MP3 / M4A / AAC / FLAC | 否 |
| AudioDecodeError | 音频文件无法解码，可能已损坏或受保护 | 否 |
| AsrModelMissingError | 语音识别模型尚未下载且当前无网络连接，请联网后重试 | 是 |
| AsrModelDownloadFailed | 模型下载失败：{reason}。请检查网络后重试 | 是 |
| KeywordPromptOverflowError | 关键词数量过多，超出识别上下文预算，请精简关键词库 | 否（引导） |
| ProviderAuthError | API Key 无效或已过期，请在设置中重新填写 | 否（引导） |
| ProviderRateLimitError | 服务商限流，请等待 {retry_after} 秒后重试 | 是（自动） |
| ProviderNetworkError | 无法连接到服务商：网络不可用或 Base URL 填写有误 | 是 |
| ProviderResponseError | 服务商返回内容无法解析，已保留原始文本，可手动整理 | 否 |
| ProviderSectionMissing | AI 返回内容缺少必要章节（{missing}），请更换模型或调整 Prompt 模板后重试 | 是 |
| StorageError | 保存失败：磁盘空间不足或目录不可写 | 否 |
| ExportError | 导出失败：{reason} | 否 |

---

## 13. 相关文档

- [05 · 关键词优先识别规格](05-keyword-correction.md)
- [06 · AI 服务商集成契约](06-ai-providers.md)
- [07 · 数据模型与持久化](07-data-model.md)
- [09 · UI 设计规范](09-ui-design-spec.md)

