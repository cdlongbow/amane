"""OpenAI 兼容 chat completions. 凭据经构造函数注入; 实例随 HotSettings.llm 重建."""

import asyncio
import re

import structlog
from aiolimiter import AsyncLimiter
from httpx2 import AsyncClient, Timeout
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

logger = structlog.get_logger()

# 去除推理模型输出中的思维链, 仅保留最终答案.
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


class OpenAIBackend:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        max_retries: int = 3,
        rate_limit: float = 2.0,
        timeout: float = 60.0,
        proxy: str | None = None,
    ) -> None:
        self._model = model
        self._max_retries = max_retries
        # LLM 端点独立限速, 与站点 host 限速隔离: 桶容量 1, 严格平滑.
        self._limiter = AsyncLimiter(1, 1 / rate_limit)
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=AsyncClient(proxy=proxy, timeout=Timeout(timeout), follow_redirects=True),
            timeout=timeout,
            max_retries=0,  # 重试自行控制 (指数退避 + 限速协同)
        )

    async def ask(self, *, system_prompt: str, user_prompt: str) -> str | None:
        """重试耗尽或无内容时返回 ``None``, 不抛异常. 结果剥离推理模型的 thinking 链."""
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        wait = 1.0
        async with self._limiter:
            for attempt in range(self._max_retries + 1):
                try:
                    resp = await self._client.chat.completions.create(model=self._model, messages=messages)
                    text = resp.choices[0].message.content
                    return _THINK.sub("", text).strip() if text else None
                except Exception as e:
                    if attempt == self._max_retries:
                        logger.warning("LLM request failed, retries exhausted", error=str(e))
                        return None
                    logger.debug("LLM request failed, retrying", error=str(e), wait=wait)
                    await asyncio.sleep(wait)
                    wait *= 2
        return None
