from atguigu.tool.json_format_tool import json_format
from atguigu.config.config import EmbeddingConfig
from pymilvus.model.hybrid import BGEM3EmbeddingFunction

bge_m3_model = None


def get_bgem3_model():
    """创建bge_m3模型"""
    global bge_m3_model
    if not bge_m3_model:
        bge_m3_model = BGEM3EmbeddingFunction(
            model_name=EmbeddingConfig.bge_m3_path,
            device=EmbeddingConfig.bge_device,
            use_fp16=EmbeddingConfig.bge_fp16,
        )
    return bge_m3_model


def get_bgem3_embedding(texts: list[str]):
    """把文本列表转为稀疏和稠密向量

    Args:
        texts (list[str]): 文本列表

    Returns:
        _type_: 稀疏和稠密向量
    """
    model = get_bgem3_model()
    embeddings = model.encode_documents(texts)
    return {
        "dense": [list(vec.tolist()) for vec in embeddings.get("dense")],
        "sparse": [
            dict(zip(vec.indices.tolist(), vec.data.tolist()))
            for vec in embeddings.get("sparse")
        ],
    }


if __name__ == "__main__":
    texts = ["hello,world", "hello milvus"]
    res = get_bgem3_embedding(texts=texts)
    print(json_format(res))
