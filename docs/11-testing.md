# 11 · 测试策略

---

## 1. 测试分层

| 层 | 目录 | 框架 | 目标 | 是否进 CI |
|---|---|---|---|---|
| 单元测试 | tests/unit/ | pytest | 业务逻辑、算法、请求构造 | ✅ |
| 集成测试 | tests/integration/ | pytest | 模块协作、协议链路 | ✅ |
| UI 测试 | tests/ui/ | pytest-qt | 交互不报错、状态机正确 | ✅ |
| 准确率测试 | tests/accuracy/ | pytest + 脚本 | 关键词召回率与零退化 | ⚠️ 手动触发（耗时） |
| 性能测试 | tests/perf/ | pytest-benchmark | 吞吐与延迟预算 | ⚠️ 夜间任务 |
| 跨平台冒烟 | scripts/smoke_test.py | 独立脚本 | 构建产物可运行 | ✅（发布前） |

**覆盖率门**：pytest-cov，全局 ≥ 70%，CI 用 --cov-fail-under=70 强制阻断。

---

## 2. 单元测试（tests/unit/）

### 2.1 模块与用例

| 模块 | 关键用例 | 数量目标 |
|---|---|---|
| keywords.prompt_builder | 排序稳定性、预算截断边界（220 字符恰好 / 超出 1 字符）、去重、噪声过滤、分组相关度排序 | 15+ |
| keywords.corrector | 相似度公式（含拼音缺失字回退）、9 条门控逐条、7 条禁止规则逐条、区间冲突消解、别名精确匹配、别名冲突检测 | 25+ |
| keywords.stage2 | 三路候选定位逐条、区域合并、预算裁剪（15% 上限）、跳过条件 | 12+ |
| keywords.stage3 | D1–D5 择优规则逐条、上下文扩展、片段越界截断、beam 参数覆盖 | 12+ |
| summary.openai_compat | headers、URL 拼接（含 base_url 已带 /chat/completions）、max_tokens 与 max_completion_tokens 开关、temperature 降级重试、content 为数组 | 14+ |
| summary.anthropic_native | x-api-key、anthropic-version、system 提升、content block 形态、max_tokens 缺省 4096、stop_reason 处理 | 12+ |
| summary.client | 429 + Retry-After、500 三次退避、401 不重试、400 降级、超时、取消、总等待上限 | 12+ |
| summary.parser | 5 章节齐全 / 缺失 / 顺序错 / 空章节 / Markdown 表格 | 10+ |
| summary.prompts | 变量渲染、未知变量阻断、变量白名单、模板校验 | 8+ |
| asr.engine | 参数展开、baseline 与 redecode 差异、模型缺失、断网保护、分块边界 | 10+ |
| audio.recorder | 状态机 5 转移、空录音、设备拔出、暂停续写 | 8+ |
| audio.importer | 格式探测、大文件拒绝、解码失败、复制与转码 | 8+ |
| storage | SQLite 事务、FTS 搜索与降级 LIKE、回收站、迁移幂等、原子写 | 12+ |
| config / secrets | 配置校验、迁移失败回滚、keyring 降级 AES-GCM 往返、脱敏过滤 6 条 | 12+ |
| errors | 15 类异常 → 中文提示映射全覆盖 | 15 |
| export | 3 格式 × 3 内容组合、BOM 开关、覆盖询问 | 10+ |

### 2.2 Mock 策略

| 被 Mock 对象 | Mock 方式 |
|---|---|
| faster-whisper | 假引擎返回固定 segments / words（含可控 probability），支持按调用次数返回不同结果（模拟 baseline vs redecode） |
| HTTP（OpenAI / Anthropic） | responses 或 respx 拦截，断言请求体构造 |
| keyring | monkeypatch 抛 InvalidPasswordAccessError 触发降级 |
| 文件系统 | tmp_path fixture，不碰真实用户目录 |
| 时间 | freezegun 或 monkeypatch now_utc |
| sounddevice | 假 InputStream 回放预置 buffer |

### 2.3 属性测试

用 hypothesis 覆盖不变量（比枚举用例更能防回归）：

