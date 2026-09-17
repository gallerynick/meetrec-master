# 10 · 打包 · CI · 完整性校验

> **重要**：本项目不商用，**不启用商业签名与公证**（ADR-012）。本章原「签名公证」内容已改为「ad-hoc 自签名 + sha256 校验和」。
> 若未来触发 ADR-012 的重新启用条件，签名流程见 Git 历史中的旧版本文档。

---

## 1. 交付物定义

| 平台 | 交付物 | 签名 | 说明 |
|---|---|---|---|
| macOS | MeetRec Master.app + MeetRecMaster-{version}.dmg | **ad-hoc 自签名**（`codesign --sign -`，免费无需账户） | dmg 内含 .app 与「拖到 Applications」提示图标 |
| Windows | **MeetRec Master.exe（one-folder 目录）** | **不签名** | **不做安装包**（ADR-011），压缩为 zip 分发 |
| 全平台 | SHA256SUMS.txt | — | 所有产物的 sha256 校验和，替代签名作为完整性保证 |

Windows 交付结构：

```text
MeetRecMaster-1.0.0-windows-x64/
├── MeetRec Master.exe        # 主程序（未签名，见 ADR-012）
├── SHA256SUMS.txt            # 校验和（用户自验完整性）
├── _internal/
│   ├── Python*.dll           # 未签名，正常
│   ├── ctranslate2/
│   ├── onnxruntime/
│   ├── av/
│   ├── PySide6/Qt/
│   ├── rapidfuzz/
│   ├── pypinyin/
│   └── jieba/
└── LICENSES.txt              # 第三方许可汇总（含模型许可）
```

---

## 2. PyInstaller 构建

### 2.1 spec 文件要点

```python
# build/meetrec.spec（要点摘录）
a = Analysis(
    ["src/meetrec/__main__.py"],
    pathex=["src"],
    datas=[
        ("src/meetrec/resources", "meetrec/resources"),
        (".../PySide6/Qt/bin/plugins", "PySide6/Qt/plugins"),
    ],
    hiddenimports=[
        "meetrec",
        "meetrec.ui",
        "meetrec.asr",
        "meetrec.keywords",
        "meetrec.summary",
        "meetrec.audio",
        "meetrec.storage",
        "ctranslate2",
        "tokenizers",
        "onnxruntime",
        "onnxruntime.capi",
        "av",
        "sounddevice",
        "rapidfuzz.distance",
        "rapidfuzz.fuzz",
        "pypinyin",
        "jieba",
        "cryptography.hazmat.bindings._rust",
        "keyring.backends.macOS",
        "keyring.backends.wincred",
    ],
    excludes=["PyQt5", "PyQt6", "tkinter", "matplotlib", "scipy", "pandas"],
)
```

### 2.2 必须显式 collect 的包

| 包 | 原因 |
|---|---|
| faster_whisper / ctranslate2 | 含 ctranslate 动态库与 kernels |
| tokenizers | Rust 扩展 |
| onnxruntime | Silero VAD；含 pybind11 state 动态库 |
| av (PyAV) | ffmpeg 动态库，wheel 已内置 |
| cryptography | Rust 绑定 |
| rapidfuzz | C++ 扩展 |
| pypinyin / jieba | 数据文件（拼音库 / 词典），必须 collect_data_files |

### 2.3 体积控制

| 措施 | 说明 |
|---|---|
| excludes | 排除 PyQt5 / PyQt6 / tkinter / matplotlib / scipy / pandas |
| UPX | 默认关闭（对 ctranslate2 / onnxruntime 有稳定性风险） |
| 模型不打包 | ADR-009，首次运行下载 |
| 体积预算 | macOS .app ≤ 500 MB；Windows 目录 ≤ 600 MB；CI 超预算告警 |

---

## 3. macOS 打包流程

### 3.1 构建

```bash
python -m PyInstaller build/meetrec.spec --noconfirm --clean
# 产物：dist/MeetRec Master.app
```

### 3.2 Info.plist 必需键

