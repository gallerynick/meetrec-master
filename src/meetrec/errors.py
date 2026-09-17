"""MeetRec Master 错误层级。

设计原则：
1. 每个错误携带面向用户的中文消息（message）与可选操作建议（hint）。
2. code 为机器可读的稳定标识，供 UI 分支与日志检索使用，不做本地化。
3. details 仅用于调试与诊断包导出（ADR-010），不展示给最终用户。
"""

from __future__ import annotations

from typing import Any


class MeetRecError(Exception):
    """MeetRec 所有错误的基类。"""

    code: str = "meetrec.unknown"
    message: str = "发生未知错误"
    hint: str | None = None

    def __init__(
        self,
        message: str | None = None,
        *,
        hint: str | None = None,
        details: Any = None,
    ) -> None:
        self.message: str = message or self.__class__.message
        self.hint: str | None = hint if hint is not None else self.__class__.hint
        self.details: Any = details
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.hint:
            return f"{self.message}（建议：{self.hint}）"
        return self.message


# ---------------------------------------------------------------------------
# 配置与存储
# ---------------------------------------------------------------------------


class ConfigError(MeetRecError):
    """配置文件读取、写入或 schema 校验失败。"""

    code = "config.error"
    message = "配置读取失败"


class ConfigSchemaError(ConfigError):
    """配置文件 schema 版本不兼容。"""

    code = "config.schema"
    message = "配置文件版本不兼容"
    hint = "请在 设置 → 高级 中选择「重置配置」，或手动修复 config.json"


class StorageError(MeetRecError):
    """文件存储（会议、音频、导出）失败。"""

    code = "storage.error"
    message = "文件存储失败"


# ---------------------------------------------------------------------------
# 密钥库（ADR-007）
# ---------------------------------------------------------------------------


class SecretsError(MeetRecError):
    """密钥存储相关错误基类。"""

    code = "secrets.error"
    message = "密钥存储失败"


class VaultUnavailableError(SecretsError):
    """OS 钥匙串不可用且降级路径也失败。"""

    code = "secrets.vault_unavailable"
    message = "无法访问系统钥匙串"
    hint = "应用将使用本地加密文件作为备用存储，安全性略低"


class VaultCorruptedError(SecretsError):
    """加密文件损坏或密钥不匹配。"""

    code = "secrets.vault_corrupted"
    message = "密钥存储文件已损坏"
    hint = "请删除损坏文件后重新配置服务商密钥"


# ---------------------------------------------------------------------------
# 音频与 ASR
# ---------------------------------------------------------------------------


class AudioError(MeetRecError):
    """音频导入或解码错误基类。"""

    code = "audio.error"
    message = "音频处理失败"


class AudioDecodeError(AudioError):
    """音频解码失败（编码不受支持或文件损坏）。"""

    code = "audio.decode"
    message = "音频解码失败"
    hint = "支持的格式：mp3 / wav / m4a / aac / flac / ogg / opus"


class ASRError(MeetRecError):
    """语音识别错误基类。"""

    code = "asr.error"
    message = "语音识别失败"


class ModelNotFoundError(ASRError):
    """ASR 模型未下载。"""

    code = "asr.model_not_found"
    message = "语音识别模型未下载"
    hint = "请在 设置 → ASR → 模型 中选择模型并点击下载"


class ModelDownloadError(ASRError):
    """模型下载失败。"""

    code = "asr.model_download"
    message = "模型下载失败"
    hint = "请检查网络连接，或手动放置模型目录（设置 → ASR → 模型目录）"


class TranscriptionError(ASRError):
    """转写过程中发生错误。"""

    code = "asr.transcription"
    message = "转写过程中发生错误"


# ---------------------------------------------------------------------------
# 关键词（四阶段架构）
# ---------------------------------------------------------------------------


class KeywordError(MeetRecError):
    """关键词纠错错误基类。"""

    code = "keyword.error"
    message = "关键词处理失败"


class KeywordLoadError(KeywordError):
    """关键词文件加载失败。"""

    code = "keyword.load"
    message = "关键词文件加载失败"
    hint = "请检查关键词文件格式，或导入示例文件"


class CorrectionError(KeywordError):
    """关键词纠错阶段错误。"""

    code = "keyword.correction"
    message = "关键词纠错失败"


# ---------------------------------------------------------------------------
# AI 服务商
# ---------------------------------------------------------------------------


class ProviderError(MeetRecError):
    """AI 服务商请求错误基类。"""

    code = "provider.error"
    message = "AI 服务商请求失败"


class ProviderConfigError(ProviderError):
    """服务商配置不完整或无效。"""

    code = "provider.config"
    message = "服务商配置不完整"
    hint = "请在 设置 → AI 服务商 中填写 Base URL 与 API Key"


class ProviderAuthError(ProviderError):
    """API Key 无效或已过期。"""

    code = "provider.auth"
    message = "API Key 无效"
    hint = "请检查 API Key 是否正确，或前往服务商后台重新生成"


class ProviderRateLimitError(ProviderError):
    """触发限流。"""

    code = "provider.rate_limit"
    message = "请求过于频繁"
    hint = "请稍后重试，或检查服务商额度"


class ProviderTimeoutError(ProviderError):
    """请求超时。"""

    code = "provider.timeout"
    message = "请求超时"
    hint = "请检查网络，或尝试更小的纪要模板"


class ProviderHTTPError(ProviderError):
    """服务商返回非预期 HTTP 状态码。"""

    code = "provider.http"
    message = "服务商返回错误响应"


# ---------------------------------------------------------------------------
# 网络
# ---------------------------------------------------------------------------


class NetworkError(MeetRecError):
    """网络连接错误。"""

    code = "network.error"
    message = "网络连接失败"
    hint = "请检查网络连接"


# ---------------------------------------------------------------------------
# 用户操作
# ---------------------------------------------------------------------------


class UserCancelledError(MeetRecError):
    """用户主动取消操作（非错误，用于中断流程）。"""

    code = "user.cancelled"
    message = "操作已取消"
