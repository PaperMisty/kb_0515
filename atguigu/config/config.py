from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv(override=True)  # override=True强制用 .env 文件中的值覆盖掉系统环境变量的值。
# load_dotenv 从当前目录开始，递归向上查找.env文件。最先找到的那个.env文件会被加载。

ROOT_DIR = Path(__file__).parents[2]
DATA_DIR = ROOT_DIR / "atguigu" / "data"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_DIR = DATA_DIR / "output"
TEST_DIR = ROOT_DIR / "test"


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


class MinIOConfig:
    minio_endpoint = os.getenv("MINIO_ENDPOINT")
    minio_access = os.getenv("MINIO_ACCESS")
    minio_secret = os.getenv("MINIO_SECRET")
    minio_bucket_name = os.getenv("MINIO_BUCKET_NAME")
    minio_img_dir = os.getenv("MINIO_IMG_DIR")


class EmbeddingConfig:
    bge_m3_path = os.getenv("BGE_M3_PATH")
    bge_m3 = os.getenv("BGE_M3")
    bge_device = os.getenv("BGE_DEVICE")
    # 特殊处理：将.env中的1/0转为布尔值，兼容常见的数字/字符串格式
    bge_fp16 = os.getenv("BGE_FP16") in ("1", "True", "true", 1)


class MilvusConfig:
    milvus_url = os.getenv("MILVUS_URL")
    chunks_collection = os.getenv("CHUNKS_COLLECTION")
    item_name_collection = os.getenv("ITEM_NAME_COLLECTION")
