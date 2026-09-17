# 03 · 技术栈与依赖清单

> 版本基线均为 2026-09 核对的可用版本。安装时建议使用区间约束（>=x.y,<x+1）以保证兼容。

---

## 1. 运行环境

| 项 | 要求 | 说明 |
|---|---|---|
| Python | 3.11.x（3.11.9 已验证；faster-whisper 要求 >=3.9） | 3.12 暂不纳入，避免 sounddevice / PyInstaller 兼容波动 |
| macOS | 12.0 Monterey 及以上（Apple Silicon + Intel） | PySide6 6.11 要求 macOS 11+，提高门槛以保证签名与公证稳定 |
| Windows | 10 21H2 / 11，x64 | 在 GitHub windows-latest runner 上构建 |
| CPU | x86_64 或 arm64 | ASR 走 CTranslate2，纯 CPU 即可 |
| GPU | 非必需 | 有 CUDA 可选（ctranslate2 cuda build），v1.0 不做 |
| 磁盘 | 安装包约 350–550 MB；small 模型约 480 MB | 模型下载到用户数据目录，不占安装空间 |

**本机开发环境实测（可行性验证）**

| 组件 | 版本 |
|---|---|
| Python 3.11.9 / 3.11.15 | 可用 |
| PySide6 6.11.0（发布基线 6.11.2） | 可用 |
| openai 2.36.0 | 可用 |
| cryptography 46.0.5 | 可用 |
| PyInstaller 6.19.0 | 可用 |
| pytest 9.0.2 | 可用 |
| platformdirs 4.9.4 / keyring 25.7.0 | 可用 |
| faster-whisper 1.2.1 / anthropic 1.6.0 / sounddevice 0.5.6 / pytest-qt / pypinyin 0.55.0 / rapidfuzz 3.14.6 | 待安装（声明为依赖） |

---

## 2. 运行时依赖（requirements.txt）

| 依赖 | 版本基线 | 用途 | 打包注意 |
|---|---|---|---|
| PySide6 | >=6.11,<7 | 原生 UI（Qt for Python） | PyInstaller 自动收集 Qt 插件；需显式收 Qt plugins/platforms |
| faster-whisper | >=1.2,<2 | 本地 ASR（CTranslate2） | 传递依赖 ctranslate2、tokenizers、onnxruntime、av、tqdm |
| av (PyAV) | 随 faster-whisper | 音频解码（导入 + 转写输入） | wheel 自带 ffmpeg 动态库，必须 collect_dynamic_libs |
| sounddevice | >=0.5.6,<0.6 | 麦克风实时采集（PortAudio） | wheel 内嵌 portaudio-binaries；Windows 需确认 DLL 路径 |
| numpy | >=1.26,<3 | 音频 buffer 与相似度计算 | 随 ctranslate2 固定，勿单独降级 |
| openai | >=2,<3 | OpenAI 兼容协议客户端 | 纯 Python，无二进制 |
| anthropic | >=1,<2 | Anthropic 原生协议客户端 | 纯 Python，无二进制 |
| cryptography | >=43 | AES-256-GCM / scrypt 密钥加密 | 含 Rust 扩展二进制，必须 collect_dynamic_libs |
| keyring | >=25 | OS 钥匙串（Keychain / Credential Manager） | 纯 Python；Windows 依赖 pywin32（keyring 按需导入） |
| rapidfuzz | >=3.14,<4 | 编辑距离 / 相似度（关键词纠错） | 含 C++ 扩展 |
| pypinyin | >=0.55,<1 | 中文拼音相似度（关键词纠错） | 纯 Python + 数据文件，需 collect_data_files |
| jieba | >=0.42,<1 | 中文分词（纠错候选切分） | 需 collect_data_files（词典） |
| platformdirs | >=4 | 跨平台目录解析 | 纯 Python |
| packaging | >=24 | SemVer 与版本比较 | 纯 Python |

### 2.1 关键传递依赖（不可忽略）

| 传递依赖 | 来源 | 打包风险 |
|---|---|---|
| ctranslate2 | faster-whisper | 大体积二进制（约 300 MB+ 含 kernels），必须显式收集 |
| tokenizers | faster-whisper | Rust 编译扩展 |
| onnxruntime | faster-whisper | Silero VAD 推理；含 onnxruntime_pybind11_state 动态库 |
| pydantic | openai / anthropic | pydantic v2（Rust 核心），需随包收集 |
| httpx / httpcore / anyio | openai / anthropic | 纯 Python，注意 anyio 后端 |
| PyAV（av） | faster-whisper | ffmpeg 库，mac / Win 由 wheel 内置 |

> **打包强制项**：spec 必须对 faster_whisper、ctranslate2、tokenizers、onnxruntime、av、cryptography、rapidfuzz、pypinyin、jieba 执行 collect_all，构建后跑冒烟测试（导入 + tiny 模型转写 3 秒音频），否则视为构建失败。

### 2.2 已实测的 API 陷阱（实现时必须遵守）

