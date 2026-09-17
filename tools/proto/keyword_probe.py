#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''MeetRec Master · 热词四阶段原型验证脚本

用途：在项目代码尚未实现前，独立验证「基线锚定 + 定向重解码」热词架构的效果。
对比三种方案：
  A. baseline     仅基线转写，不注入热词（对照组，得到召回率下界与基线 WER）
  B. legacy       旧方案：全局 initial_prompt 注入 + 后处理纠错
  C. four_stage   新方案：基线 → 缺口分析 → 定向重解码 → 后处理纠错

用法：
  python tools/proto/keyword_probe.py --audio meeting.wav \
      --keywords tools/proto/keywords.example.txt \
      --aliases  tools/proto/aliases.example.txt \
      --model large-v3-turbo

依赖：
  pip install faster-whisper pypinyin rapidfuzz av numpy

设计原则（与 docs/05-keyword-correction.md 一致）：
  · baseline 绝不注入热词 —— 普通文本 WER 退化严格为 0 的前提
  · 定向重解码只在候选区域的短片段上做 —— 片段越短，initial_prompt 偏置越强
  · 择优合并（D1–D5）失败则回退基线 —— 宁缺勿滥
'''

import argparse
import difflib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

TARGET_SR = 16000
PROMPT_BUDGET = 260
CONTEXT_PAD = 3.0
MAX_REGION_SEC = 60.0
BUDGET_RATIO = 0.15

# 标点集合（用 chr 避免引号字符，防止跨层转义问题）
PUNCT = set(",.;!?，。；！？、:：「」（）()[]~@#$%^&*+=<>/| \"\n\t") | {chr(34), chr(39)}


@dataclass
class Keyword:
    text: str
    group: str = '默认'
    aliases: tuple = ()
    expected_count: int = 0


@dataclass
class Region:
    start: float
    end: float
    reason: str
    score: float = 0.0


@dataclass
class PlanResult:
    name: str
    text: str
    elapsed: float
    detail: dict = field(default_factory=dict)
    hits: dict = field(default_factory=dict)
    corrections: list = field(default_factory=list)


# ==================== 音频 ====================

def load_audio(path: str) -> np.ndarray:
    '''PyAV 解码为 16kHz mono float32，faster-whisper 期望格式。'''
    import av
    container = av.open(path)
    try:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format='flt', layout='mono', rate=TARGET_SR)
        chunks = []
        for frame in container.decode(stream):
            for rf in resampler.resample(frame):
                chunks.append(rf.to_ndarray())
        duration = float(stream.duration * stream.time_base) if stream.duration else 0.0
    finally:
        container.close()
    if not chunks:
        raise RuntimeError('音频中没有可解码的音频流: ' + path)
    arr = np.concatenate([c.flatten() for c in chunks], axis=0).astype(np.float32)
    peak = float(np.abs(arr).max())
    if peak > 1.0:
        arr = arr / peak
    return arr


def slice_audio(audio: np.ndarray, start: float, end: float) -> np.ndarray:
    s = max(0, int(start * TARGET_SR))
    e = min(len(audio), int(end * TARGET_SR))
    return audio[s:e]


# ==================== 关键词 ====================

def load_keywords(args) -> list:
    texts = []
    if args.keywords_file:
        for line in Path(args.keywords_file).read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                texts.append(line)
    if args.keywords:
        texts.extend([t.strip() for t in args.keywords.split(',') if t.strip()])
    aliases = {}
    if args.aliases_file:
        for line in Path(args.aliases_file).read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 2 and parts[0]:
                aliases[parts[0]] = tuple(parts[1:])
    return [Keyword(text=t, aliases=aliases.get(t, ())) for t in texts]


# ==================== 相似度 ====================

def pinyin_of(s: str) -> str:
    if not s.strip():
        return ''
    try:
        from pypinyin import lazy_pinyin
        return ''.join(lazy_pinyin(s, errors=lambda c: c))
    except Exception:
        return s.lower()


def edit_sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    from rapidfuzz import fuzz
    return fuzz.ratio(a, b) / 100.0


def len_sim(a: str, b: str) -> float:
    la, lb = len(a), len(b)
    if la == 0 and lb == 0:
        return 1.0
    return 1.0 - abs(la - lb) / max(la, lb)


def pinyin_sim(a: str, b: str) -> float:
    pa, pb = pinyin_of(a), pinyin_of(b)
    if pa == '' and pb == '':
        return 0.0
    from rapidfuzz import fuzz
    return fuzz.token_sort_ratio(pa, pb) / 100.0


def similarity(a: str, b: str):
    ps = pinyin_sim(a, b)
    es = edit_sim(a, b)
    ls = len_sim(a, b)
    return 0.5 * ps + 0.3 * es + 0.2 * ls, ps, es, ls


def text_spans(text: str, max_len: int = 12):
    '''按标点切分后取候选片段；长片段用滑窗。'''
    parts, buf = [], []
    for ch in text:
        if ch in PUNCT:
            if buf:
                parts.append(''.join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append(''.join(buf))
    spans = []
    for p in parts:
        if len(p) < 2:
            continue
        if len(p) <= max_len:
            spans.append(p)
        else:
            for i in range(0, len(p) - 5, 2):
                spans.append(p[i:i + 6])
    return spans



# ==================== Prompt 构造 ====================

def build_prompt(keywords: list, language: str = 'zh', budget: int = PROMPT_BUDGET) -> str:
    '''按预算构造 initial_prompt。中文字符计 1，排序：分组顺序 → 原文稳定。'''
    if language == 'en':
        template = 'Keywords mentioned: {kw}. Use these exact spellings.'
        sep = ', '
    else:
        template = '会议中提到的关键词有：{kw}。请用这些准确写法记录。'
        sep = '、'
    fixed = len(template) - len('{kw}')
    avail = max(0, budget - fixed)
    picked, used = [], 0
    for kw in keywords:
        item = kw.text
        cost = len(item) + (len(sep) if picked else 0)
        if used + cost > avail:
            break
        picked.append(item)
        used += cost
    return template.format(kw=sep.join(picked) if picked else '无')


def group_relevance(keywords: list, segments, region) -> list:
    '''Stage 3 分组注入：按区域基线文本的相关度排序分组。'''
    text = ''.join(s.text for s in segments if s.start >= region.start - 1 and s.end <= region.end + 1)
    groups, hits = {}, {}
    for kw in keywords:
        g = kw.group
        groups.setdefault(g, []).append(kw)
        if kw.text in text:
            hits[g] = hits.get(g, 0) + 1
    return sorted(groups.keys(), key=lambda g: -hits.get(g, 0))


def keywords_of_group(keywords: list, group: str) -> list:
    return [k for k in keywords if k.group == group]


# ==================== 转写封装 ====================

def transcribe(model, audio, prompt=None, beam=5, vad=True, condition=True, language='zh'):
    kwargs = dict(
        language=language,
        beam_size=beam,
        best_of=5,
        temperature=(0.0, 0.2, 0.4, 0.6, 0.8),
        word_timestamps=True,
        vad_filter=vad,
        condition_on_previous_text=condition,
    )
    if prompt is not None:
        kwargs['initial_prompt'] = prompt
    result = model.transcribe(audio, **kwargs)
    # faster-whisper 1.2.x：transcribe() 返回 (segments 生成器, info) 元组；
    # 旧版本返回生成器本身。两者都要兼容。
    segs = result[0] if isinstance(result, tuple) else result
    return list(segs)


def seg_to_text(segments) -> str:
    return ''.join(s.text.strip() for s in segments)


def seg_problems(segments) -> dict:
    out = {}
    for s in segments:
        probs = [w.probability for w in (s.words or ()) if getattr(w, 'probability', None) is not None]
        out[s.start] = dict(avg_logprob=s.avg_logprob, no_speech_prob=s.no_speech_prob,
                            word_mean=sum(probs) / len(probs) if probs else None)
    return out


# ==================== Stage 1 · 基线 ====================

def stage1_baseline(model, audio, language='zh'):
    t0 = time.time()
    segments = transcribe(model, audio, prompt=None, beam=5, vad=True, condition=True, language=language)
    return segments, seg_to_text(segments), time.time() - t0


# ==================== Stage 2 · 缺口分析 ====================

def stage2_gaps(segments, keywords: list, audio_len: float, budget_ratio: float = BUDGET_RATIO):
    '''三路候选定位 + 合并 + 上下文扩展 + 预算裁剪。'''
    kws = [k for k in keywords if k.text]
    full_text = ''.join(s.text for s in segments)
    unmatched = [k for k in kws if k.text not in full_text]
    regions = []

    # R1 · 低置信区域
    for s in segments:
        if s.avg_logprob is not None and s.avg_logprob < -0.70:
            regions.append(Region(s.start, s.end, 'R1 低置信 logprob=' + str(round(s.avg_logprob, 3)), -s.avg_logprob))
        probs = [w.probability for w in (s.words or ()) if getattr(w, 'probability', None) is not None]
        if probs and sum(probs) / len(probs) < 0.75:
            regions.append(Region(s.start, s.end, 'R1 低词概率=' + str(round(sum(probs) / len(probs), 3)),
                                  1.0 - sum(probs) / len(probs)))

    # R2 · 疑似变体
    for s in segments:
        body = s.text.strip()
        if len(body) < 2:
            continue
        for k in unmatched:
            if len(k.text) < 2:
                continue
            ratio = len(body) / float(len(k.text))
            if ratio < 0.3 or ratio > 5.0:
                continue
            for span in text_spans(body):
                sc, ps, es, ls = similarity(span, k.text)
                lr = len(span) / float(len(k.text))
                if 0.5 <= lr <= 2.0 and ps >= 0.70 and sc >= 0.62:
                    regions.append(Region(s.start, s.end,
                                          'R2 疑似变体 ' + span + ' ~ ' + k.text + ' score=' + str(round(sc, 3)), sc))
                    break

    if not regions:
        return [], {}

    regions.sort(key=lambda r: -r.score)
    merged = []
    for r in regions:
        if merged and r.start <= merged[-1].end + 2.0:
            merged[-1].end = max(merged[-1].end, r.end)
        else:
            merged.append(Region(r.start, r.end, r.reason, r.score))

    for r in merged:
        r.start = max(0.0, r.start - CONTEXT_PAD)
        r.end = min(audio_len, r.end + CONTEXT_PAD)
        if r.end - r.start > MAX_REGION_SEC:
            r.end = r.start + MAX_REGION_SEC

    total_budget = audio_len * budget_ratio
    kept, used = [], 0.0
    for r in merged:
        d = r.end - r.start
        if used + d <= total_budget:
            kept.append(r)
            used += d
    detail = dict(candidates=len(merged), kept=len(kept), budget_sec=round(total_budget, 1),
                  used_sec=round(used, 1), regions=[(round(r.start, 2), round(r.end, 2), r.reason) for r in kept])
    return kept, detail



# ==================== Stage 3 · 定向重解码 ====================

def stage3_redecode(model, audio, baseline_segments, keywords: list, regions, language='zh'):
    '''对候选区域抽取 ±3s 片段，分组注入 initial_prompt，beam=10 重解码，D1–D5 择优合并。'''
    if not regions:
        return baseline_segments, []
    merged = list(baseline_segments)
    notes = []
    n_regions = len(regions)
    for idx, region in enumerate(regions, 1):
        start, end = region.start, region.end
        sub = slice_audio(audio, start, end)
        if len(sub) < TARGET_SR:
            notes.append((idx, start, end, 'skipped 片段过短', ''))
            continue
        order = group_relevance(keywords, baseline_segments, region)
        picked = []
        for g in order:
            picked.extend(keywords_of_group(keywords, g))
            if len(picked) >= 6:
                break
        if not picked:
            picked = keywords[:6]
        prompt = build_prompt(picked, language=language)
        re_segments = transcribe(model, sub, prompt=prompt, beam=10, vad=False, condition=False, language=language)
        base_seg = [s for s in baseline_segments if s.start >= start - 1 and s.end <= end + 1]
        base_text = ''.join(s.text for s in base_seg)
        re_text = ''.join(s.text for s in re_segments)
        if not re_text.strip():
            notes.append((idx, start, end, 'skipped 重解码空文本', prompt))
            continue
        base_lp = min([s.avg_logprob for s in base_seg if s.avg_logprob is not None], default=0.0)
        re_lp = min([s.avg_logprob for s in re_segments if s.avg_logprob is not None], default=0.0)
        new_kw = [k.text for k in picked if k.text in re_text and k.text not in base_text]
        if not new_kw:
            notes.append((idx, start, end, 'D4 无关键词增益，保留基线', prompt))
            continue
        if re_lp < base_lp - 0.10:
            notes.append((idx, start, end, 'D2 logprob 劣化 %.2f，保留基线' % (base_lp - re_lp), prompt))
            continue
        dist = edit_sim(base_text, re_text)
        if dist > 0.50:
            notes.append((idx, start, end, 'D3 差异 %.2f 过大，保留基线' % (1 - dist), prompt))
            continue
        # 采用重解码：替换该区间的基线 segment
        merged = [s for s in merged if not (s.start >= start - 1 and s.end <= end + 1)]
        offset = start - (regions[idx - 1].start if idx == 1 else regions[idx - 1].start)
        for js, s in enumerate(re_segments):
            merged.append(_Reseg(start + s.start, start + s.end, s.text,
                                 getattr(s, 'avg_logprob', re_lp), getattr(s, 'no_speech_prob', 0.0),
                                 tuple(s.words or ())))
        merged.sort(key=lambda s: s.start)
        notes.append((idx, start, end, '采用（引入 ' + '、'.join(new_kw) + '）', prompt))
    return merged, notes


class _Reseg:
    '''重解码片段重建的轻量 segment（结构与 faster-whisper Segment 对齐所需字段）。'''
    __slots__ = ('start', 'end', 'text', 'avg_logprob', 'no_speech_prob', 'words', 'id')

    def __init__(self, start, end, text, avg_logprob, no_speech_prob, words):
        self.start = float(start)
        self.end = float(end)
        self.text = text
        self.avg_logprob = avg_logprob
        self.no_speech_prob = no_speech_prob
        self.words = words
        self.id = None


# ==================== Stage 4 · 后处理纠错 ====================

def stage4_correct(text: str, keywords: list, policy='balanced'):
    '''别名精确匹配优先，其次模糊匹配（拼音+编辑距离+长度），带门控。'''
    thresholds = {
        'conservative': (0.86, 0.88, 0.78),
        'balanced': (0.78, 0.92, 0.70),
        'aggressive': (0.70, 0.95, 0.60),
    }[policy]
    m1, m4, m2 = thresholds
    corrections = []
    final = text
    covered = set()

    # 别名精确匹配（置信度 1.0，跳过门控）
    for kw in keywords:
        for alias in kw.aliases:
            if len(alias) < 1 or len(alias) > 30:
                continue
            start = 0
            while True:
                i = final.find(alias, start)
                if i < 0:
                    break
                corrections.append(dict(before=alias, after=kw.text, offset=i, length=len(alias),
                                        score=1.0, kind='alias', source='stage4'))
                covered.add((i, len(alias)))
                start = i + len(alias)

    # 模糊匹配
    spans = text_spans(final)
    for span in spans:
        if any(abs(pos - p) < max(len(span), len(covered_span)) for (pos, covered_span) in covered):
            continue
        for kw in keywords:
            if len(kw.text) < 2:
                continue
            sc, ps, es, ls = similarity(span, kw.text)
            lr = len(span) / float(len(kw.text))
            # 禁止规则：数字 / 专有符号 / 长度比
            if (any(c.isdigit() for c in span) and not any(c.isdigit() for c in kw.text)):
                continue
            if any(c in '%.-' for c in span) and not any(c in '%.-' for c in kw.text):
                continue
            if not (0.6 <= lr <= 1.8):
                continue
            if sc < m1:
                continue
            if len(kw.text) <= 2 and ps < 0.90:
                continue
            if ps < m2:
                continue
            corrections.append(dict(before=span, after=kw.text, offset=final.find(span),
                                    length=len(span), score=round(sc, 4), kind='fuzzy',
                                    source='stage4', pinyin=round(ps, 3), edit=round(es, 3)))
            break

    # 应用修正（从后往前，避免 offset 错位）
    corrections.sort(key=lambda c: -c['offset'])
    for c in corrections:
        o, L = c['offset'], c['length']
        if 0 <= o <= len(final) and final[o:o + L] == c['before']:
            final = final[:o] + c['after'] + final[o + L:]
    return final, corrections



# ==================== 命中统计 ====================

def count_hits(text, keywords):
    out = {}
    for kw in keywords:
        n = text.count(kw.text)
        for a in kw.aliases:
            n += text.count(a)
        out[kw.text] = n
    return out



# ==================== 零退化校验 ====================

def diff_spans(a: str, b: str):
    '''字符级差异区间。返回 op / a区间 / b区间 / 两侧文本。'''
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != 'equal':
            out.append(dict(op=tag, a_start=i1, a_end=i2, b_start=j1, b_end=j2,
                            a_text=a[i1:i2], b_text=b[j1:j2]))
    return out


def keyword_index(keywords) -> list:
    items = [k.text for k in keywords if k.text]
    for k in keywords:
        for a in k.aliases:
            if a:
                items.append(a)
    return items


def classify_diffs(a: str, b: str, keywords) -> dict:
    '''把 A→C 的差异分成「可归因于关键词」与「非关键词改动」。

    零退化成立的条件：非关键词改动为 0。
    因为 C 的普通文本来自 A 的基线，凡是关键词引入的差异都应能被关键词索引命中。
    '''
    spans = diff_spans(a, b)
    idx = keyword_index(keywords)
    kw_related, other = [], []
    for sp in spans:
        hit = [w for w in idx if w in sp['b_text'] or w in sp['a_text']]
        sp = dict(sp, keywords=hit)
        if hit:
            kw_related.append(sp)
        else:
            other.append(sp)
    return dict(total=len(spans), keyword_related=len(kw_related),
                other=len(other), keyword_spans=kw_related, other_spans=other)



def recall_of(hits, keywords):
    total_gt = 0
    total_hit = 0
    for kw in keywords:
        if kw.expected_count > 0:
            total_gt += kw.expected_count
            total_hit += min(hits.get(kw.text, 0), kw.expected_count)
    if total_gt == 0:
        return None
    return total_hit / float(total_gt)


# ==================== 报告 ====================

def write_report(path, audio_path, audio_len, model_name, keywords, plans, gaps_detail, re_notes):
    lines = []
    lines.append('# 热词原型验证报告')
    lines.append('')
    lines.append('- 音频：' + audio_path)
    lines.append('- 音频时长：%.1f 秒' % audio_len)
    lines.append('- 模型：' + model_name)
    lines.append('- 关键词数：%d（含别名 %d 条）' % (len(keywords), sum(len(k.aliases) for k in keywords)))
    lines.append('- 生成时间：' + time.strftime('%Y-%m-%d %H:%M:%S'))
    lines.append('')
    lines.append('## 汇总对比')
    lines.append('')
    lines.append('| 方案 | 关键词命中数 | 召回率 | 耗时 | 自动改动数 |')
    lines.append('|---|---|---|---|---|')
    for p in plans:
        n = sum(p.hits.values())
        rc = recall_of(p.hits, keywords)
        rc_s = '不适用（未提供 expected_count）' if rc is None else '%.1f%%' % (rc * 100)
        lines.append('| ' + p.name + ' | ' + str(n) + ' | ' + rc_s + ' | %.1f s | %d |'
                     % (p.elapsed, len(p.corrections)))
    lines.append('')
    lines.append('## 逐关键词命中')
    lines.append('')
    header = '| 关键词 | 期望次数 |'
    sep = '|---|---|'
    for p in plans:
        header = header + ' ' + p.name + ' |'
        sep = sep + '---|'
    lines.append(header)
    lines.append(sep)
    for kw in keywords:
        row = '| ' + kw.text + ' | ' + (str(kw.expected_count) if kw.expected_count else '-') + ' |'
        for p in plans:
            row = row + ' ' + str(p.hits.get(kw.text, 0)) + ' |'
        lines.append(row)
    lines.append('')
    lines.append('## 缺口分析（Stage 2）')
    lines.append('')
    lines.append('- 候选区域：%d → 保留 %d（预算 %.1f s / 实际 %.1f s）'
                 % (gaps_detail.get('candidates', 0), gaps_detail.get('kept', 0),
                    gaps_detail.get('budget_sec', 0), gaps_detail.get('used_sec', 0)))
    for i, item in enumerate(gaps_detail.get('regions', []), 1):
        lines.append('  %d. [%.1f-%.1f] %s' % (i, item[0], item[1], item[2]))
    lines.append('')
    lines.append('## 定向重解码决策（Stage 3）')
    lines.append('')
    for idx, s, e, decision, prompt in re_notes:
        lines.append('- 区域 %d [%.1f-%.1f]：%s' % (idx, s, e, decision))
        if prompt:
            lines.append('  - 注入 prompt（%d 字符）：' % len(prompt))
            lines.append('    ' + prompt)
    if not re_notes:
        lines.append('- 无候选区域，Stage 3 未执行')
    lines.append('')
    lines.append('## 自动改动明细')
    lines.append('')
    for p in plans:
        if not p.corrections:
            continue
        lines.append('### ' + p.name)
        lines.append('')
        lines.append('| # | 原文 | 改为 | 来源 | 置信度 |')
        lines.append('|---|---|---|---|---|')
        for i, c in enumerate(sorted(p.corrections, key=lambda x: x['offset']), 1):
            lines.append('| %d | %s | %s | %s | %s |'
                         % (i, c['before'], c['after'], c.get('kind', '?'), c['score']))
        lines.append('')
    lines.append('## 全文对照')
    lines.append('')
    for p in plans:
        lines.append('### ' + p.name)
        lines.append('')
        lines.append('```text')
        lines.append(p.text)
        lines.append('```')
        lines.append('')
    lines.append('')
    lines.append('## 全文对照')
    lines.append('')
    for p in plans:
        lines.append('### ' + p.name)
        lines.append('')
        lines.append('```text')
        lines.append(p.text)
        lines.append('```')
        lines.append('')

    lines.append('')
    lines.append('## 零退化校验（A 基线 vs C 四阶段）')
    lines.append('')
    planA_text = plans[0].text
    planB_text = plans[1].text
    planC = plans[2]
    z = classify_diffs(planA_text, planC.text, keywords)
    lines.append('- 差异区间总数：%d' % z['total'])
    lines.append('- 可归因于关键词的差异：%d' % z['keyword_related'])
    lines.append('- **非关键词改动：%d**' % z['other'])
    if z['other'] == 0:
        lines.append('')
        lines.append('**结论：零退化成立 —— C 的普通文本与 A 基线逐字一致，全部差异都由关键词引入。**')
    else:
        lines.append('')
        lines.append('**警告：发现 %d 处非关键词改动，需要排查 Stage 3 合并或 Stage 4 门控。**' % z['other'])
        for sp in z['other_spans']:
            lines.append('  - [A:%d-%d → C:%d-%d] %s → %s'
                         % (sp['a_start'], sp['a_end'], sp['b_start'], sp['b_end'],
                            repr(sp['a_text'])[:60], repr(sp['b_text'])[:60]))
    lines.append('')
    lines.append('## 零退化校验（A 基线 vs B 旧方案）')
    lines.append('')
    zb = classify_diffs(planA_text, planB_text, keywords)
    lines.append('- 差异区间总数：%d' % zb['total'])
    lines.append('- 可归因于关键词的差异：%d' % zb['keyword_related'])
    lines.append('- **非关键词改动：%d** ← 这是旧方案的副作用' % zb['other'])
    lines.append('')

    Path(path).write_text(''.join(l + chr(10) for l in lines), encoding='utf-8')
    return path



# ==================== 主流程 ====================

def run(args):
    audio = load_audio(args.audio)
    audio_len = len(audio) / float(TARGET_SR)
    keywords = load_keywords(args)
    if not keywords:
        print('错误：没有关键词。用 --keywords "张一鸣,CTranslate2" 或 --keywords-file 提供', file=sys.stderr)
        return 2

    print('加载模型 ' + args.model + ' ...', file=sys.stderr)
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)

    lang = args.language
    print('Stage 1 · 基线转写（不注入热词）', file=sys.stderr)
    segs, base_text, t_base = stage1_baseline(model, audio, lang)

    planA = PlanResult('A 仅基线', base_text, t_base,
                       detail=dict(segments=len(segs)), hits=count_hits(base_text, keywords))

    print('方案 B · 旧方案：全局 initial_prompt 注入', file=sys.stderr)
    t0 = time.time()
    legacy_prompt = build_prompt(keywords, lang)
    legacy_segs = transcribe(model, audio, prompt=legacy_prompt, beam=5, vad=True, condition=True, language=lang)
    legacy_text = seg_to_text(legacy_segs)
    legacy_text, legacy_corr = stage4_correct(legacy_text, keywords, args.policy)
    planB = PlanResult('B 旧方案（全局注入）', legacy_text, time.time() - t0,
                       detail=dict(prompt_len=len(legacy_prompt)), hits=count_hits(legacy_text, keywords),
                       corrections=legacy_corr)

    print('Stage 2 · 缺口分析', file=sys.stderr)
    regions, gaps_detail = stage2_gaps(segs, keywords, audio_len)
    print('Stage 3 · 定向重解码（%d 个区域）' % len(regions), file=sys.stderr)
    t0 = time.time()
    merged_segs, re_notes = stage3_redecode(model, audio, segs, keywords, regions, lang)
    merged_text = seg_to_text(merged_segs)
    print('Stage 4 · 后处理纠错', file=sys.stderr)
    final_text, final_corr = stage4_correct(merged_text, keywords, args.policy)
    t_c = time.time() - t0
    planC = PlanResult('C 四阶段（基线+定向重解码）', final_text, t_base + t_c,
                       detail=dict(regions=len(regions), gap_candidates=gaps_detail.get('candidates', 0)),
                       hits=count_hits(final_text, keywords), corrections=final_corr)

    plans = [planA, planB, planC]
    report_path = args.report or ('tools/proto/report-' + time.strftime('%Y%m%d-%H%M%S') + '.md')
    write_report(report_path, args.audio, audio_len, args.model, keywords, plans, gaps_detail, re_notes)

    print('')
    print('=' * 60)
    for p in plans:
        n = sum(p.hits.values())
        print('  %-28s 命中 %3d  耗时 %6.1f s  改动 %d' % (p.name, n, p.elapsed, len(p.corrections)))
    print('=' * 60)
    a_hit = sum(planA.hits.values())
    c_hit = sum(planC.hits.values())
    print('热词增益（C - A）：%+d 个关键词命中' % (c_hit - a_hit))

    z = classify_diffs(planA.text, planC.text, keywords)
    zb = classify_diffs(planA.text, planB.text, keywords)
    print('-' * 60)
    print('零退化校验')
    print('  C 四阶段：差异 %d 处，关键词相关 %d，非关键词改动 %d'
          % (z['total'], z['keyword_related'], z['other']))
    print('  B 旧方案：差异 %d 处，关键词相关 %d，非关键词改动 %d'
          % (zb['total'], zb['keyword_related'], zb['other']))
    if z['other'] == 0:
        print('  >>> C 方案零退化成立：普通文本与基线逐字一致')
    else:
        print('  >>> 警告：C 方案存在 %d 处非关键词改动，见报告排查' % z['other'])
    print('报告：' + report_path)
    return 0


def main():
    ap = argparse.ArgumentParser(description='MeetRec Master 热词四阶段原型验证')
    ap.add_argument('--audio', required=True, help='音频文件路径（WAV/MP3/M4A/AAC/FLAC）')
    ap.add_argument('--keywords', help='逗号分隔的关键词列表')
    ap.add_argument('--keywords-file', dest='keywords_file', help='关键词文件，每行一个')
    ap.add_argument('--aliases-file', dest='aliases_file', help='别名文件，每行：关键词|别名1|别名2')
    ap.add_argument('--model', default='large-v3-turbo',
                    choices=['tiny', 'base', 'small', 'medium', 'large-v3', 'large-v3-turbo'])
    ap.add_argument('--device', default='cpu', choices=['cpu', 'cuda'])
    ap.add_argument('--compute-type', dest='compute_type', default='int8',
                    choices=['int8', 'float16', 'float32', 'int8_float16'])
    ap.add_argument('--language', default='zh', choices=['zh', 'en'])
    ap.add_argument('--policy', default='balanced',
                    choices=['conservative', 'balanced', 'aggressive'])
    ap.add_argument('--report', help='报告输出路径')
    args = ap.parse_args()
    try:
        return run(args)
    except Exception as e:
        print('执行失败：' + str(e), file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())





