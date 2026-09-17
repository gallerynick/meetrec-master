"""AI 提供方。

支持 OpenAI / Anthropic / DeepSeek。
DeepSeek 使用 OpenAI 兼容接口（base_url 不同）。
"""

from __future__ import annotations

from typing import NoReturn

from meetrec.errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

__all__ = [
    "PROVIDER_NAMES",
    "AIProvider",
    "AnthropicProvider",
    "DeepSeekProvider",
    "OpenAIProvider",
    "create_provider",
]

PROVIDER_NAMES: dict[str, str] = {
    "openai": "OpenAI (GPT-4o)",
    "anthropic": "Anthropic (Claude 3.5)",
    "deepseek": "DeepSeek",
}


class AIProvider:
    """AI 提供方基类。"""

    name: str = ""
    model: str = ""

    def summarize(self, text: str, instructions: str = "") -> str:
        raise NotImplementedError

    @staticmethod
    def _handle_error(e: Exception) -> NoReturn:
        error_str = str(e)
        lower = error_str.lower()
        if "401" in error_str or "authentication" in lower:
            raise ProviderAuthError(message="API Key 无效或已过期") from e
        if "429" in error_str or "rate" in lower:
            raise ProviderRateLimitError(
                message="请求频率限制，请稍后重试"
            ) from e
        if "timeout" in lower:
            raise ProviderTimeoutError(message="请求超时，请稍后重试") from e
        raise ProviderError(message=f"请求失败：{error_str}") from e


class OpenAIProvider(AIProvider):
    """OpenAI 提供方。"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self.model = model
        self.name = "OpenAI"

    def summarize(self, text: str, instructions: str = "") -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": text}],
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            self._handle_error(e)


class AnthropicProvider(AIProvider):
    """Anthropic 提供方。"""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)
        self.model = model
        self.name = "Anthropic"

    def summarize(self, text: str, instructions: str = "") -> str:
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": text}],
            )
            return resp.content[0].text or ""
        except Exception as e:
            self._handle_error(e)


class DeepSeekProvider(AIProvider):
    """DeepSeek 提供方（OpenAI 兼容接口）。"""

    def __init__(self, api_key: str, model: str = "deepseek-chat") -> None:
        from openai import OpenAI

        self._client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        self.model = model
        self.name = "DeepSeek"

    def summarize(self, text: str, instructions: str = "") -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": text}],
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            self._handle_error(e)


def create_provider(name: str, api_key: str) -> AIProvider:
    """工厂函数：按名称创建 AI 提供方。"""
    if not api_key:
        raise ProviderConfigError(message="API Key 未配置")
    key = name.lower().strip()
    if key == "openai":
        return OpenAIProvider(api_key)
    if key == "anthropic":
        return AnthropicProvider(api_key)
    if key == "deepseek":
        return DeepSeekProvider(api_key)
    raise ProviderConfigError(message=f"未知提供方：{name}")
