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
STATIC_DIR = ROOT_DIR / "web" / "page"


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
    model_provider = "openai"


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


class MongoConfig:
    mongo_url = os.getenv("mongo_url")
    mongo_db_name = os.getenv("mongo_db_name")


class MCPConfig:
    mcp_dashscope_base_url = os.getenv("MCP_DASHSCOPE_BASE_URL")


class ReRankerConfig:
    reranker_base_url = os.getenv("RERANK_BASE_URL")


class PromptConfig:
    # 文件命名主体识别
    ITEM_NAME_USER_PROMPT_TEMPLATE = """
                请从以下信息中识别出商品名称与型号：
                文件名：{file_title}

                正文切片（用于辅助识别）：
                {context}

                要求：
                1. 返回内容为字符串形式，最好是带品牌、型号和名称的完整商品名称。比如：苏伯尓5000W大功率电磁炉；
                2. 返回结果应该只包含商品名称，不要添加任何解释或其他内容；
                3. 如果无法识别商品名称,请返回空字符串。
                """
    # Query意图识别
    ITEM_NAME_EXTRACT_SYSTEM_PROMPT = "你是一个专业的客服助手，擅长理解用户意图和提取关键信息。你在提取问题的主体名称时，能够区分主体的名称、品牌、型号或者类别。"

    ITEM_NAME_EXTRACT_TEMPLATE = """
    历史会话：
    {history_text}

    当前用户问题：
    {original_query}

    请根据历史会话和当前问题，提取用户正在询问的主体信息。

    重要概念区分：
    - 主体名称：指用户的咨询对象，可以是具体的产品名称（如"烫金机"、"手机"、"笔记本电脑"），也可以是产品的类别（如"打印机"、"吸尘器"、"电磁炉"）。
    - 型号：指商品的具体型号编号，如"hak180"、"iPhone 15"、"X1 Carbon"。
    - 品牌：指商品的品牌，如"华为"、"苹果"、"联想"。
    注意：型号编号和品牌都不是商品名称。

    提取规则：
    1. 优先从历史会话中查找用户最初提到的主体名称（如"烫金机"），型号（如"hak180"）不是主体名称。
    2. 如果历史会话中同时出现了主体名称和型号，item_names 中必须包含主体名称。可以在主体名称前附带品牌 and/or 型号作为补充信息，格式为"[品牌][型号]主体名称"，例如"hak180烫金机"或"华为Mate60手机"。
    3. 如果用户使用了代词（如"这个"、"它"），请结合历史会话指代消解，确定主体名称。
    4. 如果整个对话中确实没有任何主体名称信息，item_names 返回原始语句某个名词。
    5. 请重新改写用户的问题（rewritten_query），使其成为包含主体名称的独立完整问题。
    6. 可能有一个或多个主体，但不能重复。
    """

    HYDE_PROMPT = """
    请基于以下用户查询生成一个简洁的回答范文。
    用户查询: {rewritten_query}
    要求：
    1. 回答要简洁明了，包含核心信息即可
    2. 假设你是该领域的专家，提供专业的解释
    3. 不要使用"假设"、"可能"等不确定的词汇
    4. 保持回答与查询主题高度相关
    5. 使用中文回答且不超过300字
    """

    # 回答生成提示词
    ANSWER_PROMPT = """你是一个智能助手，请根据参考内容回答用户的问题。
    要求：
    1 尽量基于【参考内容】和【用户问题】作答，不要编造不存在的事实。
    2 如果参考内容中包含相关的图片链接（来自 MinIO 的 URL），且回答需要图片辅助说明（例如：外观、结构、接线等），请务必在回答中直接引用这些图片链接。
    3 引用图片时，请严格在相关的文字段落下方另起一行，以如下格式输出图片链接：
    【图片】
    <这里直接放入参考内容中的图片URL>
    
    （注意：图片 URL 必须完全来自于【参考内容】中真实的图片链接，绝对不要编造！如果没有合适图片，则不要输出任何图片链接，也不要输出【图片】字样）

    【参考内容】
    {context}

    【历史对话】
    {history}

    【相关商品/实体】
    {item_names}

    【用户问题】
    {question}

    请回答："""
