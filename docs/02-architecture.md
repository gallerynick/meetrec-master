# 02 · 架构设计

---

## 1. 架构总览

分层 + 单向依赖：**UI 不触碰第三方 SDK，业务层不触碰 Qt**。

```text
┌────────────────────────────────────────────────────────────┐
│ L4  UI 层 (Qt)                                              │
│  main_window / views / dialogs / widgets / theme / i18n     │
│  只依赖 L3 的 Facade，通过信号-槽接收进度，不直接 await       │
└──────────────────────────┬─────────────────────────────────┘
                           │ 同步调用 Facade + 提交后台任务
┌──────────────────────────▼─────────────────────────────────┐
│ L3  业务编排层 (usecases)                                    │
│  record / transcribe / summarize / export / library /        │
│  settings                                                    │
└───┬───────────┬──────────────┬───────────────┬──────────────┘
    │           │              │               │
┌───▼───┐  ┌───▼───┐   ┌──────▼─────┐   ┌─────▼──────┐
│ L2-A  │  │ L2-B  │   │ L2-C       │   │ L2-D       │
│ audio │  │ asr   │   │ keywords   │   │ summary    │
│ 录音  │  │ 转写  │   │ 关键词库    │   │ AI 摘要    │
│ 导入  │  │ 模型  │   │ prompt 构造 │   │ 双协议适配  │
│ 探测  │  │ 分块  │   │ 后处理纠错  │   │ 重试/解析  │
└───┬───┘  └───┬───┘   └──────┬─────┘   └─────┬──────┘
    │          │              │                │
┌───▼──────────▼──────────────▼────────────────▼────────────┐
│ L1  基础设施层                                              │
│  storage(仓库+SQLite) · config · secrets(钥匙串) · log ·    │
│  errors(错误映射) · paths(目录解析) · diagnostics(诊断包)     │
└──────────────────────────────┬─────────────────────────────┘
                               │
        sounddevice · av(PyAV) · faster-whisper · openai · anthropic
        · cryptography · keyring · platformdirs · rapidfuzz · pypinyin
```

**分层规则（code review 强制）**

1. L4 → L3：允许。L4 不得 import L1 / L2。
2. L3 → L2 / L1：允许。L3 不 import PySide6。
3. L2 → L1：允许。L2 之间互不依赖（需要共享数据时通过 L3 编排）。
4. L1 不依赖上层任何模块。
5. 任何模块不得把 PySide6 类型带入业务逻辑（Qt 只在 L4）。
6. 所有跨层数据结构是纯 dataclass / TypedDict，不携带 Qt 类型。

---

## 2. 模块划分与职责

| 模块 | 职责 | 关键约束 |
|---|---|---|
| audio | 麦克风采集、设备探测、暂停 / 继续、音频导入解码、格式探测 | 输出统一为 16 kHz 单声道 float32 numpy 数组；解码失败抛 AudioDecodeError |
| asr | faster-whisper 封装、模型下载与缓存、长音频分块、进度回调 | 只返回数据（segments / words / confidence），不碰关键词 |
| keywords | 关键词库 CRUD、initial_prompt 构造、后处理纠错、纠错日志 | prompt 有 token 预算上限；纠错必须可撤销 |
| summary | 服务商配置模型、双协议适配、重试与限流、Markdown 章节解析 | 请求构造必须单测覆盖；不得写入密钥到日志 |
| storage | 会议项目仓库、SQLite 索引、Schema 迁移、诊断包 | 目录结构见 [07 · 数据模型](07-data-model.md) |
| config | 用户配置读写、界面语言、ASR 默认参数 | 配置不含密钥，密钥只存 ref |
| secrets | API Key 加解密、OS 钥匙串 / 降级加密文件 | 见 [08 · 安全规范](08-security.md) |
| errors | 异常类型定义 + 中文用户提示映射 | 所有 UI 可见错误都经此映射 |
| log | 结构化日志、轮转、脱敏过滤器 | 禁止打印 Key 与完整 Prompt |
| ui | 窗口、页面、对话框、控件、主题、i18n | 所有耗时操作走后台任务 |
| export | Markdown / TXT 导出，内容组合策略 | 导出内容不写回应用目录，由用户选路径 |
| usecases | 编排跨模块流程（转写流水线、纪要流水线） | 唯一能同时调用多个 L2 模块的地方 |