以下均为**本机实测**得出的行为，不是文档推断。违反会导致运行时崩溃或结果错误。

| # | 陷阱 | 正确写法 | 实测版本 |
|---|---|---|---|
| T1 | **`WhisperModel.transcribe()` 返回 2 元组** `(segments 生成器, info)`，不是纯生成器。直接 `list(result)` 会得到 `[generator, info]`，遍历时报 `AttributeError: 'generator' object has no attribute 'text'` | `segs = result[0] if isinstance(result, tuple) else result` 再 `list(segs)`；同时兼容旧版返回生成器的分支 | faster-whisper 1.2.1 |
| T2 | `initial_prompt` 参数类型为 `Optional[Union[str, Iterable[int]]]`，**master 分支没有 `hot_words` 参数**（相关 PR 未合并） | 关键词只能通过 `initial_prompt` 注入自然语句，不能传列表 | faster-whisper 1.2.1 |
| T3 | `segment.words` 是**生成器**，不是列表；每次遍历都会重新迭代，二次访问为空 | 需要词级数据时立即 `list(segment.words)` | faster-whisper 1.2.1 |
| T4 | `segment.words[i].probability` 可能为 `None` | 门控计算时按 0.5 兜底，不阻断 | faster-whisper 1.2.1 |

**T1 的实测证据**（原型脚本首次运行时暴露）：

```text
type(transcribe()) = tuple
isgenerator        = False
len(r)             = 2          ← 元组，不是生成器
type(list)         = list count = 2
type(seg[0])       = generator  ← 第一个元素才是 segments 生成器
AttributeError: 'generator' object has no attribute 'text'
```

**这条会同时打穿原型和正式实现**，因此 asr.engine 模块必须封装为单一入口 `transcribe_to_segments()`，业务代码不得直接调用 `model.transcribe()`，避免各处重复踩坑。



---

## 3. 开发依赖（requirements-dev.txt）

| 依赖 | 用途 |
|---|---|
| pytest | 单元测试框架 |
| pytest-cov | 覆盖率，CI 强制 70% 门 |
| pytest-qt | UI 测试（配合 QT_QPA_PLATFORM=offscreen） |
| pytest-xdist | 并行测试 |
| pytest-timeout | 防止集成测试挂死 |
| ruff | lint + format（替代 flake8 / black / isort） |
| mypy | 业务逻辑层静态类型检查 |
| responses 或 respx | 网络 Mock（AI 请求构造测试） |
| gitleaks 或 detect-secrets | 密钥扫描（CI 强制） |
| pip-audit | 依赖漏洞扫描 |
| bandit | 安全静态扫描（可选） |

---

## 4. ASR 模型选择、准确率与许可

> 选型约束（用户明确要求）：**开源许可宽松 + 中文识别准确率高**，且**必须支持热词偏置机制**。

### 4.1 引擎选择：为什么必须是 Whisper 系列

| 候选引擎 | 中文准确率 | 热词机制 | 许可 | 结论 |
|---|---|---|---|---|
| **faster-whisper（Whisper）** | 高（large-v3 级） | ✅ initial_prompt 词法偏置 | MIT | **✅ 采用** |
| SenseVoice（FunASR） | 高（中文场景可能略优） | ❌ 无 initial_prompt 等价机制 | Apache-2.0 | ❌ 主引擎不可用 |
| Paraformer（FunASR） | 中高 | ❌ 无 | MIT | ❌ 主引擎不可用 |
| Whisper.cpp | 同 Whisper 权重 | ⚠️ 有 prompt 参数但功能受限 | GPL-3.0（含部分代码） | ❌ 许可证风险 + 功能弱 |
| openai-whisper（torch 版） | 同 faster-whisper | ✅ | MIT | ❌ 依赖 PyTorch，体积数倍、速度约慢 4 倍 |
| 云端 ASR | 高 | 各厂商不等 | 商业 | ❌ 违反离线硬约束 C3 |

**关键判断**：热词是本项目的第一差异化能力，而**只有 Whisper 提供 initial_prompt 词法偏置**。SenseVoice 在中文准确率上有优势，但没有等价机制，选它等于放弃热词能力 —— 因此**不作为主引擎**，可作为 v2.x 的可选引擎（明确标注「不支持热词」）。

### 4.2 模型清单与许可

| 模型 | 参数量 | int8 体积 | 中文定位 | 许可 | 是否可商用 |
|---|---|---|---|---|---|
| tiny | 39 M | ~75 MB | 草稿 | MIT | ✅ |
| base | 74 M | ~145 MB | 轻量 | MIT | ✅ |
| **small** | 244 M | ~480 MB | 入门 | MIT | ✅ |
| **large-v3-turbo** | 809 M | ~1.6 GB | **默认**：质量接近 large-v3，速度约为其 8 倍 | MIT | ✅ |
| **large-v3** | 1550 M | ~3 GB | 最高质量 | MIT | ✅ |

