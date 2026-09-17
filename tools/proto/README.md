# 热词原型验证工具

> **在项目代码尚未实现前，独立验证热词四阶段架构是否真的有效。**
> 一次运行同时给出三组对照，让你看到「旧方案副作用」和「新方案零退化」的实测数据。

---

## 1. 为什么现在就要跑

项目的差异化能力是热词，而热词方案的成败决定整个项目要不要重做。**先证明有效，再写 4000 行项目代码**，比反过来便宜得多。

这个脚本不依赖 `src/meetrec`，只用 faster-whisper + pypinyin + rapidfuzz，一次运行对比三种方案：

| 代号 | 方案 | 作用 |
|---|---|---|
| A | 仅基线（不注入热词） | 对照组：召回率下界、基线文本 |
| B | 旧方案：全局 initial_prompt 注入 + 后处理 | 证明副作用存在 |
| C | 四阶段：基线 → 缺口分析 → 定向重解码 → 后处理 | 验证新架构 |

---

## 2. 安装依赖

```bash
cd Project_MeetRecMaster
python3.11 -m venv tools/proto/.venv
source tools/proto/.venv/bin/activate      # Windows: tools\proto\.venv\Scripts\activate
pip install faster-whisper pypinyin rapidfuzz av numpy
```

或直接跑 `tools/proto/setup.sh`。

首次运行会自动下载模型到 `~/.cache/huggingface/hub/`：

| 模型 | 体积 | 用途 |
|---|---|---|
| tiny | ~75 MB | 链路冒烟（识别质量差，只看脚本能跑通） |
| **large-v3-turbo** | ~1.6 GB | **正式验证用这个**（默认） |
| large-v3 | ~3 GB | 最高质量对照 |

---

## 3. 准备输入

### 3.1 音频

**最好用你自己的一段真实会议录音**（3–5 分钟，MP3/WAV/M4A 均可）。真实录音才能暴露真实的 ASR 错误。

没有录音时可以先做链路冒烟（识别结果会很准，看不出差异，但能验证脚本没坏）：

```bash
# macOS：用系统 TTS 合成一段含关键词的中文音频
say -v Eddy -o /tmp/demo.aiff -r 165 \
  '今天会议主要讨论 MeetRec Master 的整体方案。张一鸣他们负责 PySide6 的界面部分，雷军那边负责 faster-whisper 的集成。CTranslate2 的 int8 量化效果不错，VAD 模块用 Silero，打包用 PyInstaller，Windows 那边还要处理 Authenticode 签名和 SmartScreen 提示。'
```

### 3.2 关键词

复制示例改：

```bash
cp tools/proto/keywords.example.txt tools/proto/my_keywords.txt
```

每行一个。示例里是人名 / 产品名 / 术语三类。

### 3.3 别名（强烈建议填）

别名是「热词做好」里性价比最高的一项——ASR 错误是系统性的，同一个词几乎每次都错成同一个写法：

```bash
cp tools/proto/aliases.example.txt tools/proto/my_aliases.txt
```

格式 `关键词|别名1|别名2`。至少给主要人名和产品名各填 2–3 个别名。

---

## 4. 运行

```bash
python tools/proto/keyword_probe.py \
    --audio /path/to/meeting.mp3 \
    --keywords-file tools/proto/my_keywords.txt \
    --aliases-file  tools/proto/my_aliases.txt \
    --model large-v3-turbo
```

常用参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| --model | large-v3-turbo | 验证质量请用这个；冒烟用 tiny |
| --device | cpu | 有 NVIDIA GPU 可用 cuda |
| --compute-type | int8 | GPU 用 float16 或 int8_float16 |
| --policy | balanced | conservative / balanced / aggressive |
| --language | zh | en 用于英文会议 |
| --report | 自动时间戳 | 指定报告路径 |

---

## 5. 读报告

报告是 Markdown，核心看四块。

### 5.1 汇总对比

| 方案 | 关键词命中数 | 召回率 | 耗时 | 自动改动数 |
|---|---|---|---|---|
| A 仅基线 | ... | ... | ... | 0 |
| B 旧方案（全局注入） | ... | ... | ... | ... |
| C 四阶段 | ... | ... | ... | ... |

**看 C 的命中数是否明显高于 A**。如果 C 约等于 A，说明热词没起作用，要排查 Stage 3 是否真的跑到了候选区域。

### 5.2 逐关键词命中

每个关键词在三方案下的命中次数。**重点看「A 为 0 但 C 大于 0」的词**——这是热词真正的增量贡献。

### 5.3 零退化校验（最关键）

这是回答「热词有没有牺牲识别正确率」的直接证据：

