import tkinter as tk
from src.toolbar.pdf_viewer_toolbar_item import PdfViewerToolbarItem

class PdfViewerToolbar(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent, bd=1, relief=tk.RAISED)
        self.pack(side=tk.TOP, fill=tk.X)

        self.buttons = {}

        # 仅添加工具栏项目的核心子集以简化 UI
        core_items = [PdfViewerToolbarItem.Translate]
        for item in core_items:
            self.add_button(item)

        self.button_states = {item: False for item in self.buttons}
        self.current_selection = None

        # 右侧的导出和 KG 按钮
        self.export_button = tk.Button(self, text="Export MD", command=lambda: self.export())
        self.export_button.pack(side='right', padx=2, pady=2)

        self.kg_button = tk.Button(self, text="Generate KG", command=lambda: self.generate_kg())
        self.kg_button.pack(side='right', padx=2, pady=2)

        # 导出当前页面的翻译（原文 + 译文）
        self.export_translations_button = tk.Button(self, text="Export Translations", command=lambda: self.export_translations())
        self.export_translations_button.pack(side='right', padx=2, pady=2)

        # 显示渲染为图像的翻译（如果 Tk 无法渲染 CJK 字体，这很有用）
        self.show_trans_image_button = tk.Button(self, text="Show Translations Image", command=lambda: self.show_translations_image())
        self.show_trans_image_button.pack(side='right', padx=2, pady=2)

        # 保持稳定的项目列表以进行键盘快捷键映射
        self.items = core_items

    def key_press(self, event):
        if event.char.isdigit():
            index = int(event.char) - 1  # 索引从 0 开始，所以减 1
            if 0 <= index < len(self.items):  # 检查索引是否有效
                self.toggle_button(self.items[index])  # 获取项目并切换

    def add_button(self, item):
        self.buttons[item] = tk.Button(self, text=item.display_name, command=lambda item=item: self.toggle_button(item))
        self.buttons[item].pack(side='left', padx=2, pady=2)

    def toggle_button(self, item):
        # 重置所有按钮
        for button_item, button_state in self.button_states.items():
            self.button_states[button_item] = False
            self.buttons[button_item].config(relief=tk.RAISED)

        # 切换点击的按钮
        self.button_states[item] = not self.button_states[item]
        if self.button_states[item]:
            self.buttons[item].config(relief=tk.SUNKEN)

        self.current_selection = item

        self.event_generate("<<ToolbarButtonClicked>>", when="tail")

    def get_current_selection(self):
        return self.current_selection
    
    def export(self):
        self.event_generate("<<ExportButtonClicked>>", when="tail")

    def export_translations(self):
        self.event_generate("<<ExportTranslationsClicked>>", when="tail")

    def show_translations_image(self):
        self.event_generate("<<ShowTranslationsImageClicked>>", when="tail")

    def generate_kg(self):
        self.event_generate("<<GenerateKGButtonClicked>>", when="tail")