"""管线只依赖 ``Translator`` / ``LLMBackend``; 当前为 OpenAI 兼容后端."""

from .backend import OpenAIBackend
from .cache import TranslationCache
from .protocol import LLMBackend, Translator
from .translator import LLMTranslator, build_translator

__all__ = [
    "LLMBackend",
    "LLMTranslator",
    "OpenAIBackend",
    "TranslationCache",
    "Translator",
    "build_translator",
]
