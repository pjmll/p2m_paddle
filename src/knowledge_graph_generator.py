#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱生成器
基于Markdown文档生成知识图谱
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
from src.service.openai_completion_service import OpenAICompletionService, CompletionData, CompletionResult
from pyvis.network import Network
import webbrowser
 

class KnowledgeGraphGenerator:
    """知识图谱生成器"""
    
    def __init__(self):
        """初始化生成器"""
        self.openai_model = os.getenv("OPENAI_MODEL", "qwen3-max")
        self.client = None
        self.ai_service = None

        # 优先使用封装服务（可连接 DashScope/qwen）
        try:
            self.ai_service = OpenAICompletionService()
        except Exception:
            self.ai_service = None

        # 如果没有封装服务，尝试直接使用 OpenAI SDK（如果配置了 OPENAI_API_KEY）
        if not self.ai_service and os.getenv("OPENAI_API_KEY"):
            try:
                self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            except Exception:
                self.client = None
        if not self.ai_service and not self.client:
            print("警告：未设置可用的AI生成客户端，将使用简单的关键词提取")
    
    def generate_knowledge_graph(self, markdown_content: str, output_dir: Path, base_name: str) -> str:
        """
        生成知识图谱
        
        Args:
            markdown_content: Markdown文档内容
            output_dir: 输出目录
            base_name: 基础文件名
            
        Returns:
            生成的HTML文件路径
        """
        print("开始生成知识图谱...")
        
        # 提取实体和关系
        if self.client:
            nodes, edges = self._extract_with_ai(markdown_content)
        else:
            nodes, edges = self._extract_simple(markdown_content)
        
        # 生成可视化图谱
        html_path = self._create_visualization(nodes, edges, output_dir, base_name)
        
        print(f"知识图谱生成完成: {html_path}")
        return html_path
    
    def _extract_with_ai(self, markdown_content: str) -> Tuple[List[Dict], List[Dict]]:
        """
        使用AI提取实体和关系
        
        Args:
            markdown_content: Markdown内容
            
        Returns:
            (节点列表, 边列表)
        """
        try:
            # 构建prompt
            prompt = self._build_kg_prompt(markdown_content)
            
            # 调用AI API：优先使用 ai_service（DashScope/qwen 封装），否则使用 OpenAI SDK
            if self.ai_service:
                messages = [
                    self.ai_service.system_message("你是一个知识提取引擎。"),
                    self.ai_service.user_message(prompt)
                ]
                response = self.ai_service.request_chat_completion(
                    model=self.openai_model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=2000
                )
                # CompletionData -> reply_text
                if isinstance(response, CompletionData):
                    ai_response = response.reply_text
                else:
                    ai_response = str(response)
            else:
                response = self.client.chat.completions.create(
                    model=self.openai_model,
                    messages=[
                        {"role": "system", "content": "你是一个知识提取引擎。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                    max_tokens=2000
                )
                ai_response = response.choices[0].message.content
            print("AI提取实体和关系完成")
            
            # 解析AI响应
            nodes, edges = self._parse_ai_response(ai_response)
            
            return nodes, edges
            
        except Exception as e:
            print(f"AI提取失败: {e}")
            print("回退到简单提取...")
            return self._extract_simple(markdown_content)
    
    def _extract_simple(self, markdown_content: str) -> Tuple[List[Dict], List[Dict]]:
        """
        简单的关键词提取（不使用AI）
        
        Args:
            markdown_content: Markdown内容
            
        Returns:
            (节点列表, 边列表)
        """
        # 提取标题作为主要实体
        nodes = []
        edges = []
        
        lines = markdown_content.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测标题
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()
                
                if title:
                    node_id = f"section_{len(nodes)}"
                    nodes.append({
                        "id": node_id,
                        "label": title,
                        "title": f"第{level}级标题",
                        "color": self._get_color_by_level(level)
                    })
                    
                    # 建立层级关系
                    if current_section and level > 1:
                        edges.append({
                            "source": current_section,
                            "target": node_id,
                            "label": "包含"
                        })
                    
                    current_section = node_id
        
        # 如果没有找到标题，创建基本节点
        if not nodes:
            nodes.append({
                "id": "document",
                "label": "文档",
                "title": "文档内容",
                "color": "#ff7f50"
            })
        
        return nodes, edges
    
    def _parse_ai_response(self, ai_response: str) -> Tuple[List[Dict], List[Dict]]:
        """
        解析AI响应，提取节点和边
        
        Args:
            ai_response: AI的响应文本
            
        Returns:
            (节点列表, 边列表)
        """
        try:
            # 清理AI响应
            cleaned_response = self._clean_json_response(ai_response)
            
            # 解析JSON
            kg_data = json.loads(cleaned_response)
            
            nodes = kg_data.get("nodes", [])
            edges = kg_data.get("edges", [])
            
            # 验证数据格式
            nodes = self._validate_nodes(nodes)
            edges = self._validate_edges(edges, nodes)
            
            return nodes, edges
            
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            print(f"AI响应: {ai_response}")
            return self._extract_simple("")
        except Exception as e:
            print(f"解析AI响应失败: {e}")
            return self._extract_simple("")
    
    def _clean_json_response(self, response: str) -> str:
        """
        清理AI响应，提取JSON部分
        
        Args:
            response: AI响应文本
            
        Returns:
            清理后的JSON字符串
        """
        # 去除首尾空白
        response = response.strip()
        
        # 移除markdown代码块标记
        if response.startswith('```json'):
            response = response[7:]
        elif response.startswith('```'):
            response = response[3:]
        
        if response.endswith('```'):
            response = response[:-3]
        
        response = response.strip()
        
        # 查找JSON对象
        start = response.find('{')
        end = response.rfind('}')
        
        if start != -1 and end != -1 and end > start:
            response = response[start:end+1]
        
        # 修复常见的格式问题
        response = re.sub(r'\s+', ' ', response)
        
        return response
    
    def _validate_nodes(self, nodes: List[Dict]) -> List[Dict]:
        """
        验证和修复节点数据
        
        Args:
            nodes: 节点列表
            
        Returns:
            验证后的节点列表
        """
        valid_nodes = []
        
        for i, node in enumerate(nodes):
            if not isinstance(node, dict):
                continue
            
            # 确保必要字段存在
            node_id = node.get("id", f"node_{i}")
            label = node.get("label", f"节点{i}")
            title = node.get("title", label)
            color = node.get("color", "#00bfff")
            
            valid_nodes.append({
                "id": str(node_id),
                "label": str(label),
                "title": str(title),
                "color": str(color)
            })
        
        return valid_nodes
    
    def _validate_edges(self, edges: List[Dict], nodes: List[Dict]) -> List[Dict]:
        """
        验证和修复边数据
        
        Args:
            edges: 边列表
            nodes: 节点列表
            
        Returns:
            验证后的边列表
        """
        valid_edges = []
        node_ids = {node["id"] for node in nodes}
        
        for i, edge in enumerate(edges):
            if not isinstance(edge, dict):
                continue
            
            source = edge.get("source", "")
            target = edge.get("target", "")
            label = edge.get("label", f"关系{i}")
            
            # 只保留有效的边
            if source in node_ids and target in node_ids and source != target:
                valid_edges.append({
                    "source": str(source),
                    "target": str(target),
                    "label": str(label)
                })
        
        return valid_edges
    
    def _get_color_by_level(self, level: int) -> str:
        """
        根据标题级别获取颜色
        
        Args:
            level: 标题级别
            
        Returns:
            颜色代码
        """
        colors = ["#ff7f50", "#00bfff", "#32cd32", "#ffd700", "#ff69b4", "#9370db"]
        return colors[min(level - 1, len(colors) - 1)]
    
    def _create_visualization(self, nodes: List[Dict], edges: List[Dict], 
                            output_dir: Path, base_name: str) -> str:
        """
        创建可视化图谱
        
        Args:
            nodes: 节点列表
            edges: 边列表
            output_dir: 输出目录
            base_name: 基础文件名
            
        Returns:
            HTML文件路径
        """
        # 创建网络图
        net = Network(
            height="750px", 
            width="100%", 
            bgcolor="#222222", 
            font_color="white",
            notebook=True,
            cdn_resources='in_line'
        )
        
        # 添加节点
        for node in nodes:
            net.add_node(
                node["id"],
                label=node["label"],
                title=node["title"],
                color=node["color"]
            )
        
        # 添加边
        for edge in edges:
            net.add_edge(
                edge["source"],
                edge["target"],
                label=edge["label"],
                title=edge["label"]
            )
        
        # 设置物理引擎参数
        net.set_options("""
        var options = {
          "physics": {
            "enabled": true,
            "stabilization": {"iterations": 100}
          }
        }
        """)
        
        # 保存HTML文件
        html_path = output_dir / f"{base_name}_knowledge_graph.html"
        # net.save_graph(str(html_path))
        # 使用 utf-8 编码手动保存，避免 Windows 下 gbk 编码错误
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(net.generate_html())
        
        return str(html_path)
    
    def _build_kg_prompt(self, markdown_content: str) -> str:
        """
        构建知识图谱提取的prompt
        
        Args:
            markdown_content: Markdown内容
            
        Returns:
            完整的prompt
        """
        # 尝试从文件读取 prompt
        prompt_path = Path("prompt/extract_knowledge_graph.txt")
        if prompt_path.exists():
            try:
                template = prompt_path.read_text(encoding="utf-8")
                return template.format(markdown_content=markdown_content)
            except Exception as e:
                print(f"读取 prompt 文件失败: {e}，使用默认 prompt")

        prompt = f"""你是一个知识提取引擎。你的任务是从给定的 Markdown 文档中识别出核心的实体（Entities）和它们之间的关系（Relationships），并以严格的 JSON 格式输出。

**重要：你的回复必须是一个有效的JSON对象，不要包含任何其他文本、解释、换行符或格式标记。**

JSON 格式要求如下：
{{
  "nodes": [
    {{"id": "unique_node_id_1", "label": "实体名称1", "title": "关于实体的简短描述", "color": "#ff7f50"}},
    {{"id": "unique_node_id_2", "label": "实体名称2", "title": "关于实体的简短描述"}}
  ],
  "edges": [
    {{"source": "unique_node_id_1", "target": "unique_node_id_2", "label": "关系描述"}}
  ]
}}

请遵循以下规则：
1. `id` 必须是唯一的字符串，可以由实体名称本身或其变体生成。
2. `label` 是显示在图谱节点上的文本。
3. `title` 是鼠标悬停时显示的提示信息。
4. `color` 是可选的，用于区分不同类型的实体。
5. `source` 和 `target` 必须对应 `nodes` 列表中的 `id`。
6. `label` 在 `edges` 中描述了两个实体间的关系。
7. 只提取文档中最重要、最核心的实体和关系。不要提取无关紧要的细节。
8. 输出必须是且仅是一个完整的、无任何额外解释的 JSON 对象。
9. 不要使用markdown代码块标记（```json 或 ```），直接输出JSON。
10. 不要添加任何换行符、缩进或额外的空格。
11. 确保JSON格式完全正确，可以被直接解析。

以下是需要分析的 Markdown 文档：
---
{markdown_content}
---"""
        
        return prompt
    
    def open_in_browser(self, html_path: str) -> None:
        """
        在浏览器中打开知识图谱
        
        Args:
            html_path: HTML文件路径
        """
        try:
            webbrowser.open(f"file://{os.path.abspath(html_path)}")
            print(f"已在浏览器中打开知识图谱: {html_path}")
        except Exception as e:
            print(f"打开浏览器失败: {e}")