| Key | 值 / 说明 |
|---|---|
| CFBundleIdentifier | io.meetrec.master（默认值，已确认）。Bundle ID 规范是反向域名，`cn` 是国家代码不符合规范；若有 GitHub 用户名可改为 `com.github.<用户名>.meetrecmaster` |
| CFBundleName / CFBundleDisplayName | MeetRec Master |
| CFBundleShortVersionString | 与 SemVer 一致 |
| CFBundleVersion | 构建号（单调递增） |
| LSMinimumSystemVersion | 12.0 |
| NSMicrophoneUsageDescription | **必填**：中文说明，否则系统直接拒绝麦克风权限 |
| CFBundleIconFile | AppIcon.icns |

### 3.3 签名（ad-hoc 自签名，替代商业签名）

```bash
# ad-hoc 签名：使用 "-" 表示自签名，免费、无需任何账户或证书
codesign --force --sign - --deep dist/"MeetRec Master.app"

# 校验签名一致性
codesign --verify --deep --strict dist/"MeetRec Master.app"
```

**为什么还需要签名**：即使不申请商业证书，也必须签名。否则 .app 内由 PyInstaller 收集的二进制库签名不一致，macOS 可能直接拒绝执行并报 "code signature is invalid"。ad-hoc 签名让所有内部库都获得一致的自签名标识。

**为什么不做 hardened runtime**：`--options runtime` 需要 Developer ID 证书才有效，ad-hoc 下无意义。本项目不请求辅助功能 / 输入监控等特权，不需要 hardened runtime。

**App Sandbox 明确不启用**：需要写入用户任意目录（音频导入 / 导出），沙箱会阻断。network.client 与 user-selected.read-write 两个 entitlement 也一并省略——ad-hoc 签名下 entitlements 不会被系统强制校验，但保留 plist 也无害，为未来切回 Developer ID 留位。

### 3.4 公证（已取消）

**不做公证**。公证（notarytool + stapler）必须搭配 Developer ID 证书，本项目不申请，因此整段流程删除。

用户首次打开 .app 时的体验与处理方式：

| 现象 | 处理 |
|---|---|
| Gatekeeper 提示「MeetRec Master.app 无法打开，因为来自身份不明的开发者」 | 右键点击 .app → 打开 → 在弹出框中选「打开」。一次即可，后续直接双击。 |
| 复制到另一台 Mac 后再次提示 | 重复上述操作（信任关系按机器 + Bundle ID 记录） |

**分发给团队成员时**：在 Release 说明里附上这一句操作指引即可，不需要任何证书。

### 3.5 dmg 制作

```bash
hdiutil create   -volname "MeetRec Master"   -srcfolder dist/dmg-staging   -ov -format UDZO   dist/MeetRecMaster-1.0.0.dmg
```

dmg-staging 内容：MeetRec Master.app、指向 /Applications 的符号链接、背景图（可选）。

---

## 4. Windows 打包流程

### 4.1 构建

```powershell
python -m PyInstaller build/meetrec.spec --noconfirm --clean
# 产物：dist/MeetRec Master.exe + dist/_internal/
```

### 4.2 签名

**不签名**。本项目的 Windows 产物完全不做 Authenticode 签名（ADR-012）。

用户首次运行 .exe 时的体验：

| 现象 | 处理 |
|---|---|
| SmartScreen 蓝色全屏警告「Windows 已保护你的电脑」 | 点击「更多信息」→「仍要运行」 |
| 杀毒软件误报 | 申请企业 EDR 白名单，或改用 zip 内直接运行（部分 EDR 对压缩包内文件策略不同） |

**为什么不签**：Authenticode 的 OV 证书需 ¥3000–8000/年 + 企业身份验证；自签名证书不被任何信任链认可，会让 SmartScreen 判定更差，比完全不签更糟。本项目不商用，这笔成本不构成必要投入。

**替代完整性保证**：sha256 校验和（见 §6）。

### 4.3 打包分发

```powershell
Compress-Archive -Path "dist\*" -DestinationPath "MeetRecMaster-1.0.0-windows-x64.zip" -Force
```

### 4.4 无安装包的补偿措施（ADR-011）