| 不变量 | 意义 |
|---|---|
| 任意关键词集合 → prompt 字符数 ≤ 260 | 预算绝不溢出 |
| 任意输入 → 最终文本中**普通文本部分与基线逐字一致** | **零退化不变量**（05 章 §2.3 的架构保证） |
| 任意 (S, K) → score ∈ [0, 1] | 分数有界 |
| 任意 CorrectionRecord 序列 → 撤销后文本等于 before 拼接 | 可逆性 |
| 任意配置 dict → 校验失败抛具体错误而非 KeyError | 健壮性 |

---

## 3. 集成测试（tests/integration/）

| 场景 | 内容 | 备注 |
|---|---|---|
| 四阶段全链路 | 关键词库 + 别名 → baseline → 缺口分析 → Mock redecode → 纠错 → transcript.json 落盘 | 断言 corrections 字段结构 |
| 开关组合 5 种 | 仅基线 / 基线+Stage3 / 基线+Stage4 / 全四阶段 / 旧全局注入方案 | 用于归因对比 |
| OpenAI 兼容协议 | 完整请求 → 响应 → 解析 → 落盘 | Mock HTTP |
| Anthropic 协议 | 同上，验证 system / max_tokens / content block | Mock HTTP |
| 限流重试 | 429 → Retry-After 等待 → 成功 | 用极短 sleep 加速 |
| 音频导入到转写 | 预置 WAV fixture → 导入 → 解码 → baseline | 用 tiny 模型控耗时 |
| 模型下载缓存 | 假下载源 → 进度 → sha256 校验 → 二次加载不重下 | tmp_path |
| 会议生命周期 | 创建 → 转写 → 总结 → 导出 → 删除 → 回收站 → 永久删除 | 端到端 |
| 配置迁移 | v1 → v2 迁移 + 幂等性 + 失败回滚 | |
| 诊断包 | 含 Key 的配置 → 导出 → 全量扫描无命中 | 安全回归 |

---

## 4. UI 测试（tests/ui/）

### 4.1 环境

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ui/
```

使用 pytest-qt 的 qtbot fixture；所有测试不弹窗、不触网、不加载真实模型。

### 4.2 覆盖范围

| 页面 / 控件 | 用例 |
|---|---|
| 录音控件 | 状态机 5 转移、按钮可用性随状态变化、暂停后计时暂停、空录音提示 |
| 关键词库对话框 | 增删改查、分组增删、别名添加与冲突提示、导入导出、排序 |
| 服务商对话框 | 三字段必填校验、base_url 格式校验、明文 http 拒绝（localhost 例外）、连接测试按钮 |
| Prompt 模板对话框 | 变量白名单校验、未知变量阻断、恢复默认 |
| 导出对话框 | 3 格式 × 3 内容组合、路径选择、覆盖询问、BOM 开关 |
| 主题切换 | 浅色 / 深色 / 跟随系统，切换后无样式残留 |
| i18n | 中 / 英切换即时生效、无未翻译 key 残留（断言不含 tr() 原串） |
| 主窗口 | 最小尺寸约束、窗口几何记忆、单实例锁 |
| 错误展示 | 15 类错误各弹一次，断言中文提示与「重试」按钮可见性 |

### 4.3 规则

1. UI 测试只验证**不崩溃、状态正确、控件可达**，不截图对比（避免平台字体差异导致 flaky）。
2. 所有耗时操作在测试中用 fake 任务替代（注入 fake engine / fake provider）。
3. 每个测试独立 QApplication，测试后 quit，避免状态泄漏。
4. 测试耗时预算：全部 UI 测试 < 60 秒。

---

## 5. 准确率测试（tests/accuracy/）

### 5.1 结构

```text
tests/accuracy/
├── run_accuracy.py          # 主脚本
├── ground_truth/
│   ├── sample1.json
│   ├── sample2.json
│   └── sample3.json
├── samples/
│   ├── sample1.wav
│   ├── sample2.wav
│   └── sample3.wav
└── reports/                 # 输出（不入库，.gitignore）
```

### 5.2 ground_truth.json 结构

```json
{
  "sample": "sample1",
  "duration_sec": 287.4,
  "language": "zh",
  "keywords": [
    {"text": "张一鸣", "group": "人名", "expected_count": 6},
    {"text": "MeetRec Master", "group": "产品名", "expected_count": 4},
    {"text": "CTranslate2", "group": "术语", "expected_count": 3}
  ],
  "aliases": [
    {"text": "张一鸣", "aliases": ["章一鸣", "张一明"]}
  ],
  "reference_transcript": "会议开始……（完整参考转写）",
  "normal_text_spans": [
    {"start": 120.0, "end": 180.0, "text": "……（普通文本参考段，用于零退化校验）"}
  ]
}
```

### 5.3 运行方式

```bash
# 完整跑（5 种组合 × 3 段，约 30–60 分钟）
python -m tests.accuracy.run_accuracy --model large-v3-turbo

