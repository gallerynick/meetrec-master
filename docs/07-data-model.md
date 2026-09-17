# 07 · 数据模型与持久化

---

## 1. 目录布局

### 1.1 用户数据目录

macOS: ~/Library/Application Support/MeetRecMaster/
Windows: %APPDATA%/MeetRecMaster/
Linux: ~/.local/share/MeetRecMaster/

```text
MeetRecMaster/
├── config.json                 # 全局配置（不含密钥）
├── library.db                  # SQLite 索引
├── providers.json              # 服务商配置（api_key 为占位符 __vault__:{id}）
├── templates/
│   └── default-zh.md           # 内置默认 Prompt 模板
├── keywords/
│   └── library.json            # 关键词库
├── models/                     # ASR 模型缓存（可安全删除）
│   ├── small/
│   └── large-v3/
├── meetings/                   # 会议内容
│   └── {meeting_id}/
│       ├── meta.json
│       ├── audio/
│       │   ├── original.wav
│       │   └── decoded.wav
│       ├── transcript.json
│       ├── summary.json
│       └── summaries/
│           └── {run_id}.md
├── trash/                      # 回收站
├── logs/
│   └── meetrec.log             # 滚动日志
├── diagnostics/                # 诊断包暂存
└── cache/                      # 可清理缓存
```

### 1.2 缓存目录

使用 platformdirs.user_cache_dir。存放临时文件、模型下载中的 .part 文件、音频解码中间产物。可随时整目录删除。

### 1.3 目录创建规则

- 启动时惰性创建，缺失即建（不打印错误）。
- 目录不可写 → 启动即失败，中文提示并给出绝对路径，不做静默降级。

---

## 2. SQLite Schema（library.db）

### 2.1 连接设置

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

### 2.2 元数据表

```sql
CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
-- key 取值: schema_version / app_version / created_at
```

### 2.3 meetings 表

```sql
CREATE TABLE meetings (
  id               TEXT PRIMARY KEY,             -- UUIDv4
  title            TEXT NOT NULL,
  created_at       TEXT NOT NULL,                -- ISO8601 UTC
  updated_at       TEXT NOT NULL,
  duration_sec     REAL,
  audio_path       TEXT,
  transcript_path  TEXT,
  summary_path     TEXT,
  asr_model        TEXT,
  language         TEXT,                         -- zh / en
  provider_id      TEXT,
  provider_model   TEXT,
  keyword_count    INTEGER NOT NULL DEFAULT 0,
  correction_count INTEGER NOT NULL DEFAULT 0,
  status           TEXT NOT NULL DEFAULT 'recorded',
  trashed          INTEGER NOT NULL DEFAULT 0,
  tags             TEXT NOT NULL DEFAULT '[]',
  note             TEXT NOT NULL DEFAULT ''
);

CREATE INDEX idx_meetings_updated ON meetings(updated_at DESC);
CREATE INDEX idx_meetings_trashed ON meetings(trashed);
```

status 取值：recorded / transcribed / summarized / exported

### 2.4 全文索引（FTS5）

```sql
CREATE VIRTUAL TABLE meetings_fts USING fts5(
  title, note, tags,
  content='meetings',
  content_rowid='rowid',
  tokenize='unicode61'
);

CREATE TRIGGER meetings_ai AFTER INSERT ON meetings BEGIN
  INSERT INTO meetings_fts(rowid, title, note, tags)
  VALUES (new.rowid, new.title, new.note, new.tags);
END;

CREATE TRIGGER meetings_ad AFTER DELETE ON meetings BEGIN
  INSERT INTO meetings_fts(meetings_fts, rowid, title, note, tags)
  VALUES ('delete', old.rowid, old.title, old.note, old.tags);
END;

CREATE TRIGGER meetings_au AFTER UPDATE OF title, note, tags ON meetings BEGIN
  INSERT INTO meetings_fts(meetings_fts, rowid, title, note, tags)
  VALUES ('delete', old.rowid, old.title, old.note, old.tags);
  INSERT INTO meetings_fts(rowid, title, note, tags)
  VALUES (new.rowid, new.title, new.note, new.tags);
END;
```

### 2.5 搜索策略

1. FTS5 匹配 title / note / tags，使用 MATCH 语法并按 BM25 排序。
2. 无结果或查询过短（少于 2 字符）→ 降级为 LIKE 模糊匹配。
3. 只返回 trashed=0 的记录；回收站界面单独查询 trashed=1。
4. 结果分页，每页 50 条。

---

## 3. 会议 meta.json

