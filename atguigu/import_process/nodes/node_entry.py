# atguigu/import_process/nodes/node_entry.py
from pathlib import Path
from atguigu.tool.logger import logger
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState


class NodeEntry(NodeBase):
    """
    入口节点：任务分发
    """

    name = "node_entry"

    def process(self, state: ImportGraphState):
        local_file_path = state.get("local_file_path", None)
        # 判断是否有输入文件
        if not local_file_path:
            logger.error("local_file_path必须有内容")
            raise KeyError("local_file_path必须有内容")
        local_file_obj = Path(local_file_path)
        # 判断是否文件存在
        if not local_file_obj.exists():
            logger.error("local_file_path必须存在")
            raise KeyError("local_file_path必须存在")
        # 取文件名信息
        file_name = local_file_obj.stem
        file_type = local_file_obj.suffix
        # 根据文件类型,更新state
        if file_type == ".md":
            return {
                "file_title": file_name,
                "md_path": local_file_path,
                "is_md_read_enabled": True,
                "is_pdf_read_enabled": False,
            }
        elif file_type == ".pdf":
            return {
                "file_title": file_name,
                "pdf_path": local_file_path,
                "is_md_read_enabled": False,
                "is_pdf_read_enabled": True,
            }
        else:
            logger.error("不支持的文件类型")
            raise ValueError("不支持的文件类型")
        return state


if __name__ == "__main__":
    node = NodeEntry()
    # init_state = {
    #     "local_file_path": r"D:\desktop\Markdown笔记\机器学习\kb_0515\atguigu\data\output\01【掌柜智库】项目简介.md"
    # }
    init_state = {
        "local_file_path": r"D:\desktop\Markdown笔记\机器学习\kb_0515\atguigu\data\output\hak180产品安全手册.pdf"
    }
    res = node(init_state)
    logger.info(res)