---

## 3. 目录结构（目标形态）

```text
Project_MeetRecMaster/
├── README.md
├── docs/                          # 本规范基线（01–12）
├── src/
│   └── meetrec/
│       ├── __main__.py            # python -m meetrec
│       ├── app.py                 # QApplication 引导、单实例锁、日志初始化
│       ├── paths.py               # platformdirs 目录解析
│       ├── config/
│       │   ├── store.py           # config.json 读写 + 迁移
│       │   └── schema.py          # 配置 dataclass
│       ├── secrets/
│       │   └── vault.py           # 钥匙串 / 降级加密
│       ├── storage/
│       │   ├── repository.py      # 会议项目仓库
│       │   ├── db.py              # SQLite 索引 + 迁移
│       │   └── diagnostics.py     # 诊断包
│       ├── usecases/
│       │   ├── record.py
│       │   ├── transcribe.py      # 转写 + 关键词 + 落盘
│       │   ├── summarize.py       # 纪要生成 + 落盘
│       │   └── export.py
│       ├── audio/
│       │   ├── recorder.py
│       │   ├── importer.py
│       │   └── probe.py
│       ├── asr/
│       │   ├── engine.py
│       │   ├── models.py          # 模型下载 / 缓存 / 校验
│       │   └── chunker.py
│       ├── keywords/
│       │   ├── store.py
│       │   ├── prompt_builder.py
│       │   └── corrector.py
│       ├── summary/
│       │   ├── types.py           # ProviderProfile 等
│       │   ├── client.py          # 统一重试 / 超时
│       │   ├── openai_compat.py
│       │   ├── anthropic_native.py
│       │   ├── prompts.py         # 模板渲染与校验
│       │   └── parser.py          # Markdown 章节解析
│       ├── errors.py
│       ├── log.py
│       ├── i18n.py
│       ├── resources/             # 图标、默认模板
│       │   ├── icons/
│       │   └── prompts/default-zh.md
│       └── ui/
│           ├── theme.py           # 设计令牌 + QSS + 明暗
│           ├── i18n/zh_CN.qm, en_US.qm
│           ├── main_window.py
│           ├── views/{library,capture,transcript,summary,export}_view.py
│           ├── dialogs/{settings,providers,keywords,prompt,export}_dialog.py
│           └── widgets/{recorder_bar,level_meter,transcript_editor,keyword_badge}.py
├── tests/
│   ├── unit/                      # 业务逻辑、请求构造、纠错、密钥
│   ├── integration/               # 协议、注入链路、导入转写（tiny 模型）
│   ├── ui/                        # pytest-qt，QT_QPA_PLATFORM=offscreen
│   ├── accuracy/                  # 关键词准确率评测
│   │   ├── ground_truth/*.json
│   │   ├── samples/*.wav
│   │   └── run_accuracy.py
│   └── fixtures/
├── build/
│   ├── pyinstaller/meetrec.spec
│   ├── resources/Info.plist, icon.icns, icon.ico
│   ├── entitlements.plist
│   ├── sign/macos_sign.sh, windows_sign.ps1
│   └── installer/                 # Windows 安装包脚本（见 10 章）
├── scripts/                       # 开发辅助脚本
├── .github/workflows/ci.yml, release.yml
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
└── UserGuide.md
```

---

## 4. 关键运行时流程

### 4.1 录音 → 转写 → 纪要（主链路）

