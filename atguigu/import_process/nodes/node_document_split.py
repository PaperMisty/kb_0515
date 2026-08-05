# atguigu/import_process/nodes/node_document_split.py
from langchain_text_splitters import RecursiveCharacterTextSplitter
from atguigu.import_process import state
from pathlib import Path
from atguigu.tool.validate_path import validate_path
from atguigu.config.config import OUTPUT_DIR
from atguigu.tool.logger import logger
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format
import re


class NodeDocumentSplit(NodeBase):
    """
    文档切分节点：智能文档切片
    """

    name = "node_document_split"

    def process(self, state: ImportGraphState):
        # 1.获取Markdown文本内容,以换行符切分为列表
        md_content_list, file_title, md_path_obj = self.get_md_content(state)
        # 2.获取Markdown每个章节内容
        section_dict_list = self.split_section(md_content_list, file_title)
        # 3.将每个章节切分为chunks并保存
        chunk_dict_list = self.split_chunks(section_dict_list, file_title, md_path_obj)
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
        file_title = state.get("file_title")
        if not file_title:
            file_title = md_path_obj.stem
        # 统一化换行符
        with open(md_path_obj, "r", encoding="utf-8") as f:
            md_content = f.read()
        if not md_content:
            logger.error(f"{md_path_obj}文件无内容")
            raise Exception(f"{md_path_obj}文件无内容")
        md_content.replace("\r\n", "\n").replace("\n\n", "\n")
        # 用换行符切割
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
        # 逐行处理
        is_block = False
        signer = None
        code_pattern = r"^(`{3,}|~{3,})"
        # 匹配 Markdown 标题：1-6个 # 号 + 空格 + 标题内容
        title_pattern = r"^(#{1,6})\s+.*"

        current_index = 0
        section_dict_list = []
        for idx, line in enumerate(md_content_list):
            line = line.strip()
            matched = re.match(code_pattern, line)
            # 判定是否处于代码块
            if matched:
                if is_block == False:
                    is_block = True
                    signer = matched.group(1)
                elif signer == matched.group(1):
                    is_block = False
                    signer = None

            # 判断是否遇到代码块外的 # 标题, 是则提取上一段的段落
            if not is_block and (match_obj := re.match(title_pattern, line)):
                temp_list = md_content_list[current_index:idx]
                section_content = "\n".join(temp_list)  # 列表转文本
                section_dict_list.append(
                    {
                        "file_title": file_title,
                        "section_title": (
                            temp_list[0]
                            if section_content.startswith("#")
                            else "无标题"
                        ),
                        "section_content": section_content,
                    }
                )
                current_index = idx
        # 补充最后一段的段落内容
        last_section_list = md_content_list[current_index:]
        section_dict_list.append(
            {
                "file_title": file_title,
                "section_title": last_section_list[0],
                "section_content": "\n".join(last_section_list),
            }
        )
        return section_dict_list

    def split_chunks(
        self, section_dict_list: list[dict], file_title: str, md_path_obj: Path
    ) -> ImportGraphState:
        """递归切割器切分段落

        Args:
            section_dict_list (list[dict]): 段落信息
            file_title (str): 文件名

        Returns:
            ImportGraphState: Graph对象
        """
        # 切分chunk
        MAX_LENGTH = 300
        CHUNK_OVERLAP = 30
        chunk_dict_list = []
        spliter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " "],
            chunk_size=MAX_LENGTH,
            chunk_overlap=CHUNK_OVERLAP,
        )
        for section_dict in section_dict_list:
            # 将段落剔除出标题
            section_title = section_dict.get("section_title")
            section_content = section_dict.get("section_content")
            real_section_content = (
                section_content[len(section_title) :]
                if section_content.startswith("#")
                else section_content
            )
            # 对于特殊段落,不做切分
            # TODO:对于连续少文本的含标题段落,会错过短合; 对于长文本<table>需要二次拆分
            if (
                len(real_section_content) < MAX_LENGTH
                or "<table"
                in real_section_content  # 兼容 <table border="1"> 带属性的标签。
            ):
                chunk_dict_list.append(
                    {
                        "file_title": file_title,
                        "section_title": section_title,
                        "chunk_content": section_content,
                        "part": 0,
                    }
                )
                continue
            # 对于常规段落,用递归切割器切分
            chunk_list = spliter.split_text(real_section_content)
            for idx, chunk in enumerate(chunk_list, start=1):
                chunk_dict_list.append(
                    {
                        "file_title": file_title,
                        "section_title": section_title,
                        "chunk_content": section_title + "\n\n" + chunk,
                        "part": idx,
                    }
                )
        # 保存切分结果
        chunk_path = md_path_obj.parents[0] / file_title
        with open(str(chunk_path) + "_chunks.json", "w", encoding="utf-8") as f:
            f.write(json_format(chunk_dict_list))

        return chunk_dict_list


if __name__ == "__main__":
    node = NodeDocumentSplit()
    init_state = {
        "md_path": str(OUTPUT_DIR / "hak180产品安全手册" / "hak180产品安全手册_new.md"),
        "file_title": "hak180产品安全手册",
    }
    res = node(init_state)
    logger.info(json_format(res))
