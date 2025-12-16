from dotenv import load_dotenv
import os

# 从 .env 文件加载环境变量
load_dotenv()

class Configuration:

    PROMPT_DIR = os.getenv("PROMPT_DIR", "./prompt")
    CACHE_DIR = os.getenv("CACHE_DIR", "./cache")
    EXPORT_DIR = os.getenv("EXPORT_DIR", "./export")

    TEXT_FONT = os.getenv("TEXT_FONT", "tkDefaultFont")
    TEXT_FONT_SIZE = os.getenv("TEXT_FONT_SIZE", 11)

global_config = Configuration()