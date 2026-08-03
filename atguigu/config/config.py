from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv(
    override=True
)  # override=True强制用 .env 文件中的值覆盖掉系统环境变量的值。
# load_dotenv 从当前目录开始，递归向上查找.env文件。最先找到的那个.env文件会被加载。

ROOT_DIR = Path(__file__).parents[2]
DATA_DIR = ROOT_DIR / "atguigu" / "data"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_DIR = DATA_DIR / "output"


class MineruConfig:
    mineru_token = os.getenv("mineru_token")
    mineru_base_url = os.getenv("mineru_base_url")


class LLMConfig:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE")
    default_model = os.getenv("LLM_DEFAULT_MODEL")
    temperature = float(os.getenv("LLM_DEFAULT_TEMPERATURE"))
    vlm_model = os.getenv("VL_MODEL")
    item_model = os.getenv("ITEM_MODEL")
