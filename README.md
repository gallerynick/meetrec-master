# MeetRec Master — 会议纪要助手

> Python 3.11 + PySide6 + faster-whisper 构建的**非 Web、原生 UI、双平台**（macOS / Windows）会议纪要桌面软件。
> 本地离线语音识别 + **关键词优先识别** + 多家 AI 服务商生成结构化纪要。

**文档版本**：Spec v1.1 · **代码状态**：待实现 · **交付里程碑**：v0.1.0（可测试构建）→ v1.0.0（签名公证发布版）

**v1.1 变更**（依据用户决策）：① 热词方案升级为四阶段「基线锚定 + 定向重解码」，普通文本准确率零退化；② 默认 ASR 模型改为 large-v3-turbo（MIT 许可）；③ Windows 交付单目录 .exe，不做安装包；④ 新增关键词别名表与命中率反馈闭环。

---

## 一、一句话定位

录音或导入会议音频，在**本地离线**完成语音识别，用**关键词库**把人名 / 产品名 / 术语识别准，再调用**任意 OpenAI 兼容或 Anthropic 服务商**生成固定章节的 Markdown 会议纪要，支持编辑与导出。

## 二、核心流程

```text
会议录音 / 导入音频
        │  MP3 · WAV · M4A · AAC · FLAC
        ▼
┌─────────────────────────────┐
│ 本地语音识别 (faster-whisper) │  ← 完全离线，默认 large-v3-turbo（MIT 许可）
└──────────────┬──────────────┘
               ▼
┌──────────────────────────────────────────┐
│ 关键词优先识别（四阶段，核心差异化）      │
│  ① 全局基线转写（不注入热词，零污染锚点）  │
│  ② 关键词缺口分析（三路候选区域定位）      │
│  ③ 定向重解码（分组注入 + 择优合并）       │
│  ④ 后处理纠错（别名精确 + 拼音/编辑距离）  │
│  ⑤ 校对：高亮、可撤销、可手动改、反馈闭环  │
└──────────────┬───────────────────────────┘
               ▼
┌─────────────────────────────┐
│ AI 生成结构化会议纪要         │  OpenAI 兼容 / Anthropic 原生
│ 概要·关键讨论·决定·行动项·未决 │  用户自配 Base URL + Key + 模型
└──────────────┬──────────────┘
               ▼
        编辑 → 导出 Markdown / TXT
```

## 三、硬约束（不可违反，验收一票否决项）

| ID | 约束 | 验收方式 |
|---|---|---|
| C1 | ❌ 禁止 Electron / Tauri / pywebview / 任何 WebView | 依赖清单审计：无 electron、tauri、pywebview，且不使用 QWebEngine 承载 UI |
| C2 | ✅ 原生 UI，双平台一套代码 | PySide6 控件，无 HTML/JS 渲染；macOS 与 Windows 共用同一份 UI 源码 |
| C3 | ✅ 语音识别完全离线 | 断网环境下转写全链路可用；代码中不存在任何云端 ASR 调用 |
| C4 | ✅ AI 不锁定厂商 | 至少跑通 1 家 OpenAI 兼容 + 1 家 Anthropic 服务商 |
| C5 | ✅ 交付 .app 与 .exe | CI Matrix 产物上传 Artifacts / Release |
| C6 | 🔒 无硬编码密钥 | 密钥扫描（gitleaks / detect-secrets）零命中；Key 加密存储 |
| C7 | 🔄 签名公证**可选**（已修订） | 项目不商用、面向自用 / 团队内部 / 开源免费分发，**不启用**商业签名公证。macOS 做 ad-hoc 自签名（`codesign --sign -`，免费无需账户）；Windows 不签名。完整性改用 sha256 校验和自验。详见 ADR-012 |
| C8 | 🎯 关键词识别准确率 ≥ 90% | 3 段中文样本（3–5 分钟，约 50 个关键词）离线评测达标 |
| C9 | 🧪 测试覆盖率 ≥ 70% 且全绿 | CI 上 pytest --cov 强制门 |

## 四、技术选型（已定稿，不再评估）

| 领域 | 选择 | 版本基线 | 理由 |
|---|---|---|---|
| 语言 | Python | 3.11.x | AI Agent 生成质量最高，语音 / AI 生态最全 |
| UI | PySide6 (Qt for Python) | 6.11.x | 原生控件、非 Web、一套代码双平台 |
| 本地 ASR | faster-whisper | 1.2.x | 离线、CTranslate2 加速、支持 initial_prompt |
| 关键词增强 | 四阶段：基线锚定 + 缺口分析 + 定向重解码 + 后处理纠错 | — | **热词效果做满，普通文本准确率零退化**（架构性保证） |
| AI 总结 | OpenAI 兼容 API + Anthropic 原生 API | openai 2.x / anthropic 1.x | 覆盖绝大多数服务商 |
| 打包 | PyInstaller | 6.x | 产出 .app / .exe |
| 构建 | GitHub Actions Matrix | macos-15 (arm64) / windows-latest | 双平台并行构建 |

