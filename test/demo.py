from atguigu.config.config import LLMConfig
from langchain.chat_models import init_chat_model

llm = init_chat_model(
    model=LLMConfig.vlm_model,
    model_provider="openai",
    base_url=LLMConfig.base_url,
    api_key=LLMConfig.api_key,
    temperature=LLMConfig.temperature,
)

img_path = "./image.png"
