import os
import argparse
import requests
from tqdm import tqdm
from urllib.parse import urlparse
import tkinter as tk
from tkinter import font
from src.pdf_viewer import PDFViewer
from src.config import global_config
import pyperclip
from pathlib import Path
from src.markdown_generator import MarkdownGenerator
from src.pdf.pdf import Pdf
import logging

# Configure logging to show INFO level logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def collect_text_from_pdf(pdf):
    text_parts = []
    total_elements = 0
    safe_elements = 0
    visible_elements = 0
    
    for key, element in pdf.iter_elements():
        total_elements += 1
        if element.safe:
            safe_elements += 1
        if element.visible:
            visible_elements += 1
            
        if not element.safe or not element.visible:
            continue
        chain_key = pdf.to_chain.get(key)
        if chain_key is not None and chain_key != key:
            continue
        if chain_key == key:
            original = pdf.chains[key][1]
        else:
            original = element.text
        text_parts.append(original or "")
        
    print(f"Debug: Total elements: {total_elements}, Safe: {safe_elements}, Visible: {visible_elements}")
    return "\n".join(text_parts)

def is_url(string):
    try:
        result = urlparse(string)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def get_filename_from_url(url):
    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    return filename

def download_file(url, destination):
    response = requests.get(url, stream=True)

    # 检查请求是否成功
    if response.status_code == 200:
        total_size_in_bytes= int(response.headers.get('content-length', 0))

        progress_bar = None
        if total_size_in_bytes > 0:
            progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)

        with open(destination, 'wb') as file:
            for chunk in response.iter_content(chunk_size=1024):
                if progress_bar is not None:
                    progress_bar.update(len(chunk))
                file.write(chunk)

        if progress_bar is not None:
            progress_bar.close()

        if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
            print("错误，发生了一些问题。")
            os.remove(destination)
            return False

        print("文件下载成功，保存在 ", destination)
        return True

    else:
        print("下载文件失败: ", response.status_code)
        return False

def get_path_name_to_open(args):
    # 获取输入文件
    path_name = args.f
    if path_name is None:

        # 检查剪贴板中是否有路径
        text = pyperclip.paste()

        if is_url(text):
            print("剪贴板中包含 URL，将其作为输入")
            path_name = text
        elif os.path.isfile(text):
            print("剪贴板中包含路径名，将其作为输入")
            path_name = text

    return path_name

def is_arxiv_url(url):
    return url.startswith('https://arxiv.org/abs/')

def is_hugging_face_url(url):
    return url.startswith('https://huggingface.co/papers/')

def try_download(url, intm_dir):

    print("检测到 URL，正在尝试下载文件...")

    # 如果是 arxiv URL，则下载 PDF
    if is_arxiv_url(url):
        print("检测到 Arxiv URL，正在下载 PDF")
        url = url.replace('https://arxiv.org/abs/', 'https://arxiv.org/pdf/')
        url += ".pdf"
    elif is_hugging_face_url(url):
        print("检测到 Hugging Face URL，正在下载 PDF")
        url = url.replace('https://huggingface.co/papers/', 'https://arxiv.org/pdf/')
        url += ".pdf"

    file_name = get_filename_from_url(url)
    if file_name == "":
        print("无法从 URL 获取文件名")
        return None

    path_name = os.path.join(intm_dir, file_name)

    if os.path.isfile(path_name):
        print(f"File '{path_name}' already exists, skipping download")
    else:
        if not download_file(url, path_name):
            return None
    
    return path_name

def get_arguments():
    # Create the parser
    parser = argparse.ArgumentParser(description='Pdf2md: Loads a PDF file and exports to a text file.')

    # Add the arguments
    parser.add_argument('--f', type=str, help='The PDF file to view')
    parser.add_argument('--l', action='store_true', help='Lists available fonts and exit')
    parser.add_argument('--i', action='store_true', help='Ignores context cache and loads the PDF file again')
    parser.add_argument('--auto_export', action='store_true', help='Automatically export to markdown and exit')

    # Parse the arguments
    args = parser.parse_args()

    return args

def main():
    args = get_arguments()

    root = tk.Tk()
    root.title("pdf2md")
    root.geometry('1200x800')  # set initial window size

    if args.l:
        print("Available fonts:")
        fonts=list(font.families())
        fonts.sort()
        for f in fonts:
            print(f)
        return

    path_name = get_path_name_to_open(args)
    if path_name is None:
        print("No input file specified")
        return
    
    intm_dir = global_config.CACHE_DIR
    intm_dir = os.path.abspath(intm_dir)
    os.makedirs(intm_dir, exist_ok=True)

    export_dir = global_config.EXPORT_DIR
    export_dir = os.path.abspath(export_dir)
    os.makedirs(export_dir, exist_ok=True)

    # download file if URL
    if is_url(path_name):
        path_name = try_download(path_name, intm_dir)
        if path_name is None:
            return

    if args.auto_export:
        print(f"Processing {path_name} for auto-export...")
        # Initialize Pdf which will trigger OCR if needed
        pdf = Pdf(path_name, intm_dir, args.i)
        
        original_text = collect_text_from_pdf(pdf)
        
        if not original_text.strip():
            print("No text content to export.")
            return

        base_name = Path(path_name).stem
        output_path = Path(export_dir) / f"{base_name}_structured.md"
        print("Generating structured Markdown...")
        
        markdown_generator = MarkdownGenerator()
        try:
            # 增加超时时间到 300秒
            markdown_content = markdown_generator.generate_markdown_with_options(original_text, use_ai=True, timeout=300)
            output_path.write_text(markdown_content, encoding="utf-8")
            print(f"Structured Markdown saved to: {output_path}")
        except Exception as exc:
            print(f"Export failed: {exc}")
        return

    # show GUI
    app = PDFViewer(path_name, intm_dir, export_dir, args.i, master=root)
    app.mainloop()

if __name__ == "__main__":
    main()