# 只跑默认组合（验收快速检查）
python -m tests.accuracy.run_accuracy --combinations full --model large-v3-turbo

# 指定样本
python -m tests.accuracy.run_accuracy --sample sample1
```

### 5.4 断言门

| 指标 | 门 | 失败动作 |
|---|---|---|
| 关键词召回率（组合 4） | ≥ 0.90 | 阻断发布 |
| 普通文本 WER 退化 | == 0（严格） | 阻断发布 |
| 整体 WER | ≤ 基线 WER | 阻断发布 |
| 自动改动精确率 | ≥ 0.90 | 告警 + 人工复核 |

### 5.5 报告内容

Markdown 报告，必须包含：

- 环境：模型、compute_type、平台、Python 版本、faster-whisper 版本
- 关键词库：总数、启用数、别名数、注入字符数
- Stage 2：候选区域数、总时长占比、被裁剪数量
- Stage 3：采用数、采用率、增益率、平均 logprob 差
- Stage 4：别名替换数、模糊替换数、歧义数、被撤销数
- 每段 × 每组合 × 每指标的数值矩阵
- 每个关键词的 hit / expected 明细

---

## 6. 性能测试（tests/perf/）

| 场景 | 预算 | 方法 |
|---|---|---|
| 基线转写吞吐（large-v3-turbo） | ≥ 0.5× 实时 | 预置 5 分钟 WAV，计时 |
| Stage 2 缺口分析 | < 100 ms / 1 小时转写 | benchmark |
| Stage 3 单区域重解码 | < 2× 区域时长 | benchmark |
| Stage 4 纠错 | < 3 s / 1 小时转写 | benchmark |
| 全流程总耗时 | ≤ 基线 × 1.15 | 端到端 |
| 应用冷启动（模型已缓存） | ≤ 3 s | 计时到主窗口可交互 |
| AI 请求（Mock） | 构造 < 5 ms | benchmark |

性能测试不进 PR CI（耗时且受 runner 波动影响），走夜间 workflow，结果归档。

---

## 7. 跨平台冒烟（scripts/smoke_test.py）

对**构建产物**（不是源码）执行，发布前必跑：

| # | 步骤 | 断言 |
|---|---|---|
| 1 | 启动应用 | 进程存活 > 5 秒 |
| 2 | 加载 tiny 模型 | 下载或命中缓存成功 |
| 3 | 转写 3 秒 fixture 音频 | 输出非空文本 |
| 4 | 关键词注入 | prompt 构造成功 |
| 5 | Mock AI 请求 | 请求体构造正确 |
| 6 | 导出 Markdown | 文件生成且非空 |
| 7 | 退出 | 退出码 0 |

失败即视为构建产物不可用，阻断发布。

---

## 8. 测试数据与安全

| 项 | 规则 |
|---|---|
| fixture 音频 | 使用合成语音或已获授权样本，不入库真实会议录音 |
| 准确率样本 | 需明确授权；ground_truth 标注不入库敏感内容 |
| 测试用 API Key | 一律用假 Key（Mock 拦截），禁止在测试中调用真实服务商 |
| 密钥扫描 | CI 跑 gitleaks，测试目录同样扫描 |
| 报告脱敏 | accuracy 报告可能含转写片段，reports/ 加入 .gitignore |

---

## 9. 相关文档

- [05 · 关键词优先识别规格](05-keyword-correction.md)（§13 测试要点）
- [06 · AI 服务商集成契约](06-ai-providers.md)（§10 契约测试）
- [08 · 安全规范](08-security.md)（§10 安全测试清单 S1–S10）
- [10 · 打包 · CI · 完整性校验](10-packaging-ci-signing.md)（CI 工作流）

