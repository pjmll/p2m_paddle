import tkinter as tk
from PIL import Image, ImageTk
from src.pdf.pdf_element import PdfRect
from src.toolbar.pdf_viewer_toolbar_item import PdfViewerToolbarItem
from src.canvas.pdf_element_manager import PdfElementManager
from src.canvas.draggable_rectangle import DraggableRectangle
from src.canvas.utility import get_image_extent

class PdfCanvas(tk.Canvas):
    def __init__(self, master=None, pdf=None, **kwargs):
        super().__init__(master, **kwargs)
        self.pdf = pdf
        
        self.bind('<Motion>', self.on_mouse_move)
        self.bind("<Configure>", self.on_resize)
        self.bind("<Button-3>", self.on_mouse_rb_down)

        self.drag_data = {"x": 0, "y": 0, "item": None}
        self.bind("<ButtonPress-1>", self.on_drag_start)
        self.bind("<B1-Motion>", self.on_drag_motion)
        self.bind("<ButtonRelease-1>", self.on_drag_stop)

        # 绑定鼠标滚轮事件
        self.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows
        self.bind("<Button-4>", self.on_scroll_up)      # linux
        self.bind("<Button-5>", self.on_scroll_down)    # linux

        # 绑定拖动事件
        self.bind("<<SafeAreaDragEnd>>", self.on_safe_area_drag_end)

        self.current_page = 0
        self.elm = PdfElementManager(self)

        self.mode = None
        self.drag_enabled = False
        self.pivot = None

    def get_pivot(self):
        return self.pivot
    
    def set_pivot(self, pivot):
        self.pivot = pivot

    def change_page(self, new_page_number):
        if new_page_number >= 0 and new_page_number < self.pdf.get_page_number():
            self.current_page = new_page_number
            self.pivot = None
            self.redraw()
            self.event_generate('<<PageChanged>>')

    def get_current_page(self):
        return self.current_page

    def change_mode(self, new_mode):
        self.mode = new_mode
        self.pivot = None
        if self.mode == PdfViewerToolbarItem.Visibility or self.mode == PdfViewerToolbarItem.MergeAndSplit or self.mode == PdfViewerToolbarItem.JoinAndSplit or self.mode == PdfViewerToolbarItem.Body:
            self.drag_enabled = True
        else:
            self.drag_enabled = False
        self.redraw()
   
    def redraw(self):
        self.clear()
        self.show_page(
            self.pdf.get_pixmap(self.current_page),
            self.pdf.get_page_extent(self.current_page), 
            self.pdf.get_safe_margin(),
            self.pdf.iter_elements_page(self.current_page))

    def clear(self):
        if hasattr(self, 'safe_area') and self.safe_area is not None:
            self.safe_area.delete()
            self.safe_area = None
        self.delete('all')  # 删除所有画布项目
        self.elm.clear()
        self.photoimg = None

    def show_page(self, pix, page_extent, safe_margin, elements):
        page_width, page_height = page_extent

        # 将 PyMuPDF 页面转换为 PIL 图像并调整大小以适应窗口

        #img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img = pix.copy()
        img = img.resize((get_image_extent(self, pix)), Image.LANCZOS)

        # 将 PIL 图像转换为 PhotoImage 并显示在画布上
        self.photoimg = ImageTk.PhotoImage(img)
        self.create_image(0, 0, image=self.photoimg, anchor='nw')

        # 在 PIL 图像上绘制 pdfminer 布局
        self.scale_factor_x = img.width / page_width
        self.scale_factor_y = img.height / page_height

        #for element in pdfminer_page:
        index = 1

        prev_body_element = self.pdf.find_last_body_element_until(self.current_page)

        for key, element in elements:
            x1, y1, x2, y2 = element.bbox
            x1, x2 = sorted([x1 * self.scale_factor_x, x2 * self.scale_factor_x])
            x2 = max(x2, x1 + 1)  # Ensure x2 is always greater than x1

            # element.bbox is in PDF coordinates (origin bottom-left). Map to canvas by flipping y:
            y1, y2 = sorted([img.height - y1 * self.scale_factor_y, img.height - y2 * self.scale_factor_y])
            y2 = max(y2, y1 + 1)  # Ensure y2 is always greater than y1

            # Create the rectangle and save the handle
            option = None
            if self.mode == PdfViewerToolbarItem.MergeAndSplit or self.mode == PdfViewerToolbarItem.JoinAndSplit:
                option = element.can_be_split()
            elif self.mode == PdfViewerToolbarItem.Order:
                option = key == self.pivot
            elif self.mode == PdfViewerToolbarItem.Body:
                option = element.body
            elif self.mode == PdfViewerToolbarItem.Translate:
                option = self.pdf.can_be_translated(key)
            elif self.mode == PdfViewerToolbarItem.Concat:
                option = 0
                if element.safe and element.visible and element.body:
                    if element.contd is not None:
                        option = element.contd
                    else:
                        # if the element is not continuing one, we need to check the previous element is continuing one or not
                        if prev_body_element is not None:
                            if prev_body_element.contd == 1:
                                option = 3
                            elif prev_body_element.contd == 2:
                                option = 4

            c1 = c2 = None
            if element.safe and element.visible and element.body:
                c1 = prev_body_element.contd if prev_body_element is not None else None
                c2 = element.contd

            self.elm.add_element(
                self.mode, 
                key, 
                index, 
                element.safe, 
                element.visible, 
                option,
                x1, y1, x2, y2,
                c1, c2)
            
            if element.visible and element.safe:
                index += 1
                if element.body:
                    prev_body_element = element

        # 计算 PDF 坐标中的安全区域（注意：PDF y 轴原点在左下角）
        # 这反映了 Pdf.recalculate_safe_area 中的计算，该计算使用
        # (page.width * margin.x1, page.height * (1 - margin.y2), ...)
        safe_pdf_x1 = page_width * safe_margin.x1
        safe_pdf_x2 = page_width * safe_margin.x2
        safe_pdf_y1 = page_height * (1 - safe_margin.y2)
        safe_pdf_y2 = page_height * (1 - safe_margin.y1)

        # 使用与元素矩形相同的变换（y 翻转）将 PDF 坐标转换为图像（画布）坐标
        safe_x1 = safe_pdf_x1 * self.scale_factor_x
        safe_x2 = safe_pdf_x2 * self.scale_factor_x
        safe_y1 = img.height - safe_pdf_y1 * self.scale_factor_y
        safe_y2 = img.height - safe_pdf_y2 * self.scale_factor_y

        # 确保顺序
        safe_x1, safe_x2 = sorted([safe_x1, safe_x2])
        safe_y1, safe_y2 = sorted([safe_y1, safe_y2])

        if self.mode == PdfViewerToolbarItem.SafeArea:
            self.safe_area = DraggableRectangle(self, safe_x1, safe_y1, safe_x2, safe_y2, outline="red", width=2, dash=(5, 3))
        else:
            # self.create_rectangle(safe_x1, safe_y1, safe_x2, safe_y2, outline="gray40", dash=(5, 3))
            pass

    def on_mouse_wheel(self, event):
        """处理鼠标滚轮滚动。"""
        if event.delta > 0:
            self.change_page(self.current_page - 1)
        else:
            self.change_page(self.current_page + 1)

    def on_scroll_up(self, event):
        self.change_page(self.current_page - 1)

    def on_scroll_down(self, event):
        self.change_page(self.current_page + 1)

    def on_resize(self, event):
        self.redraw()

    def on_drag_start(self, event):
        """开始拖动对象"""
        # 记录项目及其位置
        self.drag_data["item"] = None   # 在鼠标移动之前，我们不认为它是拖动
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
        self.drag_data["moved"] = False
        
        x, y = self.canvasx(event.x), self.canvasy(event.y)
        found = self.elm.find_by_point(x, y)
        self.drag_data["start_item"] = found[0] if found is not None else None

    def on_drag_motion(self, event):
        """处理对象的拖动"""
        # 计算鼠标移动了多少
        delta_x = event.x - self.drag_data["x"]
        delta_y = event.y - self.drag_data["y"]

        if self.drag_enabled:
            if not self.drag_data["moved"]:
                # 现在我们开始拖动
                self.drag_data["moved"] = True
                self.drag_data["item"] = self.create_rectangle(
                    self.canvasx(event.x), self.canvasy(event.y), 
                    self.canvasx(event.x) + delta_x, self.canvasy(event.y) + delta_y, 
                    outline="green",
                    dash = (5, 3))
            else:
                self.coords(
                    self.drag_data["item"], 
                    self.canvasx(self.drag_data["x"]), self.canvasy(self.drag_data["y"]), 
                    self.canvasx(self.drag_data["x"]) + delta_x, self.canvasy(self.drag_data["y"]) + delta_y)

            self.elm.update_drag(self.drag_data["item"])
        else:
            self.elm.update_hover(self.canvasx(event.x), self.canvasy(event.y))

    def on_drag_stop(self, event):
        """结束拖动对象"""
        if self.drag_data["moved"]:
            if self.drag_data["item"] is not None:
                # 拖动完成，因此我们需要更新拖动重叠
                self.elm.update_drag(self.drag_data["item"])
                self.event_generate("<<DragEnd>>")
                self.delete(self.drag_data["item"])
        else:
            # 鼠标未移动，因此它是单击
            x, y = self.canvasx(event.x), self.canvasy(event.y)
            found = self.elm.find_by_point(x, y)
            last_element = found[0] if found is not None else None
            
            if self.drag_data["start_item"] == last_element:
                self.clicked_element = last_element
                self.event_generate("<<ElementLeftClicked>>")

        # 重置拖动信息
        self.drag_data["item"] = None
        self.drag_data["x"] = 0
        self.drag_data["y"] = 0
        self.drag_data["moved"] = False
        self.drag_data["start_item"] = None

    def on_escape(self, event):
        self.pivot = None
        self.redraw()

    def on_mouse_rb_down(self, event):
        """处理鼠标在画布上的移动。"""
        x, y = self.canvasx(event.x), self.canvasy(event.y)
        found = self.elm.find_by_point(x, y)
        self.clicked_element = found[0] if found is not None else None
        self.event_generate("<<ElementRightClicked>>")
       
    def get_clicked_element(self):
        return self.clicked_element
    
    def get_selected_elements(self):
        return self.elm.get_selected()

    def on_mouse_move(self, event):
        """处理鼠标在画布上的移动。"""
        x, y = self.canvasx(event.x), self.canvasy(event.y)
        self.elm.update_hover(x, y)

    def on_safe_area_drag_end(self, event):
        # Update the safe_margin based on the new position of safe_area
        x1, y1, x2, y2 = self.coords(self.safe_area.rectangle)
        page_width, page_height = self.pdf.get_page_extent(self.current_page)
        
        self.new_safe_margin = PdfRect(
                x1 / self.scale_factor_x / page_width,
                y1 / self.scale_factor_y / page_height,
                x2 / self.scale_factor_x / page_width,
                y2 / self.scale_factor_y / page_height
            )
        
        self.event_generate("<<SafeAreaChanged>>")

    def get_new_safe_margin(self):
        return self.new_safe_margin