**已否决方案**：Electron / Tauri（Web 方案）、Go + Fyne（ASR 生态弱）、C# + Avalonia（生态与 Agent 效率不如 Python）、Rust + Slint（迭代成本高）、.NET MAUI（macOS 受限）。详见 [docs/03-tech-stack.md](docs/03-tech-stack.md)。

## 五、文档索引（项目规范基线）

| # | 文档 | 内容 |
|---|---|---|
| — | **[热词原型验证工具](tools/proto/README.md)** | **项目代码未实现前即可运行**：三方案对照 + 零退化自动校验 |
|---|---|---|
| 01 | [项目概览与术语表](docs/01-project-overview.md) | 目标、范围、非目标、交付物、术语表 |
| 02 | [架构设计](docs/02-architecture.md) | 分层、模块划分、依赖方向、目录结构、ADR |
| 03 | [技术栈与依赖清单](docs/03-tech-stack.md) | 选型理由、版本、传递依赖与打包影响 |
| 04 | [核心模块规格](docs/04-core-modules.md) | 录音 / 导入 / 转写 / 总结 / 编辑导出 / 设置的接口与行为 |
| 05 | [关键词优先识别规格](docs/05-keyword-correction.md) | **四阶段架构**、缺口分析、定向重解码择优、别名表、9 门控 / 7 禁止、撤销、反馈闭环、评测口径 |
| 06 | [AI 服务商集成契约](docs/06-ai-providers.md) | 两类协议请求构造、重试、限流、错误中文映射 |
| 07 | [数据模型与持久化](docs/07-data-model.md) | 会议项目结构、配置、密钥存储、Schema 版本 |
| 08 | [安全规范](docs/08-security.md) | 密钥加密、日志脱敏、网络错误提示、供应链安全 |
| 09 | [UI 设计规范](docs/09-ui-design-spec.md) | 基于 Apple HIG 的设计令牌、窗口、页面线框、快捷键、可访问性 |
| 10 | [打包 · CI · 签名公证](docs/10-packaging-ci-signing.md) | PyInstaller spec、CI Matrix、codesign / notarytool / signtool |
| 11 | [测试策略](docs/11-testing.md) | 单元 / 集成 / UI / 准确率 / 跨平台冒烟，覆盖率门 |
| 12 | [实施路线图与验收](docs/12-roadmap-acceptance.md) | 里程碑 M0–M7、退出标准、验收清单、待确认事项 |

## 六、开发快速开始

### 6.0 先跑热词原型（推荐第一步）

项目代码尚未实现，但热词方案可以先独立验证——这是最该先证明有效的一环：

```bash
cd Project_MeetRecMaster
bash tools/proto/setup.sh                 # 装依赖，约 3-5 分钟
bash tools/proto/smoke.sh                 # TTS 音频 + tiny 模型，验证链路跑通

# 用你自己的会议录音做正式验证（large-v3-turbo）
python tools/proto/.venv/bin/python tools/proto/keyword_probe.py \
    --audio /path/to/meeting.mp3 \
    --keywords-file tools/proto/keywords.example.txt \
    --aliases-file  tools/proto/aliases.example.txt \
    --model large-v3-turbo
```

判断标准：C 四阶段方案的关键词命中数高于 A 基线，**且非关键词改动 = 0**（零退化成立）。

### 6.1 项目本体

```bash
# 1) 虚拟环境（禁止依赖全局 Python）
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2) 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3) 运行
python -m meetrec

# 4) 测试（覆盖率门 70%）
pytest -q --cov=meetrec --cov-fail-under=70

# 5) 打包
python -m PyInstaller build/meetrec.spec
```

## 七、代码规范

- **风格**：PEP 8，ruff format + ruff check，line-length = 100
- **类型**：公共接口必须有类型注解；mypy --strict 覆盖业务逻辑层（UI 层宽松）
- **提交**：Conventional Commits —— feat / fix / docs / test / refactor / build / chore
- **分支**：main（可发布）← dev（集成分支）← feat/<short-name> / fix/<short-name>
- **文档同步**：任何环境 / 配置 / 模型下载方式变更，必须同步更新对应文档并在同一提交中提交
- **密钥**：任何提交不得包含明文 API Key；CI 强制跑密钥扫描

## 八、交付物清单

1. 完整 Git 仓库（代码 + 测试 + 文档）
2. macOS：MeetRec Master.app（建议再打成 .dmg）
3. Windows：MeetRec Master.exe（one-folder 目录，**不做安装包**，见 ADR-011）
4. 用户手册 + 版本发布说明（Release Notes）
5. 验收通过条件见 [docs/12-roadmap-acceptance.md](docs/12-roadmap-acceptance.md)

---

*本仓库所有文档为项目规范基线。执行 Agent 可自行规划具体代码实现，但不得违反硬约束 C1–C9 与本文档中的验收口径。*
