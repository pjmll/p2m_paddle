def check_overlap(rect1, rect2):
    # 矩形定义为 (x1, y1, x2, y2)
    x1_rect1, y1_rect1, x2_rect1, y2_rect1 = rect1
    x1_rect2, y1_rect2, x2_rect2, y2_rect2 = rect2

    # 检查一个矩形是否在另一个矩形的右侧
    if x1_rect1 > x2_rect2 or x1_rect2 > x2_rect1:
        return False

    # 检查一个矩形是否在另一个矩形的上方
    if y1_rect1 > y2_rect2 or y1_rect2 > y2_rect1:
        return False

    return True

def get_image_extent(widget, pix):
    window_width = max(widget.winfo_width(), 1)  # 确保宽度至少为 1
    window_height = max(widget.winfo_height(), 1)  # 确保高度至少为 1

    window_ratio = window_width / window_height
    page_ratio = pix.width / pix.height

    if window_ratio < page_ratio:
        # 窗口相对于页面较高，因此根据宽度进行缩放
        new_width = window_width
        new_height = max(int(window_width / page_ratio), 1)  # 确保高度至少为 1
    else:
        # 窗口相对于页面较宽，因此根据高度进行缩放
        new_height = window_height
        new_width = max(int(window_height * page_ratio), 1)  # 确保宽度至少为 1

    return new_width, new_height
