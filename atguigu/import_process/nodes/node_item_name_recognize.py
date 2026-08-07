# atguigu/import_process/nodes/node_item_name_recognition.py
from atguigu.tool.validate_path import validate_path
from atguigu.tool.logger import logger
from atguigu.tool.json_format_tool import json_format
from atguigu.config.config import OUTPUT_DIR
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
import json
from pathlib import Path


class NodeItemNameRecognition(NodeBase):
    """
    主体识别节点：主体识别与标签提取
    """

    name = "node_item_name_recognition"

    def process(self, state: ImportGraphState):
        chunk_data = state.get("chunk_data")
        if not chunk_data:
            logger.error(f"chunk_data无内容,必须传入值,进行主体识别")
            raise ValueError(f"chunk_data无内容,必须传入值,进行主体识别")

        # 切片固定长度chunks,输给LLM总结
        MAX_LENGTH = 10000
        content_example = json.dumps(chunk_data[:10], ensure_ascii=False)[:MAX_LENGTH]
        return {"content_example": content_example}


if __name__ == "__main__":
    node = NodeItemNameRecognition()
    file_path = str(
        OUTPUT_DIR / "hak180产品安全手册" / "hak180产品安全手册_new_chunks.json"
    )
    with open(
        file_path,
        "r",
        encoding="utf-8",
    ) as f:
        chunk_data = json.load(f)
    init_state = {"chunk_data": chunk_data}

    res = node(init_state)
    logger.info(json_format(res))
