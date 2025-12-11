#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
结构化Markdown生成器
使用AI将OCR文本转换为结构化的Markdown文档
"""

import os
import sys
import json
from typing import Optional, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from openai import OpenAI
import os
from src.service.openai_completion_service import OpenAICompletionService, CompletionResult, CompletionData

class MarkdownGenerator:
    """结构化Markdown生成器"""
    
    def __init__(self):
        """初始化生成器"""
        # 从环境变量读取 OpenAI 配置（兼容无配置的本地回退）
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_model = os.getenv('OPENAI_MODEL', 'qwen3-max')
        self.client = None
        self.ai_service = None

        if self.openai_api_key:
            try:
                self.client = OpenAI(api_key=self.openai_api_key)
            except Exception as e:
                print(f"警告：无法初始化 OpenAI 客户端: {e}，将使用本地回退")
        else:
            # 尝试使用封装的 OpenAICompletionService（可连接 DashScope/qwen 等兼容服务）
            try:
                self.ai_service = OpenAICompletionService()
            except Exception:
                self.ai_service = None
                print("警告：未设置 OPENAI_API_KEY 或无法初始化合成服务，将使用本地简单格式化")
    
    def generate_markdown(self, ocr_text: str) -> str:
        """
        将OCR文本转换为结构化Markdown
        
        Args:
            ocr_text: OCR识别的原始文本
            
        Returns:
            结构化的Markdown内容
        """
        return self.generate_markdown_with_options(ocr_text, use_ai=True, timeout=30)

    def generate_markdown_with_options(self, ocr_text: str, use_ai: bool = True, timeout: int = 30) -> str:
        """
        更灵活的生成接口，可以指定是否使用 AI 以及超时时间。

        Args:
            ocr_text: OCR 原始文本
            use_ai: 是否尝试使用 AI（若未配置 client 则会回退）
            timeout: AI 调用的最大秒数（超时将回退）
        """
        if not ocr_text.strip():
            return "# 文档\n\n[无内容]"

        # 优先使用封装的 ai_service（例如 DashScope/qwen），其次尝试直接 OpenAI client
        if use_ai and (self.ai_service or self.client):
            return self._generate_with_ai(ocr_text, timeout=timeout)
        else:
            return self._generate_simple_format(ocr_text)
    
    def _generate_with_ai(self, ocr_text: str, timeout: int = 30) -> str:
        """
        使用AI生成结构化Markdown
        
        Args:
            ocr_text: OCR文本
            
        Returns:
            AI生成的结构化Markdown
        """
        # 构建 prompt
        prompt = self._build_markdown_prompt(ocr_text)

        def do_call() -> Any:
            # 如果有 ai_service，使用它的 request_chat_completion
            if self.ai_service:
                messages = [
                    self.ai_service.system_message("你是一个专业的文档编辑和格式化助手。"),
                    self.ai_service.user_message(prompt)
                ]
                return self.ai_service.request_chat_completion(
                    model=self.openai_model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=4000
                )
            else:
                return self.client.chat.completions.create(
                    model=self.openai_model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的文档编辑和格式化助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=4000
                )

        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(do_call)
                try:
                    response = future.result(timeout=timeout)
                except FuturesTimeout:
                    future.cancel()
                    print(f"AI 调用超时（{timeout}s），回退到本地格式化")
                    return self._generate_simple_format(ocr_text)

            # 如果使用 ai_service，response 是 CompletionData；否则是 OpenAI SDK 返回对象
            if self.ai_service and isinstance(response, CompletionData):
                if response.status == CompletionResult.OK and response.reply_text:
                    markdown_content = response.reply_text
                else:
                    print(f"AI 服务返回错误状态: {response.status}, 信息: {response.status_text}")
                    raise Exception(f"AI Service Error: {response.status_text}")
            else:
                # OpenAI SDK response
                try:
                    markdown_content = response.choices[0].message.content
                except Exception:
                    # If it's the CompletionData dataclass returned by ai_service
                    try:
                        markdown_content = response.reply_text
                    except Exception:
                        markdown_content = str(response)
            
            if not markdown_content:
                raise Exception("AI 返回内容为空")

            print("AI 生成结构化 Markdown 完成")
            return markdown_content

        except Exception as e:
            print(f"AI 生成 Markdown 失败: {e}")
            print("回退到本地简单格式化...")
            return self._generate_simple_format(ocr_text)
    
    def _generate_simple_format(self, ocr_text: str) -> str:
        """
        简单的文本格式化（不使用AI）
        
        Args:
            ocr_text: OCR文本
            
        Returns:
            简单格式化的Markdown
        """
        lines = ocr_text.split('\n')
        formatted_lines = []
        
        # 添加标题
        formatted_lines.append("# 文档内容\n")
        
        current_section = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_section:
                    formatted_lines.append(current_section)
                    formatted_lines.append("")
                    current_section = ""
                continue
            
            # 简单的标题检测（基于长度和内容）
            if self._is_likely_title(line):
                if current_section:
                    formatted_lines.append(current_section)
                    formatted_lines.append("")
                formatted_lines.append(f"## {line}")
                formatted_lines.append("")
                current_section = ""
            else:
                if current_section:
                    current_section += " " + line
                else:
                    current_section = line
        
        # 添加最后一段
        if current_section:
            formatted_lines.append(current_section)
        
        return '\n'.join(formatted_lines)
    
    def _is_likely_title(self, line: str) -> bool:
        """
        判断一行是否可能是标题
        
        Args:
            line: 文本行
            
        Returns:
            是否可能是标题
        """
        # 简单的标题检测规则
        if len(line) < 3 or len(line) > 100:
            return False
        
        # 包含数字和点的可能是标题
        if any(char.isdigit() for char in line) and '.' in line:
            return True
        
        # 全大写的短行可能是标题
        if line.isupper() and len(line) < 50:
            return True
        
        # 包含特定关键词的可能是标题
        title_keywords = ['摘要', '引言', '方法', '结果', '讨论', '结论', '参考文献', 
                         'Abstract', 'Introduction', 'Method', 'Result', 'Discussion', 
                         'Conclusion', 'Reference']
        
        for keyword in title_keywords:
            if keyword.lower() in line.lower():
                return True
        
        return False
    
    def _build_markdown_prompt(self, ocr_text: str) -> str:
        """
        构建Markdown生成的prompt
        
        Args:
            ocr_text: OCR文本
            
        Returns:
            完整的prompt
        """
        prompt = f"""你是一个专业的文档编辑和格式化助手（基于 Qwen 大模型）。你的任务是将以下提供的纯文本文档内容转换成一个结构清晰、格式优美的 Markdown 文档。

请遵循以下规则：
1. **标题识别**：准确识别并使用 Markdown 标题（#, ##, ###）来组织文档结构。
2. **列表格式化**：将列表、要点或步骤格式化为无序列表（-）或有序列表（1., 2.）。
3. **强调重点**：适当地使用粗体（**text**）或斜体（*text*）来强调关键词或概念。
4. **段落优化**：保持段落之间的空行以提高可读性，修复可能的断行问题。
5. **表格处理**：如果原文中包含表格数据，请尽力将其格式化为 Markdown 表格。
6. **数学公式**：如果包含数学公式，请使用 LaTeX 格式（例如 $E=mc^2$）。
7. **内容完整**：不要添加原文中没有的信息，只做格式化和结构整理。

以下是需要格式化的文档内容：
---
{ocr_text}
---"""
        
        return prompt
    
    def save_markdown(self, markdown_content: str, output_path: str) -> None:
        """
        保存Markdown内容到文件
        
        Args:
            markdown_content: Markdown内容
            output_path: 输出文件路径
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            print(f"Markdown文件已保存到: {output_path}")
        except Exception as e:
            print(f"保存Markdown文件失败: {e}")
            raise
