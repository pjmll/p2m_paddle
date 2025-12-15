#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR处理模块
使用大模型接口对扫描版PDF进行文本识别
"""

import base64
import os
from io import BytesIO
from typing import List, Optional
import numpy as np

import fitz  # PyMuPDF
from PIL import Image
from paddleocr import PaddleOCR

from src.service.logger import logger


class OCRProcessor:
    """OCR处理器，基于PaddleOCR完成OCR识别"""

    def __init__(
        self,
        dpi: int = 300,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
    ):
        self.dpi = dpi
        # 默认尝试使用 GPU，如果失败会自动回退到 CPU
        self.device = "gpu" 
        self._init_engine()

    def _init_engine(self):
        # 初始化 PaddleOCR
        try:
            logger.info(f"正在初始化 PaddleOCR (device={self.device})...")
            # PaddleOCR v3+ uses 'device' instead of 'use_gpu'
            # use_angle_cls is deprecated, use use_textline_orientation
            self.ocr_engine = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="PP-OCRv5_mobile_rec",
                ocr_version="PP-OCRv5",
                lang="ch",
                device=self.device
            )
            logger.info(f"PaddleOCR 初始化成功 (device={self.device})")
        except Exception as e:
            logger.error(f"PaddleOCR 初始化失败: {e}")
            self.ocr_engine = None

    def process_pdf(self, pdf_path: str, lang: str = "auto") -> str:
        logger.info("开始调用大模型进行OCR: %s", pdf_path)

        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            logger.info("PDF总页数: %d", total_pages)

            all_text: List[str] = []

            for page_num in range(total_pages):
                logger.info("处理第 %d/%d 页", page_num + 1, total_pages)

                page = doc.load_page(page_num)
                matrix = fitz.Matrix(self.dpi / 72, self.dpi / 72)
                pix = page.get_pixmap(matrix=matrix)
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                page_text = self._ocr_image(image, lang)

                if page_text.strip():
                    all_text.append(f"=== 第 {page_num + 1} 页 ===\n{page_text.strip()}\n")
                else:
                    all_text.append(f"=== 第 {page_num + 1} 页 ===\n[无文本内容]\n")

            doc.close()

            combined = "\n".join(all_text)
            logger.info("OCR处理完成，共提取 %d 个字符", len(combined))
            return combined

        except Exception as exc:
            logger.error("OCR处理失败: %s", exc)
            raise

    def process_single_page(self, pdf_path: str, page_num: int, lang: str = "auto") -> str:
        try:
            doc = fitz.open(pdf_path)
            page = doc.load_page(page_num)

            matrix = fitz.Matrix(self.dpi / 72, self.dpi / 72)
            pix = page.get_pixmap(matrix=matrix)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            text = self._ocr_image(image, lang)

            doc.close()
            return text

        except Exception as exc:
            logger.error("处理第 %d 页失败: %s", page_num, exc)
            return ""

    def extract_blocks(self, image: Image.Image, lang: str = "auto") -> List[str]:
        text = self._ocr_image(image, lang)
        if not text.strip():
            return []

        separator = "\n\n" if "\n\n" in text else "\n"
        blocks = [block.strip() for block in text.split(separator) if block.strip()]
        return blocks

    def _ocr_image(self, image: Image.Image, lang: str) -> str:
        # 1. 使用 PaddleOCR 进行文本识别
        raw_text = ""
        
        if not self.ocr_engine:
             logger.error("PaddleOCR 引擎未初始化")
             return ""

        try:
            # 将 PIL 图像转换为 numpy 数组
            img_np = np.array(image)
            # 执行 OCR
            logger.info(f"Starting OCR on image of size {image.size} with device={self.device}")
            
            try:
                # 使用 predict 方法
                result = self.ocr_engine.predict(img_np)
            except Exception as e:
                logger.error(f"OCR execution failed: {e}")
                result = None

            # 检查结果是否有效
            is_empty = False
            if result is None:
                is_empty = True
            elif isinstance(result, list) and len(result) == 0:
                is_empty = True
            
            if is_empty and self.device == "gpu":
                logger.warning("PaddleOCR GPU 模式返回空结果，尝试切换到 CPU 模式重试...")
                self.device = "cpu"
                self._init_engine()
                if self.ocr_engine:
                    try:
                        result = self.ocr_engine.predict(img_np)
                    except Exception as e:
                        logger.error(f"OCR retry failed: {e}")
                        result = None
            
            if result is None:
                return ""

            lines = []
            # PaddleOCR predict returns a list of Result objects
            if isinstance(result, list):
                for res in result:
                    # 尝试获取 rec_texts 属性
                    if hasattr(res, 'rec_texts'):
                        lines.extend(res.rec_texts)
                    # 兼容旧版本或字典形式
                    elif hasattr(res, 'keys') and 'rec_texts' in res:
                        lines.extend(res['rec_texts'])
                    # 尝试从 json 属性获取
                    elif hasattr(res, 'json') and isinstance(res.json, dict) and 'rec_texts' in res.json:
                        lines.extend(res.json['rec_texts'])
                    # 尝试打印调试信息如果找不到文本
                    else:
                        try:
                            logger.debug(f"Unknown result format: {res}")
                        except:
                            pass

            raw_text = "\n".join(lines)
            logger.info(f"PaddleOCR extracted {len(raw_text)} chars total")
            
        except Exception as e:
            logger.error(f"PaddleOCR failed: {e}")
            # 如果出错且是 GPU 模式，也尝试回退
            if self.device == "gpu":
                logger.warning(f"PaddleOCR GPU 模式出错 ({e})，尝试切换到 CPU 模式重试...")
                self.device = "cpu"
                self._init_engine()
                return self._ocr_image(image, lang) # 递归调用一次
            return ""

        return raw_text
