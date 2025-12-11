from PIL import Image, ImageTk
from src.canvas.element_setting import get_setting
from src.canvas.utility import check_overlap

class PdfElementManager:
    def __init__(self, canvas):
        self.canvas = canvas
        self.elements = []
        self.selected_elements = []

    def add(self, key, rectangle, image_id, image):
        self.elements.append((key, rectangle, image_id, image))

    def clear(self):
        self.elements = []
        self.selected_elements = []

    def get_selected(self):
        return self.selected_elements

    def find_by_key(self, key):
        return next((element for element in self.elements if element[0] == key), None)

    def find_by_point(self, x, y):
        return next((element for element in self.elements if self.is_inside_rectangle(x, y, element[1])), None)

    def add_element(self, mode, key, index, safe, visible, can_be_split, x1, y1, x2, y2, c1, c2):
        settings = get_setting(mode, safe, visible, can_be_split)
        outline = settings['outline']
        fill = settings['fill']
        dash = settings.get('dash')
        width = settings.get('width')

        alpha = int(0.25 * 255)
        img_fill = self.canvas.winfo_rgb(fill) + (alpha,)
        
        image = Image.new('RGBA', (int(x2-x1), int(y2-y1)), img_fill)
        image = ImageTk.PhotoImage(image)
        image_id = self.canvas.create_image(x1, y1, image=image, anchor='nw')
        self.canvas.itemconfig(image_id, state='hidden')  # 初始隐藏图像

        # 创建矩形
        kwargs = { 'outline': outline, 'width': width }
        if dash is not None:
            kwargs.update({ 'dash': dash })
        rectangle = self.canvas.create_rectangle(x1, y1, x2, y2, **kwargs)

        # 在矩形内的左上角添加文本。
        if safe and visible:
            text_id = self.canvas.create_text(x1 - 5 - width/2, y1 - width/2, text=str(index), anchor='ne', fill='white')  # 将文本放置在距离左上角 5 像素的位置。
            text_bg = self.canvas.create_rectangle(self.canvas.bbox(text_id), fill=fill)
            self.canvas.tag_lower(text_bg, text_id)

            if c1 is not None:
                # 使用 == 进行值比较
                text_id = self.canvas.create_text(x1 + 2 - width/2, y1 + 2 - width/2, text="concat" if c1 == 1 else "join", font=("TkDefaultFont", 7), anchor='nw', fill='white')
                text_bg = self.canvas.create_rectangle(self.canvas.bbox(text_id), fill=fill)
                self.canvas.tag_lower(text_bg, text_id)

            if c2 is not None:
                # 使用 == 进行值比较
                text_id = self.canvas.create_text(x2 - 2 - width/2, y2 - 2 - width/2, text="concat" if c2 == 1 else "join", font=("TkDefaultFont", 7), anchor='se', fill='white')
                text_bg = self.canvas.create_rectangle(self.canvas.bbox(text_id), fill=fill)
                self.canvas.tag_lower(text_bg, text_id)

        self.elements.append((key, rectangle, image_id, image))
        return rectangle

    def is_inside_rectangle(self, x, y, rectangle):
        """检查点 (x, y) 是否在给定的矩形内。"""
        x1, y1, x2, y2 = self.canvas.coords(rectangle)
        return x1 <= x <= x2 and y1 <= y <= y2

    def update_hover(self, x, y):
        for _, rectangle, image_id, _ in self.elements:
            if self.is_inside_rectangle(x, y, rectangle):
                self.canvas.itemconfig(image_id, state='normal')  # 显示图像
            else:
                self.canvas.itemconfig(image_id, state='hidden')  # 隐藏图像

    def update_drag(self, drag_id):
        self.selected_elements = []

        if drag_id is not None:
            drag_rect = self.canvas.coords(drag_id)
            for key, rectangle, image_id, _ in self.elements:
                element_rect = self.canvas.coords(rectangle)
                if check_overlap(drag_rect, element_rect):
                    self.canvas.itemconfig(image_id, state='normal')  # 显示图像
                    self.selected_elements.append(key)
                else:
                    self.canvas.itemconfig(image_id, state='hidden')  # 隐藏图像
        else:
            for _, rectangle, image_id, _ in self.elements:
                self.canvas.itemconfig(image_id, state='hidden')  # 隐藏图像
