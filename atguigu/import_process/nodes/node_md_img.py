# atguigu/import_process/nodes/node_md_img.py
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.config.config import RAW_DIR, OUTPUT_DIR
from pathlib import Path
import os, re


class NodeMDImg(NodeBase):
    """
    MarkDown图片处理节点：多模态图片理解
    """

    name = "node_md_img"

    def process(self, state: ImportGraphState):
        md_path = state.get("md_path")
        # 判定文件是否可得
        if not md_path or (not md_path.exists()):
            logger.error(f"md路径无法读取:{md_path=}")
            raise FileNotFoundError("md路径无法读取")
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 判定文件内容存在性
        if not content:
            logger.error("文件没有内容")
            raise ValueError("文件没有内容")
        md_path_img = md_path.parent / "images"
        # 判定图片存在性
        if not md_path_img or (not md_path_img.exists()):
            logger.warning(f"md_img路径无法读取:{md_path_img=}")
        md_path_img_list = os.listdir(md_path_img)
        if not md_path_img_list:
            logger.info(f"md_path_img_list无内容")

        # 2.遍历图片,获取上下文
        IMG_SUFFIX_SET = {".jpg", ".png", ".jpeg", ".gif", ".webp", ".bmp"}
        MAX_CONTEXT = 250
        img_context_list = []
        for img_name in md_path_img_list:
            if Path(img_name).suffix.lower() not in IMG_SUFFIX_SET:
                logger.warning(f"图片格式不支持:{img_name=}")
                continue
            # 取图片的上下文
            pattern = re.compile(
                r"!\[.*?\]\(.*?" + re.escape(img_name) + r"\)"
            )  # re.escape作用是把img_name的.字符转义,避免被re当做元字符
            context_match = pattern.search(content)
            if not context_match:
                logger.warning("image文件夹内的图片未被md引用")
                continue
            start, end = context_match.span()
            pre_context = content[max(start - MAX_CONTEXT, 0) : start]
            post_context = content[
                end : end + MAX_CONTEXT
            ]  # 切片可以越下界,但不推荐越上界,越上界会出现负数,导致从末尾开始索引;
            img_context_list.append(
                {
                    "img_name": img_name,
                    "pre_context": pre_context,
                    "post_content": post_context,
                    "img_path": str(md_path_img / img_name),
                }
            )
            print(json_format(img_context_list))
        return state


if __name__ == "__main__":
    node_md_img = NodeMDImg()
    init_state = {
        "md_path": OUTPUT_DIR / "hak180产品安全手册" / "hak180产品安全手册.md",
    }
    res = node_md_img(init_state)
    logger.info(res)
