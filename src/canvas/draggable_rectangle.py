class DraggableRectangle:
    CORNER_THRESHOLD = 10  # 考虑为角落拖动的距离
    EDGE_THRESHOLD = 5  # 考虑为边缘拖动的距离

    CORNER_CURSORS = {
        'lu': 'top_left_corner',
        'ru': 'top_right_corner',
        'ld': 'bottom_left_corner',
        'rd': 'bottom_right_corner',
    }
    EDGE_CURSORS = {
        'left': 'left_side',
        'right': 'right_side',
        'top': 'top_side',
        'bottom': 'bottom_side',
    }

    def __init__(self, canvas, x1, y1, x2, y2, **kwargs):
        self.canvas = canvas
        self.rectangle = canvas.create_rectangle(x1, y1, x2, y2, **kwargs)

        self.canvas.tag_bind(self.rectangle, '<Motion>', self.on_motion)
        self.canvas.tag_bind(self.rectangle, '<ButtonPress-1>', self.on_press)
        self.canvas.tag_bind(self.rectangle, '<B1-Motion>', self.on_drag)
        self.canvas.tag_bind(self.rectangle, '<ButtonRelease-1>', self.on_release)
        self.canvas.tag_bind(self.rectangle, '<Leave>', self.on_leave)

        self.start_x = 0
        self.start_y = 0
        self.corner = None
        self.edge = None

    def delete(self):
        """从画布中移除矩形。"""
        self.canvas.tag_unbind(self.rectangle, '<Motion>')
        self.canvas.tag_unbind(self.rectangle, '<ButtonPress-1>')
        self.canvas.tag_unbind(self.rectangle, '<B1-Motion>')
        self.canvas.tag_unbind(self.rectangle, '<ButtonRelease-1>')
        self.canvas.tag_unbind(self.rectangle, '<Leave>')

        self.canvas.delete(self.rectangle)

    def check_corner(self, x, y):
        """检查 (x, y) 是否在角落的阈值内。"""
        x1, y1, x2, y2 = self.canvas.coords(self.rectangle)
        corners = {'lu': (x1, y1), 'ru': (x2, y1), 'ld': (x1, y2), 'rd': (x2, y2)}
        for corner, coords in corners.items():
            if abs(x - coords[0]) < self.CORNER_THRESHOLD and abs(y - coords[1]) < self.CORNER_THRESHOLD:
                return corner
        return None
    
    def check_edge(self, x, y):
        """检查 (x, y) 是否在边缘的阈值内。"""
        x1, y1, x2, y2 = self.canvas.coords(self.rectangle)
        if abs(x - x1) < self.EDGE_THRESHOLD and y1 <= y and y <= y2:
            return 'left'
        elif abs(x - x2) < self.EDGE_THRESHOLD and y1 <= y and y <= y2:
            return 'right'
        elif abs(y - y1) < self.EDGE_THRESHOLD and x1 <= x and x <= x2:
            return 'top'
        elif abs(y - y2) < self.EDGE_THRESHOLD and x1 <= x and x <= x2:
            return 'bottom'
        else:
            return None

    def on_motion(self, event):
        corner = self.check_corner(event.x, event.y)
        edge = self.check_edge(event.x, event.y) if not corner else None
        if corner:
            self.canvas.config(cursor=self.CORNER_CURSORS[corner])
        elif edge:
            self.canvas.config(cursor=self.EDGE_CURSORS[edge])

    def on_leave(self, event):
        self.canvas.config(cursor='')

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.corner = self.check_corner(event.x, event.y)
        self.edge = self.check_edge(event.x, event.y) if not self.corner else None

    def on_drag(self, event):
        dx = event.x - self.start_x
        dy = event.y - self.start_y

        x1, y1, x2, y2 = self.canvas.coords(self.rectangle)
        coords = list(self.canvas.coords(self.rectangle))

        if self.corner:
            # 通过移动适当的角落来调整矩形的大小
            if self.corner == 'lu':
                x1, y1 = event.x, event.y
            elif self.corner == 'ru':
                x2, y1 = event.x, event.y
            elif self.corner == 'ld':
                x1, y2 = event.x, event.y
            elif self.corner == 'rd':
                x2, y2 = event.x, event.y
            self.canvas.coords(self.rectangle, x1, y1, x2, y2)
        elif self.edge:
            # Move the edge
            if self.edge == 'left':
                coords[0] += dx
            elif self.edge == 'right':
                coords[2] += dx
            elif self.edge == 'top':
                coords[1] += dy
            elif self.edge == 'bottom':
                coords[3] += dy
            self.canvas.coords(self.rectangle, *coords)
        else:
            # Move the entire rectangle
            self.canvas.move(self.rectangle, dx, dy)

        self.start_x = event.x
        self.start_y = event.y

    def on_release(self, event):
        self.corner = None
        self.edge = None

        # Generate an event to notify that the drag has ended
        self.canvas.event_generate("<<SafeAreaDragEnd>>")