```json
{
  "schema_version": 1,
  "id": "uuid",
  "title": "产品评审会 2026-09-16",
  "created_at": "2026-09-16T09:12:03Z",
  "updated_at": "2026-09-16T10:40:11Z",
  "duration_sec": 4823.5,
  "language": "zh",
  "tags": ["产品", "评审"],
  "note": "",
  "audio": {
    "original_path": "audio/original.wav",
    "decoded_path": "audio/decoded.wav",
    "original_name": "IMG_0231.M4A",
    "original_sha256": "hash",
    "sample_rate": 48000,
    "channels": 2,
    "codec": "aac",
    "size_bytes": 48211003,
    "decode_sample_rate": 16000,
    "decode_channels": 1
  },
  "asr": {
    "model": "small",
    "compute_type": "int8",
    "device": "cpu",
    "vad_filter": true,
    "word_timestamps": true,
    "beam_size": 5,
    "initial_prompt_chars": 214,
    "engine_version": "1.2.1",
    "started_at": "2026-09-16T09:30:00Z",
    "elapsed_sec": 612.4
  },
  "keywords": {
    "library_id": "uuid",
    "library_snapshot_sha256": "hash",
    "injection_enabled": true,
    "correction_enabled": true,
    "correction_policy": "balanced",
    "count_used": 47,
    "count_truncated": 3
  },
  "summary": {
    "provider_id": "uuid",
    "provider_model": "deepseek-chat",
    "template_id": "default-zh",
    "temperature": 0.2,
    "max_tokens": 4096,
    "runs": ["run_001"]
  }
}
```

**设计要点**：meta.json 记录**生成时的参数快照**，而非引用当前设置。这样即使用户后来改了设置，历史会议仍可被解释与复现。

---

## 4. transcript.json

```json
{
  "schema_version": 1,
  "meeting_id": "uuid",
  "language": "zh",
  "raw": "会议开始。今天主要讨论 MeetRec Master 的 P0 范围……",
  "text": "会议开始。今天主要讨论 MeetRec Master 的 P0 范围……",
  "text_edited": false,
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 12.4,
      "text": "会议开始。今天主要讨论……",
      "avg_logprob": -0.21,
      "no_speech_prob": 0.01,
      "words": [
        {"start": 0.0, "end": 0.6, "word": "会议", "probability": 0.97},
        {"start": 0.6, "end": 1.1, "word": "开始", "probability": 0.91}
      ]
    }
  ],
  "corrections": [
    {
      "id": "uuid",
      "segment_id": 0,
      "offset": 12,
      "length": 3,
      "before": "章一鸣",
      "after": "张一鸣",
      "score": 0.86,
      "pinyin_sim": 0.91,
      "edit_sim": 0.66,
      "word_probs": [0.44, 0.51, 0.48],
      "rule_version": "1.0",
      "policy": "balanced",
      "created_at": "2026-09-16T09:36:12Z",
      "reverted": false
    }
  ],
  "stats": {
    "segment_count": 320,
    "word_count": 6120,
    "correction_count": 27,
    "correction_reverted": 2
  }
}
```

**约束**：

- raw 与 text 必须同时存在；text_edited 为 true 后 corrections 的 offset 视为**可能失效**，重新校正时以 raw 为基准。
- 单文件建议上限 20 MB；超过则按 segment 分片为 transcript.partN.json（schema 相同，meeting_id 相同）。

---

## 5. summary.json 与 summaries 目录

```json
{
  "schema_version": 1,
  "meeting_id": "uuid",
  "current_run_id": "run_001",
  "runs": [
    {
      "id": "run_001",
      "created_at": "2026-09-16T10:12:00Z",
      "provider_id": "uuid",
      "provider_name": "DeepSeek 主账号",
      "provider_type": "openai_compatible",
      "model": "deepseek-chat",
      "base_url": "https://api.deepseek.com/v1",
      "temperature": 0.2,
      "max_tokens": 4096,
      "latency_ms": 8421,
      "attempts": 1,
      "usage": {"input_tokens": 6120, "output_tokens": 940, "total_tokens": 7060},
      "sections": {
        "summary": true,
        "discussion": true,
        "decisions": true,
        "action_items": true,
        "open_questions": true
      },
      "chunks": 1,
      "markdown_path": "summaries/run_001.md",
      "markdown_edited": false
    }
  ]
}
```

- 每次生成追加一条 run，不覆盖历史，支持「回到上一版」。
- base_url 落盘（不含 Key）；Key 一律不落盘。
- markdown_edited 为 true 表示用户改过正文，重新生成时提示会新增 run。

---

## 6. 配置文件

### 6.1 config.json

```json
{
  "schema_version": 1,
  "app_version": "1.2.0",
  "locale": "zh",
  "theme": "system",
  "auto_check_update": true,
  "asr": {
    "default_model": "small",
    "default_language": "zh",
    "compute_type": "int8",
    "model_dir": "models",
    "vad_filter": true,
    "beam_size": 5
  },
  "keywords": {
    "library_path": "keywords/library.json",
    "warning_threshold": 300,
    "injection_enabled": true,
    "correction_enabled": true,
    "correction_policy": "balanced",
    "prompt_budget_chars": 260
  },
  "ai": {
    "default_provider_id": "uuid",
    "temperature": 0.2,
    "max_tokens": 4096,
    "timeout_seconds": 120,
    "max_retries": 3
  },
  "recorder": {
    "device_index": null,
    "output_format": "wav"
  },
  "data": {
    "trash_days": 30,
    "log_level": "INFO",
    "export_bom": false
  },
  "window": {
    "geometry": [1280, 800],
    "position": [200, 120],
    "sidebar_width": 260
  }
}
```

