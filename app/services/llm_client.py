import httpx
from typing import List, Dict
from app.core.config import get_settings

settings = get_settings()

DASHSCOPE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"


async def chat_completion(
    messages: List[Dict[str, str]],
    model: str = None,
    timeout: float = None,
) -> str:
    """
    调用通义千问 DashScope API。
    失败时返回兜底文案，不抛异常到上层。
    """
    model = model or settings.llm_model
    timeout = timeout or settings.request_timeout

    headers = {
        "Authorization": f"Bearer {settings.dashscope_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "input": {
            "messages": messages,
        },
        "parameters": {
            "result_format": "message",
            "max_tokens": 800,
            "temperature": 0.8,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(DASHSCOPE_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # 解析返回
        output = data.get("output", {})
        choices = output.get("choices", [])
        if not choices:
            return "（角色望着河水，一时陷入沉思……）"

        message = choices[0].get("message", {})
        content = message.get("content", "").strip()
        return content or "（角色望着河水，一时陷入沉思……）"

    except httpx.TimeoutException:
        return "（角色望着河水，一时陷入沉思……）"
    except Exception:
        return "（角色望着河水，一时陷入沉思……）"
