from colorama import Fore, Style
from enum import Enum
from typing import Optional
from dataclasses import dataclass
from src.service.logger import logger
from src.config import global_config
import openai
import os
from openai import OpenAI

class CompletionResult(Enum):
    OK = 0
    TOO_LONG = 1
    INVALID_REQUEST = 2
    OTHER_ERROR = 3
    MODERATION_FLAGGED = 4
    MODERATION_BLOCKED = 5
    RATE_LIMITED = 6

@dataclass
class CompletionData:
    status: CompletionResult
    reply_text: Optional[str] = None
    status_text: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

class OpenAICompletionService:
    def __init__(self):
        try:
            # 初始化通义千问的客户端
            base_url = os.getenv('DASHSCOPE_API_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
            self.client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url=base_url,
            )
        except TypeError as e:
            logger.error("Failed to initialize OpenAI client. Make sure the API key is set correctly.")
            raise e

    def system_message(self, text: str):
        return {"role": "system", "content": text}

    def user_message(self, text: str):
        return {"role": "user", "content": text}

    def assistant_message(self, text: str):
        return {"role": "assistant", "content": text}

    def dump_prompt(self, messages):
        for message in messages:
            role = message.get("role", "unknown")
            content = message.get("content", "")
            color = {
                "user": Fore.LIGHTYELLOW_EX,
                "assistant": Fore.YELLOW,
                "system": Fore.BLUE
            }.get(role, Fore.WHITE)
            print(Fore.RED + f'{role:<10}' + color + content)
        print(Style.RESET_ALL)

    def dump_response(self, response: CompletionData):
        print(Fore.RED + "RESPONSE(" + response.status.name + "):" + Fore.GREEN)
        if response.status_text:
            print("Status:" + response.status_text)
        if response.reply_text:
            print(response.reply_text)
        if response.prompt_tokens is not None and response.completion_tokens is not None:
            total = response.prompt_tokens + response.completion_tokens
            print(Fore.RED + f"Total({total}) = Prompt({response.prompt_tokens}) + Completion({response.completion_tokens})")
        print(Style.RESET_ALL)

    def request_chat_completion(
        self,
        model,
        messages,
        max_tokens=None,
        temperature=None,
        top_p=None,
        stop=None,
        verbose_prompt=False,
        verbose_response=False
    ) -> CompletionData:

        if verbose_prompt:
            self.dump_prompt(messages)

        try:
            if model is None:
                model = os.getenv('OPENAI_MODEL', 'qwen3-max')

            completion = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop,
            )

            reply_text = self._extract_text_from_completion(completion)
            usage = getattr(completion, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)

            response = CompletionData(
                status=CompletionResult.OK,
                reply_text=reply_text,
                status_text=None,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens
            )

            if verbose_response:
                self.dump_response(response)

            return response

        except openai.RateLimitError as e:
            logger.exception(e)
            return CompletionData(status=CompletionResult.RATE_LIMITED, status_text=str(e))
        except openai.BadRequestError as e:
            if "maximum context length" in str(e):
                return CompletionData(status=CompletionResult.TOO_LONG, status_text=str(e))
            else:
                logger.exception(e)
                return CompletionData(status=CompletionResult.INVALID_REQUEST, status_text=str(e))
        except Exception as e:
            logger.exception(e)
            return CompletionData(status=CompletionResult.OTHER_ERROR, status_text=str(e))
        finally:
            if verbose_prompt or verbose_response:
                print(Style.RESET_ALL, '')

    @staticmethod
    def _extract_text_from_completion(completion) -> str:
        try:
            choice = completion.choices[0]
        except Exception:
            return ""

        content = getattr(choice.message, "content", None)
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            texts = []
            for item in content:
                text = None
                if isinstance(item, dict):
                    text = item.get("text") or item.get("value")
                else:
                    text = getattr(item, "text", None)
                if text:
                    texts.append(str(text))
            if texts:
                return "\n".join(texts).strip()

        try:
            data = completion.model_dump()
        except AttributeError:
            data = completion

        if isinstance(data, dict):
            choices = data.get("choices") or []
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content")
                if isinstance(content, str):
                    return content.strip()
                if isinstance(content, list):
                    texts = []
                    for item in content:
                        text = item.get("text") or item.get("value")
                        if text:
                            texts.append(str(text))
                    if texts:
                        return "\n".join(texts).strip()

        return ""