| 缺口 | 补偿 |
|---|---|
| 无开始菜单快捷方式 | 应用首次启动提供「创建桌面快捷方式」按钮；README 说明手动创建方法 |
| 无卸载入口 | 应用内「关于」页显示安装目录；文档说明直接删除目录即可 |
| 无 per-machine 安装 | 全部按 per-user 设计，无需管理员权限 |
| 多文件目录易误删 | 应用启动时校验 _internal 完整性（关键 .dll 缺失则报 MissingDependencyError 并给出重新下载指引） |

---

## 5. GitHub Actions CI

### 5.1 工作流矩阵

```yaml
# .github/workflows/release.yml
name: release

on:
  push:
    tags: ["v*.*.*"]        # SemVer tag 触发发布构建

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        # 用户决策：macOS 仅 Apple Silicon（arm64），不做 Intel x64。
        # 代价：Intel Mac 用户无法运行本版本，需在发布说明中明确。
        - os: macos-15
          arch: arm64
        - os: windows-latest
          arch: x64
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - name: Install deps
        run: pip install -r requirements.lock -r requirements-dev.txt
      - name: Test
        run: pytest -q --cov=meetrec --cov-fail-under=70 -m "not accuracy"
      - name: Build
        run: python -m PyInstaller build/meetrec.spec --noconfirm --clean
      - name: Smoke test (built artifact)
        run: python scripts/smoke_test.py
      - name: Ad-hoc sign (macOS)
        if: startsWith(matrix.os, 'macos')
        run: codesign --force --sign - --deep dist/"MeetRec Master.app" && codesign --verify --deep --strict dist/"MeetRec Master.app"
      # Windows 不签名（ADR-012）：SmartScreen 警告为预期行为
      - name: Package + checksums
        run: bash build/package.sh && (cd dist && shasum -a 256 *.dmg *.zip > SHA256SUMS.txt)
      - uses: actions/upload-artifact@v4
        with:
          name: MeetRecMaster-${{ github.ref_name }}-${{ matrix.os }}-${{ matrix.arch }}
          path: dist/*.dmg, dist/*.zip, dist/SHA256SUMS.txt
```

### 5.2 双工作流

| 工作流 | 触发 | 内容 |
|---|---|---|
| ci.yml | PR / push to main | 单元测试 + UI 测试 + 密钥扫描 + pip-audit + ruff + mypy；不构建、不签名 |
| release.yml | v*.*.* tag | 全量测试 + 构建 + ad-hoc 自签名 + sha256 校验和 + 打包 + 上传 Release（无商业签名，见 ADR-012） |

### 5.3 CI 关键检查（ci.yml）

| 步骤 | 工具 | 阻断条件 |
|---|---|---|
| 格式化 / lint | ruff format --check + ruff check | 任何违规 |
| 类型检查 | mypy --strict（业务层） | 业务层错误 |
| 密钥扫描 | gitleaks | 任何命中 |
| 依赖漏洞 | pip-audit | high / critical |
| 单元测试 | pytest + cov | 失败或覆盖率 < 70% |
| UI 测试 | pytest-qt (offscreen) | 失败 |

---

## 6. 完整性校验（替代签名凭据）

本项目不申请任何签名证书（ADR-012），因此**不需要配置任何 GitHub Secrets**。完整性保证改用 sha256 校验和。

### 6.1 生成

CI 在打包步骤之后生成（见 §5.1）：

```bash
cd dist
shasum -a 256 *.dmg *.zip > SHA256SUMS.txt
cat SHA256SUMS.txt
```

产物格式（Unix 标准 sha256sum 格式，Windows 用 certutil 自行核对）：

```text
a1b2c3...  MeetRecMaster-1.0.0.dmg
d4e5f6...  MeetRecMaster-1.0.0-windows-x64.zip
```

### 6.2 用户如何自验

| 平台 | 命令 | 通过标准 |
|---|---|---|
| macOS | `shasum -a 256 MeetRecMaster-1.0.0.dmg` | 输出前 64 位与 SHA256SUMS.txt 中该行前缀一致 |
| Windows | `certutil -hashfile MeetRecMaster-1.0.0-windows-x64.zip SHA256` | 输出的 hex 串（忽略空格）与校验和一致 |

Release 页面在文件列表下方贴出 SHA256SUMS.txt 全文，用户对照即可。