### 6.2 providers.json

```json
{
  "schema_version": 1,
  "providers": [
    {
      "id": "uuid",
      "name": "DeepSeek 主账号",
      "type": "openai_compatible",
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "__vault__:uuid",
      "model": "deepseek-chat",
      "temperature": 0.2,
      "max_tokens": 4096,
      "use_max_completion_tokens": false,
      "extra_headers": {},
      "enabled": true,
      "is_default": true
    },
    {
      "id": "uuid",
      "name": "Claude 官方",
      "type": "anthropic_native",
      "base_url": "https://api.anthropic.com/v1",
      "api_key": "__vault__:uuid",
      "model": "claude-sonnet-4-20250514",
      "max_tokens": 4096,
      "api_version_header": "2023-06-01"
    }
  ]
}
```

api_key 字段**只存占位符**，格式为 __vault__:{secret_id}，真实值存放在密钥库（见 [08 章](08-security.md)）。

### 6.3 keywords/library.json

```json
{
  "schema_version": 1,
  "groups": [
    {"id": "g1", "name": "人名", "order": 1, "color": "#4A90D9", "enabled": true},
    {"id": "g2", "name": "产品名", "order": 2, "color": "#34A853", "enabled": true},
    {"id": "g3", "name": "术语", "order": 3, "color": "#F9AB00", "enabled": true}
  ],
  "keywords": [
    {"id": "uuid", "text": "张一鸣", "group_id": "g1", "priority": 90, "enabled": true},
    {"id": "uuid", "text": "MeetRec Master", "group_id": "g2", "priority": 80, "enabled": true},
    {"id": "uuid", "text": "CTranslate2", "group_id": "g3", "priority": 60, "enabled": true}
  ]
}
```

---

## 7. Schema 版本与迁移

1. 所有 JSON 文件带 schema_version；library.db 的 meta 表存 schema_version。
2. 启动时比对版本，按顺序执行迁移函数（v1→v2→…），**不可跳级**。
3. 迁移前自动备份到 backups/config-{version}-{timestamp}.json（保留最近 5 份）。
4. 迁移失败 → 使用备份恢复并中文提示「配置迁移失败，已回滚到上一版本」；仍失败则使用内置默认配置并把原文件改名为 .broken 保留。
5. 迁移函数必须**幂等**（重复执行结果不变）。

---

## 8. 并发、锁与原子写

| 场景 | 机制 |
|---|---|
| SQLite | WAL + busy_timeout=5s；写操作用短事务 |
| 单实例 | 启动时创建锁文件（macOS 用 fcntl；Windows 用互斥体）；已运行则聚焦现有窗口 |
| 文件原子写 | 先写 .tmp，fsync，再 os.replace |
| 大文件写 | 分块流式写（音频、Markdown），进度可上报 |
| 模型下载 | 写 .part 文件 + 完成标记 .ok；启动时清理无 .ok 的 .part |

---

## 9. 回收站与清理

1. 删除会议 → 目录整体移到 trash/{timestamp}_{id}/，同时 meetings.trashed 置 1。
2. 回收站可**恢复**（移回并清 trashed）与**永久删除**（真实删除 + 删除索引行）。
3. 每日启动时清理超过 data.trash_days（默认 30 天）的回收站条目。
4. 「清除缓存」按钮仅删 cache/ 与 models/（可选），**不触碰** meetings/。
5. 磁盘占用统计：启动时惰性计算并缓存到 meta 表，5 分钟过期。

---

## 10. 磁盘占用与容量规划

| 内容 | 单场会议典型占用（50 分钟） |
|---|---|
| 原始音频（导入） | 10–50 MB |
| decoded.wav（16k mono s16） | 约 95 MB |
| transcript.json | 0.5–2 MB |
| summary Markdown | 50–200 KB |
| 合计 | 约 105–150 MB |

- 建议在 UI 显示每场会议的占用，并提供「删除解码音频，保留原文件」的瘦身选项。
- 应用数据总量超过 2 GB 时提示清理；超过 8 GB 时提示外部存储。
- ASR 模型缓存（small 约 480 MB、large-v3 约 3 GB）单独统计，不计入会议占用。

---

## 11. 相关文档

- [04 · 核心模块规格](04-core-modules.md)
- [08 · 安全规范](08-security.md)
- [10 · 打包 · CI · 完整性校验](10-packaging-ci-signing.md)