```text
UI 录音页          Recorder            AudioWriter
   │ 点击录音          │                    │
   │──────────────────▶│ sounddevice.InputStream (16k/mono/f32)
   │                   │── 回调分块 ───────▶│ 追加写入临时 WAV
   │ 暂停              │ 状态机: idle→recording→paused→recording→stopped
   │ 停止              │                    │ 关闭文件，产出 audio_path
   │◀──────────────────┤ 录音完成信号        │
   ▼
UI 转写页          TranscribeUsecase              asr / keywords
   │ 点击转写          │                        │
   │──────────────────▶│ keywords.prompt_builder → initial_prompt
   │                   │───────────────────────▶│ asr.engine.transcribe(progress_cb)
   │ 进度条            │◀───────────────────────│ segments + words
   │                   │ keywords.corrector.correct(segments, keywords)
   │ 关键词高亮/纠错角标│ transcript_repo.save(...)
   │◀──────────────────│ 转写完成信号            │
   ▼
UI 纪要页          SummarizeUcase                 summary
   │ 点击生成          │ 模板渲染({transcript},{keywords},{language})
   │──────────────────▶│ client.call(provider, messages, 重试/超时)
   │ 生成中            │ parser.parse(markdown) → 校验 5 章节
   │◀──────────────────│ 完成信号（含原文 + 结构化章节）
   ▼
UI 导出页          ExportUcase
   │ 选择格式/内容 ───▶│ 写 Markdown / TXT 到用户选目录
```

### 4.2 线程与并发模型

| 场景 | 执行位置 | 说明 |
|---|---|---|
| 录音回调 | sounddevice 内部音频线程 | 只写 buffer，不做业务逻辑 |
| ASR 推理 | QThreadPool 后台线程（单任务占一线程） | 通过 Qt signal 回传进度，UI 线程永不阻塞 |
| AI 请求 | 同上 | timeout + 重试全部在后台完成 |
| 模型下载 | 同上 | 支持取消，取消时清理部分下载文件 |
| SQLite 写入 | 专用 storage 线程或写锁 | WAL 模式，短事务 |
| 文件导出 | 后台线程 | 大文件分块写入，进度可回调 |

**规则**：任何超过 200 ms 的操作一律后台执行；UI 线程只做布局与渲染。

---

## 5. 错误处理策略

1. 所有异常在 L1 / L2 抛为**业务异常类型**（AudioDecodeError、AsrModelMissingError、KeywordPromptOverflowError、ProviderAuthError、ProviderRateLimitError、ProviderNetworkError、ProviderResponseError、StorageError）。
2. errors.map_to_user_message(exc, i18n) 统一产出中文提示（中英双语由 i18n 决定），含「可重试 / 不可重试」标记。
3. UI 层捕获后展示 QMessageBox 或内联错误条（内联优先，模态只用于致命错误）。
4. 网络类错误支持「一键重试」按钮，重试最多 3 次指数退避（详见 [06](06-ai-providers.md)）。
5. 未捕获异常统一落到顶层 excepthook，记录日志并提示用户导出诊断包。

---

## 6. 架构决策记录（ADR）

### ADR-001 · UI 采用 PySide6，拒绝一切 Web 方案
- **状态**：Accepted
- **背景**：硬约束 C1 / C2 禁止 Electron / Tauri / Web / WebView。
- **决策**：使用 PySide6（Qt for Python）构建原生 UI，一套代码双平台。
- **备选**：Go + Fyne（ASR / AI 生态弱）、C# + Avalonia（Agent 迭代效率低）、Rust + Slint（迭代成本高）、.NET MAUI（macOS 受限）、Dear PyGui（桌面专业感不足）。
- **代价**：Qt 二进制体积较大；需要 QSS 定制主题；PyInstaller 需处理 Qt 插件目录。
- **明确禁用**：QWebEngineView 即便能跑原生壳，仍属于 WebView 方案，直接违反 C1。

### ADR-002 · 本地 ASR 采用 faster-whisper
- **状态**：Accepted
- **背景**：需完全离线（C3），且需要「关键词偏置」能力。
- **决策**：faster-whisper 1.2.x（CTranslate2 后端），**默认 large-v3-turbo 模型** + 中文。
- **模型许可**：Whisper 全系列（tiny/base/small/large-v3-turbo/large-v3）均为 OpenAI 官方发布的 **MIT 许可**，允许商用与再分发。详见 [03 章 §4](03-tech-stack.md)。
- **备选**：openai-whisper（torch 依赖大、速度慢约 4 倍）、transformers whisper（内存占用高）、本地 SenseVoice / Paraformer（生态与模型更新较慢）。
- **收益**：CPU 即可运行，CTranslate2 int8 量化下 small 模型吞吐满足 0.5× 实时目标。