### 6.3 仍须遵守的安全项

即使不签名，以下安全要求不变（见 08 章）：

1. 代码中的 API Key **永不**硬编码；CI 仍跑 gitleaks。
2. 应用内的密钥仍走 keyring → AES-GCM 降级路径（ADR-007）。
3. 诊断包导出前必须脱敏（ADR-010）。
4. **依赖供应链**：pip-audit 在 CI 阻断 high / critical 漏洞。签名缺失无法靠供应链审查弥补，所以这条比签名项目更关键。
5. Release 页面必须标注 git commit SHA，便于用户追溯产物对应的确切代码。

---

## 7. 版本号与发布流程

### 7.1 版本规则

- SemVer：MAJOR.MINOR.PATCH，如 1.2.0。
- Git Tag：v1.2.0 触发 release.yml。
- 版本来源：单一 pyproject.toml 中的 version 字段，构建时注入 Info.plist / 文件版本信息。

### 7.2 发布步骤

| # | 步骤 | 责任人 |
|---|---|---|
| 1 | 合并代码到 main | 开发 |
| 2 | 本地跑全量测试 + 准确率评测 | 开发 |
| 3 | 更新 CHANGELOG 与 Release Notes | 开发 |
| 4 | git tag v{version} 并 push | 开发 |
| 5 | release.yml 自动构建 + ad-hoc 自签名 + sha256 校验和 + 上传 | CI |
| 6 | 双平台手动验收（见 12 章验收清单） | 测试 |
| 7 | 发布 GitHub Release | 开发 |

### 7.3 发布前门禁（全部通过才能打 tag）

| # | 门禁 |
|---|---|
| G1 | CI 全绿（单测 + UI + 安全扫描） |
| G2 | 关键词召回率 ≥ 90% 且普通文本 WER 退化 == 0（准确率报告） |
| G3 | 至少各跑通 1 家 OpenAI 兼容 + 1 家 Anthropic 服务商 |
| G4 | macOS ad-hoc 自签名一致（`codesign --verify --deep --strict` 通过） |
| G5 | SHA256SUMS.txt 已生成且与实际产物一致（两平台） |
| G6 | 仓库无硬编码密钥（gitleaks 零命中） |
| G7 | 模型许可清单已核对并随包分发（LICENSES.txt） |
| G8 | 双平台核心流程手动冒烟通过 |

---

## 8. 常见构建故障与排查

| 现象 | 原因 | 处理 |
|---|---|---|
| .app 启动即崩溃 | 缺 Qt 平台插件 | spec 中显式收 PySide6/Qt/plugins/platforms |
| 报「找不到 ctranslate2」 | 未 collect ctranslate2 | hiddenimports + collect_dynamic_libs |
| VAD 不生效 | 缺 onnxruntime 动态库 | collect onnxruntime + silero model 文件 |
| 音频导入失败 | 缺 PyAV 的 ffmpeg 库 | collect av 的 .dylib / .dll |
| 中文分词报错 | jieba 词典未打包 | collect_data_files(jieba) |
| 拼音相似度全 0 | pypinyin 数据未打包 | collect_data_files(pypinyin) |
| macOS 报「code signature is invalid」 | .app 内二进制签名不一致 | 必须执行 ad-hoc 自签名（`codesign --force --sign - --deep`），不可跳过 |
| Windows SmartScreen 仍警告 | 只签了 .exe | 签全部 .exe / .dll / .pyd |
| signtool 报「时间戳服务器不可达」 | 网络问题 | 换 timestamp.digicert.com / timestamp.sectigo.com |
| 模型首次下载失败 | 断网或 HF 不可达 | 支持断点续传 + 本地 models 目录手动放置 |

---

## 9. 相关文档

- [02 · 架构设计](02-architecture.md)（ADR-009 模型不打包 / ADR-011 Windows 单目录）
- [03 · 技术栈与依赖清单](03-tech-stack.md)（构建工具链与依赖安全策略）
- [08 · 安全规范](08-security.md)（凭据与许可证）
- [11 · 测试策略](11-testing.md)（CI 测试矩阵）
- [12 · 实施路线图与验收](12-roadmap-acceptance.md)（发布门禁）





