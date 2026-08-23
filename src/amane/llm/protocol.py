"""LLM 端口协议 - 管线对 LLM 能力的稳定依赖面.

两层协议:
- ``LLMBackend``: 原始 chat 能力. 一次问答, 不含业务语义.
- ``Translator``: 翻译业务能力. 管线 (handlers) 仅依赖此协议.

分两层的原因: 翻译以外的未来用途 (分类/抽取等) 可复用同一 ``LLMBackend``,
而各业务各有自己的高层协议. 后端可替换 (OpenAI / dspy / ...) 而协议不变.
"""

from typing import Protocol, runtime_checkable

from ..enums import Language, MetadataField


@runtime_checkable
class LLMBackend(Protocol):
    """原始 LLM 问答后端. 失败返回 ``None`` (机会主义, 不抛)."""

    async def ask(self, *, system_prompt: str, user_prompt: str) -> str | None: ...


@runtime_checkable
class Translator(Protocol):
    """文本翻译能力. 管线只依赖此协议."""

    async def translate(
        self, text: str, target: Language, field: MetadataField, *, use_cache: bool = True
    ) -> str | None:
        """将 ``text`` 翻译为 ``target`` 语言.

        返回译文; 无需翻译或失败时返回 ``None`` (调用方保留原值).
        ``field`` 供后端按字段定制提示词 (如 title 简洁, plot 完整).
        ``use_cache=False`` 时跳过译文缓存读取 (强制重译), 但仍刷新缓存.
        """
        ...