### ADR-003 · 关键词方案 = 四阶段「基线锚定 + 定向重解码」
- **状态**：Accepted（v2.0，取代 v1.0 的「全局注入 + 后处理」两步方案）
- **依据**：
  1. 已核对 faster-whisper 源码（faster_whisper/transcribe.py），WhisperModel.transcribe() 的 initial_prompt 参数签名为 Optional[Union[str, Iterable[int]]]，接受文本串或 token id 列表，作为解码起点上下文注入；当前 master 分支**没有** hot_words 参数（相关 PR 未合并）。
  2. initial_prompt 是**词法偏置**：模型在歧义时倾向回落到 prompt 中已有的写法。但它是解码起点上下文，**对长音频中段的人名偏置会衰减**；且 prompt 越长副作用越明显。
  3. 实测经验（社区案例）：**把专有名词字典整段塞进 initial_prompt 是公认误用** —— 词表无上限、维护成本高、长 prompt 有副作用。
- **决策**：四阶段架构（详见 [05 章](05-keyword-correction.md)）：
  1. **Stage 1 全局基线转写**：**不注入热词**，为普通文本建立零污染锚点。
  2. **Stage 2 关键词缺口分析**：命中率统计 + 三路候选区域定位（低置信 / 疑似变体 / 称呼开场），候选音频总量 ≤ 基线的 15%。
  3. **Stage 3 定向重解码**：对候选区域抽取 ±3 秒音频，按**分组相关度**注入 initial_prompt，beam_size 提高到 10 重新转写，再用 D1–D5 规则与基线**择优合并**。
  4. **Stage 4 后处理纠错（兜底）**：别名**精确匹配**优先，其次拼音 + 编辑距离 + 词概率门控，所有替换可撤销。
- **为什么这样更好**：
  - **普通文本 WER 退化严格为 0**（架构性保证，不靠调阈值）：普通文本来自从未注入热词的基线。
  - **热词偏置更强而非更弱**：片段只有 10–30 秒时，initial_prompt 在解码上下文中的占比远高于整段 1 小时音频，偏置强度更高。
  - **成本可控**：总耗时 ≈ 基线 × 1.10，而非 ×2。
- **诚实约束**：initial_prompt 仍不能保证每个关键词都识别正确（Stage 3 的 D2/D3 规则会拒绝质量不达标或差异过大的重解码结果）。因此保留 Stage 4 兜底，并引入**别名表**把系统性同音错误变成确定性映射。
- **验收口径**：关键词召回率 ≥ 90% **且**普通文本 WER 退化 == 0，双条件同时满足。
- **备选**：自训练热词（需 GPU 与标注数据，超范围）；纯后处理（召回不足）；仅 initial_prompt 全局注入（副作用不可控，v1.0 方案，保留为对比组）；SenseVoice / Paraformer 引擎（无 initial_prompt 等价机制，热词能力不可用，故不作主引擎）。

### ADR-004 · AI 采用双协议适配层
- **状态**：Accepted
- **决策**：定义统一的 SummaryProvider 抽象，实现两个适配器：openai_compat（POST /chat/completions）与 anthropic_native（POST /v1/messages）。用户新增服务商只需填 Base URL + Key + 模型名。
- **理由**：OpenAI 兼容协议覆盖 OpenAI / DeepSeek / 通义 / 智谱 / Ollama / vLLM 等绝大多数；Anthropic 原生协议必须单独处理（system 单独字段、max_tokens 必填、anthropic-version header）。
- **代价**：需维护两套请求构造与错误码映射；用单测 + 契约测试约束。

### ADR-005 · 音频解码统一复用 PyAV
- **状态**：Accepted
- **理由**：faster-whisper 已依赖 av（PyAV），导入音频时直接用同一解码器转成 16 kHz mono float32，避免引入 soundfile / ffmpeg 子进程两套解码路径。
- **代价**：PyAV 需要打包其自带 ffmpeg 动态库（wheel 已内置，PyInstaller 需正确处理）。

### ADR-006 · SQLite 作会议库索引，内容以文件系统存放
- **状态**：Accepted
- **决策**：library.db（SQLite，WAL）只存会议索引与元数据；音频 / 转写 / 纪要按「会议项目目录」存放。
- **理由**：媒体与长文本不适合塞进数据库；文件系统便于用户直接备份与迁移，也便于诊断包打包。
- **代价**：需实现 Schema 版本迁移；文件与索引需一致性维护（删除会议时事务内标记，文件延迟清理）。