- 全部为 OpenAI 官方发布的 Whisper 权重，**MIT 许可，明确允许商用、修改与再分发**，无需署名以外的义务。
- faster-whisper 通过 CTranslate2 加载这些权重，运行时行为等价。
- **发布前必须二次核对**：从 HuggingFace 模型卡读取 license 字段并写入「模型许可清单」，随应用内「关于」页展示（见 08 章 §7.1）。本次编写时 HF API 在本环境不可达（HTTP 000），故许可结论依据 OpenAI 官方发布记录，**不作为最终凭证**。

### 4.3 默认模型：large-v3-turbo

选它而不是 small 或 large-v3，理由：

| 维度 | small | **large-v3-turbo** | large-v3 |
|---|---|---|---|
| 中文准确率 | 中 | 高 | 最高 |
| CPU 吞吐 | ~0.5–1× 实时 | ~0.5–1× 实时 | ~0.1× 实时 |
| 热词偏置响应 | 一般 | 好（beam=10 重解码收益明显） | 好但极慢 |
| 下载体积 | ~480 MB | ~1.6 GB | ~3 GB |
| 内存 | ~1.5 GB | ~2.5 GB | ~6 GB |

**核心权衡**：热词方案（05 章）依赖 Stage 3 用 beam_size=10 对候选区域重解码。小模型在 beam=10 下对偏置的响应弱、logprob 区分度低，会导致 D2「质量不劣于基线」判定大量失败，热词收益被吃掉。large-v3-turbo 在保持可用的 CPU 速度的同时提供了足够的解码质量区分度。

### 4.4 模型分层策略

| 档位 | 模型 | 触发场景 |
|---|---|---|
| 默认 | large-v3-turbo | 用户首次运行自动下载 |
| 最高质量 | large-v3 | 用户手动切换；正式纪要、长会议 |
| 快速 | small | 用户手动切换；低配机器 |
| 草稿 | base / tiny | 仅开发调试与 CI 测试 |

### 4.5 性能预期（规划值，M3 必须实测回填）

| 模型 | macOS arm64 预期吞吐 | 内存 |
|---|---|---|
| tiny | ~4× 实时 | ~250 MB |
| base | ~2.5× 实时 | ~350 MB |
| small | ~0.5–1× 实时 | ~1.5 GB |
| large-v3-turbo | ~0.5–1× 实时 | ~2.5 GB |
| large-v3 | ~0.1× 实时 | ~6 GB |

包含 Stage 3 重解码（约 10% 额外音频）后，总耗时约为上表的 1.10 倍。

---

## 5. 已否决方案对比

| 方案 | 否决理由 | 违反约束 |
|---|---|---|
| Electron | Web 渲染，内存占用高，空壳即 150 MB+ | C1 / C2 |
| Tauri | 依赖 WebView（WKWebView / WebView2），仍属 Web 方案 | C1 / C2 |
| pywebview | 同上，且 PyInstaller 打包极不稳定 | C1 / C2 |
| QWebEngineView（原生壳 + Web UI） | 本质仍是 WebView | C1 / C2 |
| Go + Fyne | ASR / AI 生态远弱于 Python，迭代效率低 | — |
| C# + Avalonia | 生态与 Agent 生成质量不如 Python；跨平台 ASR 绑定成本高 | — |
| Rust + Slint | 迭代成本高，产出效率低 | — |
| .NET MAUI | macOS 支持受限，不符合双平台统一 | C2 |
| Dear PyGui / Kivy | 桌面专业感与可访问性不足，控件体系不完整 | C2（质量） |
| openai-whisper（torch 版） | 依赖 PyTorch，体积与内存数倍，速度约慢 4 倍 | — |
| 云端 ASR（各云厂商 / OpenAI whisper API） | 违反离线硬约束，引入合规风险 | C3 |

---

## 6. 构建工具链

| 用途 | 工具 | 平台 |
|---|---|---|
| Python 包构建 | PyInstaller 6.x + .spec | macOS / Windows |
| 交付形态 | PyInstaller one-folder 产出 .exe（**不做安装包**，用户明确要求） | Windows |
| dmg 制作 | hdiutil（macOS 自带）+ create-dmg | macOS |
| 代码签名 | codesign + xcrun notarytool + xcrun stapler | macOS |
| 代码签名 | signtool sign /fd SHA256 /f *.pfx | Windows |
| CI | GitHub Actions（matrix） | — |
| 版本管理 | SemVer + Git Tag（v1.2.0 触发发布构建） | — |

---

## 7. 依赖安全策略

1. **锁文件**：提交 requirements.txt（区间约束）+ requirements.lock（pip-compile 精确版本），CI 用锁文件构建。
2. **漏洞扫描**：CI 跑 pip-audit，high / critical 阻断发布。
3. **供应链**：仅使用 PyPI 官方源；--require-hashes 于 v1.1 后启用。
4. **体积监控**：CI 记录安装包体积，回退 > 10% 告警。

---

## 8. 相关文档

- [02 · 架构设计](02-architecture.md)
- [10 · 打包 · CI · 完整性校验](10-packaging-ci-signing.md)
