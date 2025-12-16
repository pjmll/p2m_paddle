import os
import threading
import webbrowser
from pathlib import Path
from typing import Iterable, Tuple

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont

from src.pdf.pdf import Pdf
from src.toolbar.pdf_viewer_toolbar import PdfViewerToolbar
from src.toolbar.pdf_viewer_toolbar_item import PdfViewerToolbarItem
from src.canvas.pdf_canvas import PdfCanvas
from src.config import global_config
from src.markdown_generator import MarkdownGenerator
from src.knowledge_graph_generator import KnowledgeGraphGenerator


class PDFViewer(tk.Frame):
    """主 Tk 查看器，协调 OCR、导出和 KG 生成。"""

    def __init__(self, pdf_path: str, intm_dir: str, export_dir: str, ignore_cache: bool = False, master: tk.Tk | None = None):
        super().__init__(master)
        self.master = master or tk.Tk()
        self.master.title(f"pdf2md - {os.path.basename(pdf_path)}")

        # 尝试最大化窗口，提供更大的阅读空间
        try:
            if self.master.tk.call('tk', 'windowingsystem') == 'win32':
                self.master.state('zoomed')
            else:
                self.master.attributes('-zoomed', True)
        except Exception:
            pass

        self.pack(fill="both", expand=True)

        self.pdf_path = os.path.abspath(pdf_path)
        self.intm_dir = os.path.abspath(intm_dir)
        self.export_dir = os.path.abspath(export_dir)
        os.makedirs(self.intm_dir, exist_ok=True)
        os.makedirs(self.export_dir, exist_ok=True)

        # 核心服务
        self.pdf = Pdf(self.pdf_path, self.intm_dir, ignore_cache)
        self.markdown_generator = MarkdownGenerator()

        self._kg_button = None

        self._build_ui()
        self.after_idle(self._initial_load)
        self._set_status("安全区域模式：拖动红色矩形可限定正文范围。")

    # ------------------------------------------------------------------
    # UI 设置
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # 工具栏
        self.toolbar = PdfViewerToolbar(self)
        self.toolbar.bind("<<ToolbarButtonClicked>>", self.on_toolbar_button_clicked)
        self.toolbar.bind("<<ExportButtonClicked>>", self.on_export_button_clicked)
        self.toolbar.bind("<<GenerateKGButtonClicked>>", self.on_generate_kg_button_clicked)
        for i in range(1, 6):
            self.master.bind(str(i), self.toolbar.key_press)
        self._kg_button = getattr(self.toolbar, "kg_button", None)

        # 分割窗口（经典的 Tk 变体，具有更广泛的兼容性）
        self.paned_window = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            sashwidth=6,
            sashrelief=tk.RAISED,
            showhandle=False,
        )
        self.paned_window.pack(fill="both", expand=True)

        self.canvas = PdfCanvas(self.paned_window, self.pdf, background="#202020", highlightthickness=0)
        self.canvas.config(width=760)
        self.canvas.bind("<<PageChanged>>", self.on_page_changed_by_canvas)
        self.canvas.bind("<<SafeAreaChanged>>", self.on_safe_area_changed_by_canvas)
        self.canvas.bind("<<DragEnd>>", self.on_drag_end_by_canvas)
        self.canvas.bind("<<ElementLeftClicked>>", self.on_element_left_clicked_by_canvas)
        self.canvas.bind("<<ElementRightClicked>>", self.on_element_right_clicked_by_canvas)
        self.master.bind("<Escape>", self.canvas.on_escape)
        self.paned_window.add(self.canvas, minsize=320)

        font_name = getattr(global_config, "TEXT_FONT", "TkDefaultFont")
        try:
            font_size = int(getattr(global_config, "TEXT_FONT_SIZE", 11))
        except (TypeError, ValueError):
            font_size = 11

        self.text_widget = tk.Text(
            self.paned_window,
            wrap="word",
            font=(font_name, font_size),
            spacing3=6,
            state=tk.DISABLED,
        )
        self.text_widget.config(width=48)
        self.paned_window.add(self.text_widget, minsize=200)
        self.after(100, self._set_initial_sash_position)

        self.status_label = tk.Label(self, anchor="w")
        self.status_label.pack(side="bottom", fill="x")

    def _initial_load(self) -> None:
        self.update_idletasks()
        self.canvas.update_idletasks()
        self.canvas.change_page(0)
        self._refresh_text_widget()

    def _set_initial_sash_position(self) -> None:
        try:
            width = self.paned_window.winfo_width()
            if width <= 1:
                self.after(100, self._set_initial_sash_position)
                return
            # 将左侧 PDF 区域的初始宽度比例调整为 50%
            self.paned_window.sash_place(0, int(width * 0.50), 0)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 事件处理程序
    # ------------------------------------------------------------------
    def on_toolbar_button_clicked(self, _event=None) -> None:
        mode = self.toolbar.get_current_selection()
        self.canvas.change_mode(mode)

        match mode:
            case _:
                self._set_status("")

    def on_safe_area_changed_by_canvas(self, _event=None) -> None:
        margin = getattr(self.canvas, "get_new_safe_margin", lambda: None)()
        if margin is not None:
            self.pdf.set_safe_margin(margin)
            self._persist_context()
        self.canvas.redraw()
        self._refresh_text_widget()
        self._set_status("安全区域已更新。")

    def on_drag_end_by_canvas(self, _event=None) -> None:
        self._persist_context()
        self.canvas.redraw()
        self._refresh_text_widget()

    def on_element_left_clicked_by_canvas(self, _event=None) -> None:
        key = getattr(self.canvas, "get_clicked_element", lambda: None)()
        if key is None:
            return

        mode = self.toolbar.get_current_selection()
        if mode == PdfViewerToolbarItem.Visibility:
            self.pdf.toggle_visibility(key)
        else:
            return

        self._persist_context()
        self.canvas.redraw()
        self._refresh_text_widget()

    def on_element_right_clicked_by_canvas(self, _event=None) -> None:
        key = getattr(self.canvas, "get_clicked_element", lambda: None)()
        if key is None:
            return

        # 默认右键切换可见性
        self.pdf.toggle_visibility(key)
        self._persist_context()
        self.canvas.redraw()
        self._refresh_text_widget()

    def on_page_changed_by_canvas(self, _event=None) -> None:
        page = self.canvas.get_current_page()
        total = self.pdf.get_page_number()
        self._refresh_text_widget()
        self._set_status(f"当前页：{page + 1} / {total}")

    def on_export_button_clicked(self, _event=None) -> None:
        original_text = self._collect_original_text()
        if not original_text.strip():
            messagebox.showinfo("Export", "没有可导出的文本内容。")
            return

        base_name = Path(self.pdf_path).stem
        output_path = Path(self.export_dir) / f"{base_name}_structured.md"
        self._set_status("正在生成结构化 Markdown...", transient=False)

        def worker() -> None:
            error = None
            markdown_content = ""
            try:
                # 增加超时时间到 300秒，防止长文档处理超时
                markdown_content = self.markdown_generator.generate_markdown_with_options(original_text, use_ai=True, timeout=300)
                output_path.write_text(markdown_content, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                error = str(exc)

            def finish() -> None:
                if error:
                    messagebox.showerror("Export", f"导出失败：{error}")
                    self._set_status("Markdown 导出失败。")
                else:
                    # Update text widget with markdown content
                    self.text_widget.config(state=tk.NORMAL)
                    self.text_widget.delete("1.0", tk.END)
                    self.text_widget.insert("1.0", markdown_content)
                    self.text_widget.config(state=tk.DISABLED)
                    
                    messagebox.showinfo("Export", f"结构化 Markdown 已保存到:\n{output_path}")
                    self._set_status("Markdown 导出完成。")

            self.master.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def on_generate_kg_button_clicked(self, _event=None) -> None:
        base_name = Path(self.pdf_path).stem
        md_path = Path(self.export_dir) / f"{base_name}_structured.md"
        if not md_path.exists():
            messagebox.showerror("Generate KG", f"未找到结构化 Markdown 文件，请先执行 Export MD。\n预期路径：{md_path}")
            return

        md_content = md_path.read_text(encoding="utf-8")
        if not md_content.strip():
            messagebox.showerror("Generate KG", "Markdown 文件为空，无法生成知识图谱。")
            return

        button = self._kg_button
        if button:
            button.config(state=tk.DISABLED, text="Generating…")
        self._set_status("知识图谱生成中...", transient=False)

        def worker() -> None:
            error = None
            output_html = None
            try:
                kg = KnowledgeGraphGenerator()
                output_html = kg.generate_knowledge_graph(md_content, Path(self.export_dir), base_name)
            except Exception as exc:  # noqa: BLE001
                error = str(exc)

            def finish() -> None:
                if button:
                    button.config(state=tk.NORMAL, text="Generate KG")
                if error:
                    messagebox.showerror("Generate KG", error)
                    self._set_status("知识图谱生成失败。")
                elif output_html:
                    self._set_status("知识图谱已生成。")
                    try:
                        webbrowser.open(Path(output_html).resolve().as_uri())
                    except Exception:  # noqa: BLE001
                        pass

            self.master.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # 辅助函数
    # ------------------------------------------------------------------
    def _iter_visible_heads(self, page: int | None = None) -> Iterable[Tuple[int, object, str]]:
        iterator = self.pdf.iter_elements_page(page) if page is not None else self.pdf.iter_elements()
        for key, element in iterator:
            if not element.safe or not element.visible:
                continue
            chain_key = self.pdf.to_chain.get(key)
            if chain_key is not None and chain_key != key:
                continue
            if chain_key == key:
                original = self.pdf.chains[key][1]
            else:
                original = element.text
            yield key, element, original or ""

    def _collect_original_text(self) -> str:
        return "\n".join(original for _, _, original in self._iter_visible_heads())

    def _refresh_text_widget(self) -> None:
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete("1.0", tk.END)

        for _, _, original in self._iter_visible_heads(self.canvas.get_current_page()):
            self.text_widget.insert(tk.END, f"{original}\n\n")

        self.text_widget.config(state=tk.DISABLED)

    def _set_status(self, text: str, *, transient: bool = True, delay_ms: int = 4000) -> None:
        self.status_label.config(text=text)
        if transient and text:
            self.after(delay_ms, lambda: self.status_label.config(text=""))

    def _persist_context(self) -> bool:
        """将 PDF 上下文持久化到磁盘，失败时显示错误。"""
        try:
            self.pdf.save()
            return True
        except PermissionError as exc:
            messagebox.showerror(
                "保存失败",
                "无法写入缓存文件，请检查 cache 目录的权限或删除旧的 *.context 文件后重试。\n"
                f"错误详情: {exc}",
            )
            self._set_status("保存缓存失败，部分操作可能不会生效。")
            return False
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("保存失败", f"意外错误：{exc}")
            self._set_status("保存缓存失败，部分操作可能不会生效。")
            return False