```text
## 零退化校验（A 基线 vs C 四阶段）
- 差异区间总数：7
- 可归因于关键词的差异：7
- 非关键词改动：0

结论：零退化成立 —— C 的普通文本与 A 基线逐字一致，全部差异都由关键词引入。

## 零退化校验（A 基线 vs B 旧方案）
- 差异区间总数：19
- 可归因于关键词的差异：7
- 非关键词改动：12 ← 这是旧方案的副作用
```

| 指标 | 期望 | 不达标意味着 |
|---|---|---|
| C 的非关键词改动 | **0** | Stage 3 的 D2/D3 合并规则或 Stage 4 门控太松，把正常文本改坏了 |
| B 的非关键词改动 | **大于 0** | 全局注入的副作用（预期如此，这是新架构存在的理由） |

如果 C 的非关键词改动大于 0，报告里会列出具体区间，照着排查：是 Stage 3 采用了不该采用的重解码结果（logprob 或编辑距离门控），还是 Stage 4 的 M1/M2 阈值太松。

### 5.4 定向重解码决策

列出每个候选区域的决策理由：采用 / D2 logprob 劣化 / D3 差异过大 / D4 无关键词增益。这里能看到模型在哪些区域真的被热词偏置带动了，哪些被规则拦下来了。

---

## 6. 怎么判断方案有效

三条同时满足才算通过：

1. **热词有增量**：C 的关键词命中数高于 A，且至少 3 个关键词是「A 未命中、C 命中」的。
2. **零退化成立**：C 的非关键词改动 = 0。
3. **成本可接受**：C 的总耗时不超过 A 的 1.15 倍。

不满足时：

| 症状 | 先查什么 |
|---|---|
| C 命中约等于 A | Stage 2 是否找到候选区域？报告里看「缺口分析」的候选区域数；为 0 说明关键词根本没在低置信或疑似变体里出现，检查关键词是否与音频内容匹配 |
| C 命中高于 A 但零退化不成立 | Stage 3 的 D2/D3 阈值，或 Stage 4 的 M1/M2 |
| C 耗时超 1.15 倍 | 候选区域预算（BUDGET_RATIO 0.15），降到 0.10 试试 |

---

## 7. 局限

| 局限 | 说明 |
|---|---|
| 无分组注入 | 原型把前 6 个关键词整段注入；正式实现按区域分组相关度注入（docs/05 §5.2） |
| 无歧义门控 M7 / 频次保护 M8 | 原型只实现 M1/M2/M4/M5，正式实现 9 条门控全量 |
| 无撤销与 CorrectionRecord 落盘 | 原型只输出报告，不做持久化 |
| 无 UI | 就是命令行 |
| 召回率需 expected_count | 原型用 `text.count()` 统计命中，未做真值匹配；要算召回率需给关键词标期望次数 |
| 零退化是「可归因性」判定 | 用关键词索引判定差异是否关键词相关，非严格字符级还原；正式验收用 ground_truth.json 的普通文本参考段算 WER |

这些是**原型与正式实现的差距**，不是架构缺陷。要完整验证走 M4 的 `tests/accuracy/run_accuracy.py`（见 docs/11 §5）。

---

## 8. 常见问题

| 现象 | 处理 |
|---|---|
| 报 ModuleNotFoundError: faster_whisper | 激活虚拟环境，或 `pip install faster-whisper` |
| 模型下载卡住 | 设置镜像 `export HF_ENDPOINT=https://hf-mirror.com` 后重试 |
| 中文识别全是英文 | 检查 --language zh 是否生效；模型语言支持情况 |
| 「没有关键词」 | --keywords 与 --keywords-file 至少给一个 |
| Stage 2 候选区域为 0 | 音频里可能没这些关键词，或识别得太准了；换一段真实录音 |
| macOS 提示麦克风权限 | 不需要——脚本只读文件，不录音 |

---

## 9. 文件

| 文件 | 说明 |
|---|---|
| keyword_probe.py | 主脚本（自包含，约 700 行） |
| keywords.example.txt | 关键词示例 |
| aliases.example.txt | 别名示例 |
| setup.sh | 一键创建虚拟环境并安装依赖 |
| report-*.md | 运行输出的报告 |

## 10. 相关文档

- [docs/05-keyword-correction.md](../docs/05-keyword-correction.md) —— 四阶段架构完整规格（本脚本的原型版）
- [docs/11-testing.md](../docs/11-testing.md) —— §5 准确率测试（正式验收脚本）
- [docs/12-roadmap-acceptance.md](../docs/12-roadmap-acceptance.md) —— C8 验收口径
