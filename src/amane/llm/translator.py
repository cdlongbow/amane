"""LLM 翻译器 - ``Translator`` 协议的实现.

职责分流 (见 amane/utils/language):
- 跨语系 (日/英 → 目标) → 查缓存, 未命中才调用 ``LLMBackend`` 并回写缓存.
- 中文内部 (简↔繁) → ``zhconv`` 字形转换, 不耗 LLM 也不进缓存 (幂等, 共用字天然 no-op).
- 已是目标语言 → 返回 ``None``, 调用方保留原值.

``build_translator`` 由 HotSettings.llm 装配后端; enabled=False 或缺 api_key 时返回 ``None``,
管线据此跳过翻译.
"""

import structlog
import zhconv

from ..enums import Language, MetadataField
from ..utils.language import needs_llm_translation
from .backend import OpenAIBackend
from .cache import TranslationCache
from .protocol import LLMBackend

logger = structlog.get_logger()

# Language 枚举 → zhconv locale 代码 (仅中文变体).
_ZHCONV_LOCALE: dict[Language, str] = {
    Language.ZH_CN: "zh-cn",
    Language.ZH_TW: "zh-tw",
}

# 目标语言的人类可读名 (用于提示词).
_LANG_NAME: dict[Language, str] = {
    Language.ZH_CN: "简体中文",
    Language.ZH_TW: "繁體中文",
    Language.JP: "日本語",
    Language.EN: "English",
}

# 字段级翻译要求.
_FIELD_HINT: dict[MetadataField, str] = {
    MetadataField.TITLE: "这是一部影片的标题, 翻译应简洁自然, 保留专有名词与番号.",
    MetadataField.PLOT: "这是一部影片的简介, 完整通顺地翻译全部内容.",
}


def _build_prompts(text: str, target: Language, field: MetadataField) -> tuple[str, str]:
    lang_name = _LANG_NAME[target]
    hint = _FIELD_HINT.get(field, "")
    system = (
        f"你是专业的影视元数据翻译. 将用户提供的文本翻译为{lang_name}. "
        f"{hint} 只输出译文本身, 不要解释、不要引号、不要附加任何内容."
    )
    return system, text


class LLMTranslator:
    """实现 ``Translator``: 跨语系走 LLM (带缓存), 中文变体走 zhconv."""

    def __init__(self, backend: LLMBackend, cache: TranslationCache | None = None) -> None:
        self._backend = backend
        self._cache = cache

    async def translate(
        self, text: str, target: Language, field: MetadataField, *, use_cache: bool = True
    ) -> str | None:
        text = text.strip()
        if not text:
            return None

        if needs_llm_translation(text, target):
            # 缓存命中即跳过 LLM: 全缓存重刮, 配置不变时不重复翻译, 也避免 temperature 漂移.
            # use_cache=False 时跳过读取 (强制重译), 但仍回写以刷新缓存.
            if self._cache is not None and use_cache:
                cached = await self._cache.get(text, target, field)
                if cached is not None:
                    return cached
            system, user = _build_prompts(text, target, field)
            result = await self._backend.ask(system_prompt=system, user_prompt=user)
            if not result:
                return None
            if self._cache is not None:
                await self._cache.put(text, target, field, result)
            return result

        # 中文文本: 简繁字形转换 (幂等); 共用字/已是目标变体则结果等于原文 → 返回 None 省去写回.
        locale = _ZHCONV_LOCALE.get(target)
        if locale is not None:
            converted = zhconv.convert(text, locale)
            return converted if converted != text else None

        return None


def build_translator(
    *,
    enabled: bool,
    api_key: str | None,
    base_url: str,
    model: str,
    max_retries: int,
    rate_limit: float,
    proxy: str | None = None,
    cache: TranslationCache | None = None,
) -> LLMTranslator | None:
    """按配置装配翻译器. 未启用或缺密钥时返回 ``None`` (管线跳过翻译).

    ``cache`` 为会话级译文缓存 (bootstrap 创建并经 AppRuntime 注入), 热重载时复用同一实例.
    """
    if not enabled or not api_key:
        return None
    backend = OpenAIBackend(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_retries=max_retries,
        rate_limit=rate_limit,
        proxy=proxy,
    )
    return LLMTranslator(backend, cache)
