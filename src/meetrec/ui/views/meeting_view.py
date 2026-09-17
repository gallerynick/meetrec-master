"""会议详情页 — 五步流程（录音/导入 → 转写 → 校对 → 纪要 → 导出）。

M2–M6 的 UI 接线层。参考 Hyprnote 的干净卡片式设计：
- 分步卡片布局，圆角 + 微妙边框
- 录音状态指示灯（红点闪烁）
- 进度条与状态文本
- 每步完成后自动点亮下一步

五步流程与 docs/09-ui-design-spec.md §3.2 对齐：
    录音/导入 → 转写 → 关键词校对 → 生成纪要 → 导出
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from meetrec.models import Meeting
from meetrec.ui.flow_bar import FlowBar, StepState
from meetrec.ui.service import MeetingService
from meetrec.ui.workers import Worker

__all__ = ["MeetingView"]

_log = logging.getLogger(__name__)


class MeetingView(QFrame):
    """单次会议的五步流程详情页。

    通过 MeetingService 协调录音、转写、校对、纪要、导出的完整工作流。
    """

    step_content_changed = Signal(int)

    def __init__(self, service: MeetingService, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._meeting: Meeting | None = None
        self._worker: Worker | None = None
        self._recording_timer = QTimer(self)
        self._recording_timer.setInterval(100)
        self._recording_timer.timeout.connect(self._on_recording_tick)
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = QVBoxLayout()
        header.setSpacing(4)
        self._title_label = QLabel("新会议")
        self._title_labelstylesheet = "font-size: 18px; font-weight: 600;"
        self._title_label.setStyleSheet(self._title_labelstylesheet)
        self._flow_bar = FlowBar()
        self._flow_bar.step_selected.connect(self._on_step_selected)
        header.addWidget(self._title_label)
        header.addWidget(self._flow_bar)
        layout.addLayout(header)

        self._stack = QStackedWidget()
        self._step1 = self._build_step1()
        self._step2 = self._build_step2()
        self._step3 = self._build_step3()
        self._step4 = self._build_step4()
        self._step5 = self._build_step5()
        self._stack.addWidget(self._step1)
        self._stack.addWidget(self._step2)
        self._stack.addWidget(self._step3)
        self._stack.addWidget(self._step4)
        self._stack.addWidget(self._step5)
        layout.addWidget(self._stack, 1)

    def _build_step1(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("会议标题："))
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("输入会议标题…")
        title_row.addWidget(self._title_edit, 1)
        layout.addLayout(title_row)

        rec_card = QFrame()
        rec_card.setObjectName("card")
        rec_layout = QVBoxLayout(rec_card)
        rec_layout.setSpacing(8)
        rec_layout.setContentsMargins(16, 12, 16, 12)

        rec_controls = QHBoxLayout()
        self._record_btn = QPushButton("● 开始录音")
        self._record_btn.setFixedHeight(36)
        self._record_btn.clicked.connect(self._toggle_recording)

        self._duration_label = QLabel("00:00")
        self._duration_label.setStyleSheet("font-size: 20px; font-weight: 600; font-family: 'SF Mono', Menlo, Consolas, monospace;")
        rec_controls.addWidget(self._record_btn)
        rec_controls.addWidget(self._duration_label)
        rec_controls.addStretch(1)
        rec_layout.addLayout(rec_controls)

        self._level_bar = QProgressBar()
        self._level_bar.setRange(0, 100)
        self._level_bar.setTextVisible(False)
        self._level_bar.setFixedHeight(6)
        self._level_bar.setStyleSheet(
            "QProgressBar { border: none; border-radius: 3px; background: transparent; } "
            "QProgressBar::chunk { border-radius: 3px; background: #0A84FF; }"
        )
        rec_layout.addWidget(self._level_bar)
        layout.addWidget(rec_card)

        imp_card = QFrame()
        imp_card.setObjectName("card")
        imp_layout = QVBoxLayout(imp_card)
        imp_layout.setSpacing(8)
        imp_layout.setContentsMargins(16, 12, 16, 12)
        imp_layout.addWidget(QLabel("或导入音频文件"))
        imp_controls = QHBoxLayout()
        self._import_btn = QPushButton("选择文件…")
        self._import_btn.clicked.connect(self._import_audio)
        self._audio_path_label = QLabel("")
        self._audio_path_labelstylesheet = "color: #6E6E73; font-size: 12px;"
        self._audio_path_label.setStyleSheet(self._audio_path_labelstylesheet)
        imp_controls.addWidget(self._import_btn)
        imp_controls.addWidget(self._audio_path_label, 1)
        imp_layout.addLayout(imp_controls)
        layout.addWidget(imp_card)
        layout.addStretch(1)
        return w

    def _build_step2(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("模型："))
        self._model_combo = QComboBox()
        for size in ["tiny", "base", "small", "medium", "large-v3-turbo", "large-v3"]:
            display = {
                "tiny": "Tiny (75M, 最快)",
                "base": "Base (145M, 推荐)",
                "small": "Small (250M)",
                "medium": "Medium (770M)",
                "large-v3-turbo": "Large-v3-turbo (809M, 最佳)",
                "large-v3": "Large-v3 (1550M)",
            }.get(size, size)
            self._model_combo.addItem(display, size)
        self._model_combo.setCurrentIndex(1)
        model_row.addWidget(self._model_combo, 1)
        layout.addLayout(model_row)

        self._transcribe_btn = QPushButton("开始转写")
        self._transcribe_btn.setFixedHeight(36)
        self._transcribe_btn.clicked.connect(self._start_transcribe)
        layout.addWidget(self._transcribe_btn)

        self._transcribe_progress = QProgressBar()
        self._transcribe_progress.setRange(0, 0)
        self._transcribe_progress.setVisible(False)
        self._transcribe_progress.setFixedHeight(8)
        layout.addWidget(self._transcribe_progress)

        self._transcribe_status = QLabel("")
        self._transcribe_statusstylesheet = "color: #6E6E73; font-size: 12px;"
        self._transcribe_status.setStyleSheet(self._transcribe_statusstylesheet)
        layout.addWidget(self._transcribe_status)

        layout.addWidget(QLabel("转写结果："))
        self._transcript_edit = QPlainTextEdit()
        self._transcript_edit.setReadOnly(True)
        self._transcript_edit.setPlaceholderText("转写结果将显示在这里…")
        layout.addWidget(self._transcript_edit, 1)
        return w

    def _build_step3(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        hotword_row = QHBoxLayout()
        hotword_row.addWidget(QLabel("热词文件："))
        self._hotword_path_edit = QLineEdit()
        self._hotword_path_edit.setPlaceholderText("选择热词文件…")
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._browse_hotword_file)
        self._correct_btn = QPushButton("开始校对")
        self._correct_btn.setFixedHeight(36)
        self._correct_btn.clicked.connect(self._start_correct)
        hotword_row.addWidget(self._hotword_path_edit, 1)
        hotword_row.addWidget(browse_btn)
        hotword_row.addWidget(self._correct_btn)
        layout.addLayout(hotword_row)

        self._correction_label = QLabel("")
        self._correction_labelstylesheet = "color: #6E6E73; font-size: 12px;"
        self._correction_label.setStyleSheet(self._correction_labelstylesheet)
        layout.addWidget(self._correction_label)

        compare = QHBoxLayout()
        orig_card = QFrame()
        orig_card.setObjectName("card")
        orig_layout = QVBoxLayout(orig_card)
        orig_layout.setSpacing(4)
        orig_layout.setContentsMargins(12, 8, 12, 8)
        orig_layout.addWidget(QLabel("原文"))
        self._original_edit = QPlainTextEdit()
        self._original_edit.setReadOnly(True)
        orig_layout.addWidget(self._original_edit, 1)
        compare.addWidget(orig_card, 1)

        corr_card = QFrame()
        corr_card.setObjectName("card")
        corr_layout = QVBoxLayout(corr_card)
        corr_layout.setSpacing(4)
        corr_layout.setContentsMargins(12, 8, 12, 8)
        corr_layout.addWidget(QLabel("校对后"))
        self._corrected_edit = QPlainTextEdit()
        self._corrected_edit.setReadOnly(True)
        corr_layout.addWidget(self._corrected_edit, 1)
        compare.addWidget(corr_card, 1)
        layout.addLayout(compare, 1)
        return w

    def _build_step4(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        provider_row = QHBoxLayout()
        provider_row.addWidget(QLabel("AI 服务："))
        self._provider_combo = QComboBox()
        for name in ["openai", "anthropic", "deepseek"]:
            self._provider_combo.addItem(name, name)
        provider_row.addWidget(self._provider_combo, 1)
        layout.addLayout(provider_row)

        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("API Key："))
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("输入 API Key…")
        load_key_btn = QPushButton("从保险库加载")
        load_key_btn.clicked.connect(self._load_api_key)
        key_row.addWidget(self._api_key_edit, 1)
        key_row.addWidget(load_key_btn)
        layout.addLayout(key_row)

        layout.addWidget(QLabel("额外指令（可选）："))
        self._instructions_edit = QPlainTextEdit()
        self._instructions_edit.setPlaceholderText("例如：请重点突出行动项…")
        self._instructions_edit.setFixedHeight(60)
        layout.addWidget(self._instructions_edit)

        self._summarize_btn = QPushButton("生成纪要")
        self._summarize_btn.setFixedHeight(36)
        self._summarize_btn.clicked.connect(self._start_summarize)
        layout.addWidget(self._summarize_btn)

        self._summarize_status = QLabel("")
        self._summarize_statusstylesheet = "color: #6E6E73; font-size: 12px;"
        self._summarize_status.setStyleSheet(self._summarize_statusstylesheet)
        layout.addWidget(self._summarize_status)

        layout.addWidget(QLabel("AI 纪要："))
        self._summary_edit = QPlainTextEdit()
        self._summary_edit.setReadOnly(True)
        self._summary_edit.setPlaceholderText("纪要内容将显示在这里…")
        layout.addWidget(self._summary_edit, 1)
        return w

    def _build_step5(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.addWidget(QLabel("导出为 Markdown 文件"))

        self._export_btn = QPushButton("导出")
        self._export_btn.setFixedHeight(36)
        self._export_btn.clicked.connect(self._export_meeting)
        layout.addWidget(self._export_btn)

        self._export_path_label = QLabel("")
        self._export_path_labelstylesheet = "color: #6E6E73; font-size: 12px;"
        self._export_path_label.setStyleSheet(self._export_path_labelstylesheet)
        layout.addWidget(self._export_path_label)

        self._open_file_btn = QPushButton("打开文件")
        self._open_file_btn.setEnabled(False)
        self._open_file_btn.setFixedHeight(32)
        self._open_file_btn.clicked.connect(self._open_exported_file)
        layout.addWidget(self._open_file_btn)
        layout.addStretch(1)
        return w

    # -------------------------------------------------------- FlowBar 交互

    def _on_step_selected(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    def _update_flow_bar(self) -> None:
        m = self._meeting
        if m is None:
            return
        states = []
        if m.has_audio():
            states.append(StepState.DONE)
        else:
            states.append(StepState.ACTIVE)
        if m.has_transcript():
            states.append(StepState.DONE)
        elif m.has_audio():
            states.append(StepState.ACTIVE)
        else:
            states.append(StepState.PENDING)
        if m.has_corrected():
            states.append(StepState.DONE)
        elif m.has_transcript():
            states.append(StepState.ACTIVE)
        else:
            states.append(StepState.PENDING)
        if m.has_summary():
            states.append(StepState.DONE)
        elif m.has_corrected() or m.has_transcript():
            states.append(StepState.ACTIVE)
        else:
            states.append(StepState.PENDING)
        if m.status == "exported":
            states.append(StepState.DONE)
        elif m.has_audio() or m.has_transcript():
            states.append(StepState.ACTIVE)
        else:
            states.append(StepState.PENDING)
        for i, s in enumerate(states):
            self._flow_bar.set_state(i + 1, s)

    # ----------------------------------------------------------- 公开 API

    def load_meeting(self, meeting: Meeting) -> None:
        self._meeting = meeting
        self._title_label.setText(meeting.display_title)
        self._title_edit.setText(meeting.title)
        if meeting.audio_path:
            self._audio_path_label.setText(str(meeting.audio_path))
            self._audio_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if meeting.transcript:
            self._transcript_edit.setPlainText(meeting.transcript)
            self._transcribe_btn.setEnabled(False)
        if meeting.hotwords:
            self._original_edit.setPlainText(meeting.transcript or "")
            self._corrected_edit.setPlainText(meeting.corrected_transcript or "")
            self._correction_label.setText("已校对")
        if meeting.summary:
            self._summary_edit.setPlainText(meeting.summary)
            self._summarize_btn.setEnabled(False)
        if meeting.provider:
            idx = self._provider_combo.findData(meeting.provider)
            if idx >= 0:
                self._provider_combo.setCurrentIndex(idx)
        if meeting.status == "exported":
            self._open_file_btn.setEnabled(True)
        self._update_flow_bar()
        self.step_content_changed.emit(0)

    def new_meeting(self) -> None:
        self._meeting = self._service.create_meeting("新会议")
        self._title_label.setText("新会议")
        self._title_edit.clear()
        self._audio_path_label.clear()
        self._transcript_edit.clear()
        self._original_edit.clear()
        self._corrected_edit.clear()
        self._summary_edit.clear()
        self._correction_label.clear()
        self._summarize_status.clear()
        self._export_path_label.clear()
        self._open_file_btn.setEnabled(False)
        self._record_btn.setText("● 开始录音")
        self._record_btn.setStyleSheet("")
        self._duration_label.setText("00:00")
        self._level_bar.setValue(0)
        self._transcribe_btn.setEnabled(True)
        self._transcribe_btn.setText("开始转写")
        self._transcribe_progress.setVisible(False)
        self._transcribe_status.clear()
        self._summarize_btn.setEnabled(True)
        self._summarize_btn.setText("生成纪要")
        self._flow_bar.set_state(1, StepState.ACTIVE)
        self._flow_bar.set_state(2, StepState.PENDING)
        self._flow_bar.set_state(3, StepState.PENDING)
        self._flow_bar.set_state(4, StepState.PENDING)
        self._flow_bar.set_state(5, StepState.PENDING)
        self._stack.setCurrentIndex(0)

    def flow_bar(self) -> FlowBar:
        return self._flow_bar

    # --------------------------------------------------------- Step 1: 录音

    def _toggle_recording(self) -> None:
        if self._service.recorder.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        m = self._meeting
        if m is None:
            QMessageBox.warning(self, "错误", "请先创建或选择会议")
            return
        try:
            self._service.start_recording(m)
        except Exception as e:
            QMessageBox.critical(self, "录音失败", str(e))
            return
        self._record_btn.setText("■ 停止录音")
        self._record_btnstylesheet = "background: #FF3B30; color: white; border-radius: 8px; font-weight: 600;"
        self._record_btn.setStyleSheet(self._record_btnstylesheet)
        self._recording_timer.start()
        self._audio_path_label.setText("正在录音…")

    def _stop_recording(self) -> None:
        m = self._meeting
        if m is None:
            return
        try:
            path = self._service.stop_recording(m)
        except Exception as e:
            QMessageBox.critical(self, "停止录音失败", str(e))
            self._recording_timer.stop()
            return
        self._recording_timer.stop()
        self._record_btn.setText("● 开始录音")
        self._record_btnstylesheet = ""
        self._record_btn.setStyleSheet(self._record_btnstylesheet)
        self._audio_path_label.setText(str(path))
        self._audio_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._level_bar.setValue(0)
        self._title_edit.setText(m.title)
        self._update_flow_bar()

    def _on_recording_tick(self) -> None:
        rec = self._service.recorder
        dur = rec.duration
        mins = int(dur) // 60
        secs = int(dur) % 60
        self._duration_label.setText(f"{mins:02d}:{secs:02d}")
        self._level_bar.setValue(int(rec.level * 100))

    def _import_audio(self) -> None:
        m = self._meeting
        if m is None:
            QMessageBox.warning(self, "错误", "请先创建或选择会议")
            return
        path, _ = QFileDialog.getOpenFileName(self, "选择音频文件", "", "音频文件 (*.wav *.mp3 *.m4a *.aac *.flac *.ogg);;所有文件 (*)")
        if not path:
            return
        try:
            self._service.import_audio(m, path)
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))
            return
        self._audio_path_label.setText(str(path))
        self._audio_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._update_flow_bar()

    # --------------------------------------------------------- Step 2: 转写

    def _start_transcribe(self) -> None:
        m = self._meeting
        if m is None:
            QMessageBox.warning(self, "错误", "请先创建或选择会议")
            return
        if not m.has_audio():
            QMessageBox.warning(self, "提示", "请先录音或导入音频")
            return
        model_size = self._model_combo.currentData()
        self._transcribe_btn.setEnabled(False)
        self._transcribe_progress.setVisible(True)
        self._transcribe_status.setText("正在转写…")
        self._worker = Worker(self._service.transcribe, m, model_size)
        self._worker.progress.connect(self._update_progress)
        self._worker.result_ready.connect(self._on_transcribe_done)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _update_progress(self, msg: str) -> None:
        self._transcribe_status.setText(msg)

    def _on_transcribe_done(self, result) -> None:
        self._transcribe_btn.setEnabled(True)
        self._transcribe_progress.setVisible(False)
        self._transcribe_status.setText("转写完成")
        m = self._meeting
        if m is not None and result is not None:
            m.transcript = result.text
            m.duration = result.duration
            m.model_size = self._model_combo.currentData()
            self._service.update_meeting(m)
            self._transcript_edit.setPlainText(result.text)
            self._update_flow_bar()

    # --------------------------------------------------------- Step 3: 校对

    def _browse_hotword_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择热词文件", "", "文本文件 (*.txt);;所有文件 (*)")
        if path:
            self._hotword_path_edit.setText(path)

    def _start_correct(self) -> None:
        m = self._meeting
        if m is None:
            QMessageBox.warning(self, "错误", "请先创建或选择会议")
            return
        if not m.has_transcript():
            QMessageBox.warning(self, "提示", "请先完成转写")
            return
        hotword_path = self._hotword_path_edit.text().strip()
        if not hotword_path:
            QMessageBox.warning(self, "提示", "请选择热词文件")
            return
        try:
            from meetrec.keywords.loader import KeywordLoader
            hotwords = KeywordLoader().load_from_file(Path(hotword_path))
        except Exception as e:
            QMessageBox.critical(self, "加载热词失败", str(e))
            return
        try:
            result = self._service.correct(m, hotwords)
        except Exception as e:
            QMessageBox.critical(self, "校对失败", str(e))
            return
        m.corrected_transcript = result.text
        m.hotwords = hotwords
        self._service.update_meeting(m)
        self._original_edit.setPlainText(m.transcript or "")
        self._corrected_edit.setPlainText(result.text)
        count = len(result.corrections)
        self._correction_label.setText(f"共 {count} 处修正")
        self._update_flow_bar()

    # --------------------------------------------------------- Step 4: 纪要

    def _load_api_key(self) -> None:
        from meetrec.secrets.vault import SecretVault
        provider = self._provider_combo.currentData()
        try:
            key = SecretVault().get(f"ai_{provider}")
        except Exception:
            key = None
        if key:
            self._api_key_edit.setText(key)
        else:
            QMessageBox.information(self, "提示", f"未找到 {provider} 的 API Key，请在设置中配置")

    def _start_summarize(self) -> None:
        m = self._meeting
        if m is None:
            QMessageBox.warning(self, "错误", "请先创建或选择会议")
            return
        text = m.corrected_transcript or m.transcript
        if not text:
            QMessageBox.warning(self, "提示", "请先完成校对或转写")
            return
        provider = self._provider_combo.currentData()
        api_key = self._api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, "提示", "请输入 API Key")
            return
        instructions = self._instructions_edit.toPlainText().strip()
        self._summarize_btn.setEnabled(False)
        self._summarize_btn.setText("正在生成…")
        self._summarize_status.setText("正在调用 AI 生成纪要…")
        self._worker = Worker(self._service.summarize, m, provider, api_key, instructions)
        self._worker.progress.connect(lambda msg: self._summarize_status.setText(msg))
        self._worker.result_ready.connect(self._on_summarize_done)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _on_summarize_done(self, result: str) -> None:
        self._summarize_btn.setEnabled(True)
        self._summarize_btn.setText("生成纪要")
        self._summarize_status.setText("纪要生成完成")
        m = self._meeting
        if m is not None and result:
            m.summary = result
            m.provider = self._provider_combo.currentData()
            self._service.update_meeting(m)
            self._summary_edit.setPlainText(result)
            self._update_flow_bar()

    # --------------------------------------------------------- Step 5: 导出

    def _export_meeting(self) -> None:
        m = self._meeting
        if m is None:
            QMessageBox.warning(self, "错误", "请先创建或选择会议")
            return
        try:
            path = self._service.export(m)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
            return
        self._export_path_label.setText(str(path))
        self._export_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._open_file_btn.setEnabled(True)
        m.status = "exported"
        self._service.update_meeting(m)
        self._update_flow_bar()

    def _open_exported_file(self) -> None:
        text = self._export_path_label.text().strip()
        if text and Path(text).exists():
            QDesktopServices.openUrl(Path(text).as_uri())

    # ------------------------------------------------------------- 通用

    def _on_worker_error(self, err: str) -> None:
        self._transcribe_btn.setEnabled(True)
        self._transcribe_progress.setVisible(False)
        self._summarize_btn.setEnabled(True)
        self._summarize_btn.setText("生成纪要")
        self._transcribe_status.setText(f"错误：{err}")
        self._summarize_status.setText(f"错误：{err}")
        QMessageBox.critical(self, "操作失败", err)
        _log.error("Worker error: %s", err)
