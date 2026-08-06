# atguigu/import_process/nodes/node_document_split.py
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from langchain_text_splitters import RecursiveCharacterTextSplitter
from atguigu.import_process import state
from pathlib import Path
from atguigu.tool.validate_path import validate_path
from atguigu.config.config import OUTPUT_DIR
from atguigu.tool.logger import logger
from atguigu.tool.json_format_tool import json_format
import re


class NodeDocumentSplit(NodeBase):
    """
    文档切分节点：父子文档切分方式,先按段落(父),再按换行符和标点符号(子)
    """

    name = "node_document_split"

    def process(self, state: ImportGraphState):
        # 1.获取Markdown文本内容,以换行符切分为列表
        md_content_list, file_title, md_path_obj = self.get_md_content(state)
        # 2.获取Markdown每个章节内容,将每个章节切分为chunks
        chunk_dict_list = self.split_section(md_content_list, file_title)
        # 3.保存
        self.save_chunks_json(md_path_obj, chunk_dict_list)
        # 4.返回chunks详细信息
        return {"chunk_dict_list": chunk_dict_list}

    def get_md_content(self, state: ImportGraphState) -> tuple[list[str], str, Path]:
        """读取Markdown文件, 做换行标准化，按换行切割返回文本行列表。

        Args:
            state (ImportGraphState): LangGraph导入流程状态对象
                - md_path: markdown文件路径
                - file_title: 可选，文件标题；不存在则使用文件名stem

        Raises:
            Exception: 当md文件读取后内容为空字符串时抛出；路径校验失败由validate_path内部抛出。

        Returns:
            list[str]: markdown按换行分割后的每行文本组成的列表，不含原始\r\n换行符。
            file_title: 有效的文件名
        """
        md_path_obj = Path(state.get("md_path"))
        md_path_obj = validate_path(md_path_obj, "error")
        with open(md_path_obj, "r", encoding="utf-8") as f:
            md_content = f.read()
        if not md_content:
            logger.debug(f"{md_path_obj}无内容")
            return {}

        file_title = state.get("file_title")
        if not file_title:
            file_title = md_path_obj.stem

        # 统一换行符
        md_content = md_content.replace("\r\n", "\n").replace("\n\n", "\n")
        md_content_list = md_content.split("\n")
        return md_content_list, file_title, md_path_obj

    def split_section(self, md_content_list: list[str], file_title: str) -> list[dict]:
        """按 # 字符来切分段落

        Args:
            md_content_list (list[str]): Markdown文本列表
            file_title (str): 文件名称

        Returns:
            list[dict]: 切分后的段落信息
        """
        is_block = False
        code_fence = None
        code_pattern = r"^(`{3,}|~{3,})"

        current_idx = 0
        chunk_dict_list = []
        for idx, line in enumerate(md_content_list):
            line = line.strip()
            code_matched = re.match(code_pattern, line)
            # 判断是否处于代码围栏内
            if code_matched:
                if not is_block:
                    is_block = True
                    code_fence = code_matched.group(1)
                elif code_fence == code_matched.group(1):
                    is_block = False
                    code_fence = None

            title_pattern = r"^(#{1,6})\s+.*"
            # 如果不在代码围栏, 且触发了标题判定或触发最后一行判定, 则开始按标题切分
            if not is_block and (
                title_matched := re.match(title_pattern, line)
                or idx == len(md_content_list) - 1
            ):
                section_list = md_content_list[current_idx:idx]
                section_content = "\n".join(section_list)
                if section_list:
                    # 包装段落信息
                    section_title = (
                        section_list[0] if section_content.startswith("#") else "摘要"
                    )
                    _chunk_dict_list = self.split_chunks(
                        file_title, section_title, section_content
                    )
                    chunk_dict_list.extend(_chunk_dict_list)
                current_idx = idx
        return chunk_dict_list

    def split_chunks(
        self, file_title: str, section_title: str, section_content: str
    ) -> list[dict]:
        """递归切割器切分段落,给每个Chunk分配段落标题,
        对于含有HTML的和小于MAX_LENGTH的暂不切分

        Args:
            section_dict_list (list[dict]): 段落信息
            file_title (str): 文件名

        Returns:
            ImportGraphState: Graph对象
        """
        MAX_LENGTH = 300
        CHUNK_OVERLAP = 30
        chunk_dict_list = []
        spliter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " "],
            chunk_size=MAX_LENGTH,
            chunk_overlap=CHUNK_OVERLAP,
        )
        if len(section_content) < 300 or "<table" in section_content:
            chunk_dict_list.append(
                {
                    "file_title": file_title,
                    "section_title": section_title,
                    "chunk_content": section_content,
                    "part": 0,
                }
            )
        else:
            real_section_content = section_content[len(section_title) :]  # 去除段落标题
            chunk_list = spliter.split_text(real_section_content)
            for idx, chunk in enumerate(chunk_list, 1):
                chunk_dict_list.append(
                    {
                        "file_title": file_title,
                        "section_title": section_title,
                        "chunk_content": section_title + "\n\n" + chunk,
                        "part": idx,
                    }
                )
        return chunk_dict_list

    def save_chunks_json(self, md_path_obj: Path, chunk_dict_list: list[dict]):
        """保存Markdown文档已切分的chunks信息

        Args:
            md_path_obj (Path):
            chunk_dict_list (list[dict]):
        """
        chunks_json_path = (
            str(md_path_obj.parent) + "/" + md_path_obj.stem + "_chunks.json"
        )
        with open(
            chunks_json_path,
            "w",
            encoding="utf-8",
        ) as f:
            f.write(json_format(chunk_dict_list))
        logger.info(f"{chunks_json_path}文件成功写入")


if __name__ == "__main__":
    node = NodeDocumentSplit()
    init_state = {
        "md_path": str(OUTPUT_DIR / "hak180产品安全手册" / "hak180产品安全手册_new.md"),
        "file_title": "hak180产品安全手册",
    }

    res = node(init_state)
    logger.info(json_format(res))
