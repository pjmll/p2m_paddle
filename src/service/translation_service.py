import os
import requests
from typing import Optional
from src.config import global_config
from src.service.openai_completion_service import OpenAICompletionService, CompletionResult, CompletionData
from src.service.prompt_manager import prompt_manager


class TranslationService:
    """统一的翻译服务入口，优先使用 DeepL via RapidAPI（若配置），否则回退到 OpenAI。"""

    def __init__(self):
        self.deepl_key = getattr(global_config, 'DEEPL_RAPID_API_KEY', None)
        self.deepl_host = getattr(global_config, 'DEEPL_RAPID_API_HOST', None)
        # 新增：DashScope API 支持（用户已在环境变量中添加 DASHSCOPE_API_KEY）
        # 支持两种配置方式：
        # - 提供 DASHSCOPE_API_URL（完整 URL），例如 https://api.dashscope.example/v1/translate
        # - 或提供 DASHSCOPE_RAPIDAPI_HOST（与 RapidAPI 一起）并使用 X-RapidAPI-Key
        self.dashscope_key = os.getenv('DASHSCOPE_API_KEY')
        self.dashscope_url = os.getenv('DASHSCOPE_API_URL')
        self.dashscope_rapidapi_host = os.getenv('DASHSCOPE_RAPIDAPI_HOST')

        # 使用封装的 OpenAICompletionService 作为回退
        try:
            self.openai_service = OpenAICompletionService()
        except Exception:
            self.openai_service = None
        
        # 如果用户提供了 DASHSCOPE_API_KEY，也尝试用封装的 OpenAICompletionService 直接调用（优先）
        try:
            self.ai_service = OpenAICompletionService()
        except Exception:
            self.ai_service = None

    def translate(self, text: str, source: Optional[str] = None, target: Optional[str] = None, method: str = 'auto', timeout: int = 60) -> str:
        """
        翻译文本，默认优先选择 DeepL RapidAPI（若配置），否则回退到 OpenAI。

        Args:
            text: 待翻译文本
            source: 源语言（如 'EN'），若 None 则自动检测
            target: 目标语言（如 'KO'），若 None 则使用配置中的默认
            method: 'auto'|'deepl'|'openai' 强制选择方法
            timeout: 请求超时时间（秒）

        Returns:
            翻译后的文本
        """
        dst = target or getattr(global_config, 'DEEPL_RAPID_API_DST_LANG', None) or 'KO'
        src = source or getattr(global_config, 'DEEPL_RAPID_API_SRC_LANG', None) or 'AUTO'

        use_deepl = (method == 'deepl') or (method == 'auto' and self.deepl_key and self.deepl_host)

        # 优先使用 DashScope（如果配置且 method 为 auto 或 dashscope）
        use_dashscope = (method == 'dashscope') or (method == 'auto' and self.dashscope_key)

        if use_dashscope:
            # 首选：如果存在封装的 ai_service（兼容 DashScope/qwen），使用它进行翻译
            if self.ai_service:
                try:
                    # Map short language codes to human-friendly names for better model instruction
                    lang_map = {
                        'ZH': 'Chinese', 'ZH-CN': 'Chinese', 'CN': 'Chinese',
                        'KO': 'Korean', 'EN': 'English', 'JA': 'Japanese', 'DE': 'German',
                        'FR': 'French', 'ES': 'Spanish'
                    }
                    dst_name = lang_map.get(dst.upper(), dst)

                    messages = [
                        self.ai_service.system_message(f"You are a helpful translator. Translate the user's text to {dst_name} without extra explanation."),
                        self.ai_service.user_message(text)
                    ]
                    resp = self.ai_service.request_chat_completion(
                        model=os.getenv('OPENAI_MODEL', 'qwen3-max'),
                        messages=messages,
                        temperature=0.0,
                        max_tokens=1000
                    )
                    if isinstance(resp, CompletionData):
                        if resp.status == CompletionResult.OK:
                            result = resp.reply_text
                            # ensure string
                            if isinstance(result, bytes):
                                result = result.decode('utf-8', errors='replace')
                            return str(result)
                        else:
                            print(f"DashScope (ai_service) returned non-OK status: {resp.status} - falling back")
                    else:
                        # 保守处理：尝试从对象提取文本
                        try:
                            result = resp.choices[0].message.content
                            if isinstance(result, bytes):
                                result = result.decode('utf-8', errors='replace')
                            return str(result)
                        except Exception:
                            print("DashScope ai_service returned unexpected response; falling back")
                except Exception as e:
                    print(f"DashScope ai_service translation failed: {e} - falling back to other backends")

            # 如果 ai_service 不可用或失败，回退到直接 HTTP 调用（旧逻辑）
            try:
                # 如果提供了完整的 URL，则直接 POST 到该 URL
                if self.dashscope_url:
                    url = self.dashscope_url
                    headers = {
                        'Authorization': f'Bearer {self.dashscope_key}',
                        'Content-Type': 'application/json'
                    }
                    payload = { 'text': text, 'source': src, 'target': dst }
                    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
                    resp.raise_for_status()
                    data = resp.json()
                    # 支持多种可能的返回字段名
                    result = data.get('translatedText') or data.get('text') or data.get('translation') or ''
                    if isinstance(result, bytes):
                        result = result.decode('utf-8', errors='replace')
                    return str(result)
                # 否则如果使用 RapidAPI 风格的 host
                elif self.dashscope_rapidapi_host:
                    url = f"https://{self.dashscope_rapidapi_host}/translate"
                    headers = {
                        'content-type': 'application/json',
                        'X-RapidAPI-Key': self.dashscope_key,
                        'X-RapidAPI-Host': self.dashscope_rapidapi_host
                    }
                    payload = { 'text': text, 'source': src, 'target': dst }
                    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
                    resp.raise_for_status()
                    data = resp.json()
                    result = data.get('translatedText') or data.get('text') or data.get('translation') or ''
                    if isinstance(result, bytes):
                        result = result.decode('utf-8', errors='replace')
                    return str(result)
                else:
                    # 最后尝试一个常见的 DashScope 端点路径（假定主机为 dashscope.example）
                    url = os.getenv('DASHSCOPE_API_FALLBACK_URL', 'https://api.dashscope.ai/v1/translate')
                    headers = { 'Authorization': f'Bearer {self.dashscope_key}', 'Content-Type': 'application/json' }
                    payload = { 'text': text, 'source': src, 'target': dst }
                    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
                    resp.raise_for_status()
                    data = resp.json()
                    result = data.get('translatedText') or data.get('text') or data.get('translation') or ''
                    if isinstance(result, bytes):
                        result = result.decode('utf-8', errors='replace')
                    return str(result)
            except Exception as e:
                print(f"DashScope translation failed: {e} - falling back to other backends")

        if use_deepl:
            try:
                url = "https://deepl-translator.p.rapidapi.com/translate"
                payload = {"text": text, "source": src, "target": dst}
                headers = {
                    "content-type": "application/json",
                    "X-RapidAPI-Key": self.deepl_key,
                    "X-RapidAPI-Host": self.deepl_host
                }
                resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                # DeepL RapidAPI 返回的 text 字段
                result = data.get('text') or data.get('translatedText') or ''
                if isinstance(result, bytes):
                    result = result.decode('utf-8', errors='replace')
                return str(result)
            except Exception as e:
                print(f"DeepL translation failed: {e} - falling back to OpenAI")

        # 回退到 OpenAI
        if self.openai_service is None:
            raise RuntimeError('No translation backend available')

        # 构建 prompt（使用 prompt_manager 的 translate 模板）
        try:
            prompt = prompt_manager.generate_prompt('translate', { 'Text': text })
        except Exception:
            # 如果没有模板，使用简单的指令
            prompt = f"Translate the following text to {dst}:\n\n{text}"

        response = self.openai_service.request_chat_completion(
            model=os.getenv('OPENAI_MODEL', 'qwen3-max'),
            messages=[self.openai_service.user_message(prompt)],
            temperature=0.0
        )

        if response.status == CompletionResult.OK:
            result = response.reply_text
            if isinstance(result, bytes):
                result = result.decode('utf-8', errors='replace')
            return str(result)
        else:
            raise RuntimeError(f"OpenAI translation failed: {response.status_text}")