### ADR-007 · 密钥存储：OS 钥匙串优先，降级为本地加密文件
- **状态**：Accepted
- **决策**：优先使用 keyring（macOS Keychain / Windows Credential Manager / Linux Secret Service）；不可用时降级为 AES-256-GCM 加密文件，密钥由「机器指纹 + 随机盐」经 scrypt 派生，盐文件权限 0600。
- **理由**：钥匙串提供平台原生保护与用户可见管理；降级方案保证无钥匙串环境（部分 CI、精简 Windows）仍可用，同时不引入明文。
- **风险**：降级模式下机器克隆会带走密钥 —— 文档中明确告知，并提供「重置密钥」入口。

### ADR-008 · 后台任务统一走线程池 + 信号桥接
- **状态**：Accepted
- **决策**：ASR、AI 请求、模型下载、导出全部提交到 QThreadPool 派生的任务对象（QRunnable 或 threading.Thread + Qt signal 桥接），禁止在 UI 线程执行。
- **理由**：ASR 与网络请求均为长耗时操作，UI 线程阻塞会导致平台「无响应」提示（macOS 黄色光标 / Windows 应用未响应）。

### ADR-009 · ASR 模型不打包，首次运行按需下载
- **状态**：Accepted（v1.1 修订：强化应用内模型管理 UI）
- **决策**：安装包不含模型；应用内提供**模型管理界面**，用户自主选择与下载；模型存放在用户数据目录 `models/{size}/`，带完整性校验与断点续传。
- **应用内模型管理要求**（用户明确要求）：
  1. 设置 → ASR → 模型列表，逐行显示：模型名、体积、预估速度、质量定位、当前状态（已下载 / 未下载 / 下载中 X%）。
  2. 每行提供：下载、删除、设为默认 三个操作；删除已设为默认的模型时禁止并提示先切换。
  3. 首次启动若检测到无任何模型，弹出引导卡（非阻断），指向模型管理页。
  4. 支持用户手动放置模型目录（离线装机场景）：应用启动时扫描 `models/`，校验文件名与大小后识别为已安装。
- **理由**：small 约 480 MB、large-v3-turbo 约 1.6 GB、large-v3 约 3 GB，捆绑会使安装包难以分发、Gatekeeper 扫描变慢。
- **已否决**：捆绑 small 模型做「离线装机版」（用户决策）。理由：+480 MB 分发体积，且本项目不商用、不做离线装机场景。离线需求一律走手动放置模型目录（应用内模型管理要求第 4 条）。
- **代价**：首次使用有下载等待；必须提供进度、取消与失败重试。中国大陆网络需支持 `HF_ENDPOINT` 镜像配置（默认值 `https://hf-mirror.com`，可在设置中切换）。

### ADR-010 · 日志脱敏 + 诊断包导出
- **状态**：Accepted
- **决策**：日志默认 INFO，滚动 5 × 1 MB；全局过滤器拦截 API Key、Authorization header、Prompt 正文（仅保留长度与哈希前 8 位）；提供「导出诊断包」功能打包日志 + 环境 + 配置（脱敏）。
- **理由**：桌面应用无崩溃收集服务器；诊断包是唯一排障通道，必须默认安全。

### ADR-011 · Windows 交付形态 = 单目录 .exe，不做安装包
- **状态**：Accepted
- **决策**：Windows 仅交付 PyInstaller one-folder 产出的 .exe（+ 依赖目录），**不使用 Inno Setup / NSIS 做安装程序**。
- **理由**：用户明确要求「Windows 交付 exe 就行」。one-folder 免安装、解压即用、便于内部分发与升级覆盖。
- **代价与补偿**：
  - 无「开始菜单快捷方式 / 卸载入口」→ 文档中提供「创建桌面快捷方式」与「手动删除目录」说明；应用内「关于」页显示安装目录路径。
  - 无 per-machine 安装 → 全部按 per-user 设计（配置、模型、数据均在用户目录，见 07 章）。
  - 杀毒软件对未签名多文件目录的误报风险 → 见 ADR-012：本项目不签名，接受 SmartScreen 警告；分发给已知用户时提供 sha256 校验和自验。

