# utils/embedding_utils.py

from pymilvus.model.hybrid import BGEM3EmbeddingFunction
from atguigu.config.config import BGEM3Config

bge_embedding_model = None


def get_bge_embedding_model():
    global bge_embedding_model
    if not bge_embedding_model:
        print(BGEM3Config.bge_m3_path)
        bge_embedding_model = BGEM3EmbeddingFunction(
            model_name=BGEM3Config.bge_m3_path,
            device=BGEM3Config.bge_device,
            use_fp16=True if BGEM3Config.BGE_FP16 in ("True", "1", 1, True) else False,
        )
    return bge_embedding_model


def get_embeddings(text_list):
    model = get_bge_embedding_model()
    embeddings = model.encode_documents(text_list)
    return {
        "dense": [list(d) for d in embeddings["dense"]],
        "sparse": [dict(zip(row.indices, row.data)) for row in embeddings["sparse"]],
    }


if __name__ == "__main__":
    get_bge_embedding_model()
