# p2d

`p2d` 是一款面向科研 PDF 的可视化处理工具，可完成扫描版 OCR、交互式段落管理、翻译、结构化 Markdown 导出与知识图谱生成，帮助快速整理和理解论文内容。

## 核心特性

- **交互式 PDF 查看器**：左侧渲染原始页面，右侧同步显示段落及译文。
- **扫描版 OCR**：利用 PaddleOCR 进行光学字符识别（OCR）从 PDF 页面中提取文本，并结合 Qwen 系列大语言模型将提取的文本结构化为 Markdown，输出可编辑的正文。
- **模型与集成**：OCR 使用 PaddleOCR，文本结构化与语义理解使用 Qwen（或 DashScope/OpenAI 兼容模型），可通过环境变量配置具体模型或 API。
- **结构化 Markdown 导出**：按照当前可见正文导出层次清晰的 Markdown。
- **知识图谱生成**：读取 Markdown 内容提取实体关系，输出交互式 HTML 图谱。
- **段落整理工具栏**：安全区域调整、正文切换、顺序重排、可见性过滤等操作一应俱全。

## 环境准备

- Python 3.12
- DashScope / OpenAI 兼容的多模态大模型 API Key（用于 OCR 与翻译）
- 可选：RapidAPI DeepL 的密钥，用于翻译与图谱生成

### 安装步骤

```bash
git clone https://github.com/pjmll/p2m.git
cd p2d

python -m venv .venv_p2d
source .venv_p2d/bin/activate  # Windows 请使用 .venv_p2d\Scripts\activate

pip install -r requirements.txt
```

创建 `.env` 文件（示例）：

```env
CACHE_DIR=./cache
EXPORT_DIR=./export
PROMPT_DIR=./prompt

TEXT_FONT=tkDefaultFont
TEXT_FONT_SIZE=11

# RapidAPI DeepL（可选）
DEEPL_RAPID_API_KEY=your_rapidapi_key
DEEPL_RAPID_API_HOST=deepl-translator.p.rapidapi.com
DEEPL_RAPID_API_SRC_LANG=EN
DEEPL_RAPID_API_DST_LANG=ZH

# DashScope / OpenAI 兼容接口
DASHSCOPE_API_KEY=your_dashscope_key
DASHSCOPE_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen3-max
OCR_MODEL=qwen3-vl-plus
OCR_MAX_OUTPUT_TOKENS=2048
```
```

## 启动应用

```bash
python -m src.main --f /path/to/document.pdf
```

常用参数：

- `--i` 重新解析 PDF（忽略缓存）
- `--l` 列出所有可用字体后退出

支持直接输入 Arxiv 或 HuggingFace 论文页链接，程序会自动转换为对应 PDF 地址。

## 界面操作速览

- **Safe Area**：拖动红框限定整篇文档的有效内容区域。
- **Body**：点击段落切换是否视为正文，直接影响导出结果。
- **Order**：先选锚点再点击其他段落，可调整阅读顺序。
- **Export MD**：基于当前可见正文生成结构化 Markdown。
- **Generate KG**：读取最近导出的 Markdown，生成知识图谱 HTML。

## 输出位置

- Markdown：`<EXPORT_DIR>/<pdf-name>_structured.md`
- 知识图谱：`<EXPORT_DIR>/<pdf-name>_knowledge_graph.html`

解析缓存存放于 `CACHE_DIR`，可手动删除或使用 `--i` 参数刷新。

## 常见问题

- **无 PDF 画面**：确认大模型 API Key 配置正确且缓存目录可写；必要时删除同名 `.context` 文件后重试。
- **翻译失败**：检查 `.env` 中密钥是否正确，并查看终端输出的具体错误。
- **知识图谱为空**：请先成功导出 Markdown，确认文本中包含可识别的实体信息。

## 许可证

详见仓库内 `LICENSE` 文件。欢迎在遵循协议的前提下扩展或二次开发。
- Extraction of tables in the PDF.
- Proper parsing or image extraction of equations in the PDF.
- Automatic identification and modification of text attributes such as title, subtitle, and body text through font analysis.
- Export to markdown (md) files with formatting.
- Export to MHTML files, including images, tables, and equations.

python -m src.main --f /home/lrj/下载/p2d/3.pdf

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv_win\Scripts\Activate.ps1

python -m src.main --f D:\p2m\新时代中国特色社会主义理论与实践（2024年版）_27-59.pdf