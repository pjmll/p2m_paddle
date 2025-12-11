from enum import Enum, auto


class PdfViewerToolbarItem(Enum):
    SafeArea = auto(), "Safe Area"
    Visibility = auto(), "Visibility"
    Body = auto(), "Body"
    MergeAndSplit = auto(), "Concat / Split"
    JoinAndSplit = auto(), "Join / Split"
    Order = auto(), "Order"
    Concat = auto(), "Chain"
    Translate = auto(), "Translate"
    Export = auto(), "Export MD"
    GenerateKG = auto(), "Generate KG"

    # 重写 __new__ 方法以存储显示名称以及默认的 Enum 值
    def __new__(cls, value, display_name):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.display_name = display_name
        return obj