### ADR-012 · 不启用商业签名与公证（C7 修订）
- **状态**：Accepted（修订硬约束 C7）
- **决策**：macOS 仅做 ad-hoc 自签名（`codesign --force --sign - --deep`），**不申请 Developer ID、不做公证**；Windows **完全不签名**，不提供 Authenticode 证书。
- **理由**：用户明确「不商用，证书最简化」。签名与公证的核心价值是为**向不特定的第三方分发**建立操作系统级信任链；本项目定位为自用 / 团队内部 / 开源免费分发，该信任链不构成必要成本。同时消除三类持续开销：Apple Developer Program 年费（$99/年）、Windows OV 证书年费（¥3000–8000/年）、证书到期轮换与维护。
- **实际效果**：

| 平台 | 用户首次打开时 | 处理方式 |
|---|---|---|
| macOS | Gatekeeper 提示「无法验证开发者」 | 右键 → 打开 → 打开，一次即可（后续不再提示） |
| Windows | SmartScreen 蓝色警告「已保护你的电脑」 | 更多信息 → 仍要运行 |

- **替代完整性保证**（取代签名校验）：
  1. CI 对每个发布产物计算 sha256，写入 `SHA256SUMS.txt` 并随 Release 分发。
  2. 用户在下载页核对校验和：macOS `shasum -a 256`，Windows `certutil -hashfile *.exe SHA256`。
  3. 版本元数据（版本号、git commit、构建时间）写入应用内「关于」页，便于追溯。
- **代价与已知风险**：
  - 每次把产物拷到一台新机器或新用户，都要走一次「右键打开」或「仍要运行」；分发给多人时沟通成本上升。
  - 部分企业 EDR / 杀毒软件可能对未签名 Python 打包产物主动拦截（不是 SmartScreen，而是直接删除）。遇到时只能申请白名单。
  - macOS ad-hoc 签名**不满足** hardened runtime 的完整要求；本项目不请求特殊系统权限（无辅助功能、无输入监控），因此不受影响。若未来需要申请辅助功能权限，必须改回 Developer ID 签名。
  - **模型许可不受影响**：Whisper 全系列 MIT 许可，不商用与商用均允许，见 03 章 §4。
- **重新启用条件**（触发任一条则回到完整签名流程）：
  1. 开始收费或接受捐赠并要求提供技术支持；
  2. 公开发布给不特定用户且下载量超过团队可人工支持的规模；
  3. 需要申请 macOS 辅助功能 / 输入监控等特权；
  4. 企业客户要求提供签名产物。
- **备选**：自签名证书（signtool 自签）—— 已否决。自签名不被任何信任链认可，反而会让 SmartScreen 判定更差，比完全不签更糟。



---

## 7. 技术风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| initial_prompt 对关键词的偏置效果不稳定 | 准确率不达标 | 双保险：后处理纠错；prompt token 预算内排序；评测脚本持续跟踪；提供「仅后处理」开关 |
| large-v3 模型在 CPU 上过慢 | 用户体验差 | 默认 small；进度与预计耗时提示；文档标注各模型实测吞吐 |
| PyInstaller 打包 faster-whisper / PyAV 二进制缺失 | 安装包无法运行 | spec 中显式 collect_all；两平台冒烟测试在 CI 必跑 |
| 不同 OpenAI 兼容服务商字段差异（max_tokens vs max_completion_tokens） | 请求失败 | 每服务商可配置字段开关，默认 max_tokens；错误映射给出可操作提示 |
| 钥匙串不可用 | 密钥无法安全存储 | ADR-007 降级方案 + 明确提示 |
| 关键词过多导致 prompt 溢出 | 识别质量下降 | token 预算上限 + 优先级排序 + 超量告警 |
| 用户误删会议 | 数据丢失 | 删除进入「回收站」目录，30 天后清理（可配置） |

---

## 8. 相关文档

- [03 · 技术栈与依赖清单](03-tech-stack.md)
- [04 · 核心模块规格](04-core-modules.md)
- [05 · 关键词优先识别规格](05-keyword-correction.md)
- [07 · 数据模型与持久化](07-data-model.md)
