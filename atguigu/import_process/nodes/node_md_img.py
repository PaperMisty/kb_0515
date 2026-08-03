# atguigu/import_process/nodes/node_md_img.py
from collections import deque
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.config.config import RAW_DIR, OUTPUT_DIR
from pathlib import Path
import os, re, time
from rich import print
from langchain.chat_models import init_chat_model
from atguigu.config.config import LLMConfig


class NodeMDImg(NodeBase):
    """
    MarkDown图片处理节点：多模态图片理解
    """

    name = "node_md_img"

    # 路径文件检查器
    @staticmethod
    def validate_path(path: str, level: str):
        # 判定路径是否可得
        if not path or (not path.exists()):
            if level == "error":
                logger.error(f"路径无法读取/无内容:{path=}")
                raise FileNotFoundError("路径无法读取")
            elif level == "warning":
                logger.warning(f"路径无法读取/无内容:{path=}")
            elif level == "info":
                logger.info(f"路径无法读取/无内容:{path=}")
            elif level == "debug":
                logger.debug(f"路径无法读取/无内容:{path=}")
        return path

    def process(self, state: ImportGraphState):
        # 1.获取图片
        md_path_img_list, content, md_path_img = self.get_img(state)
        # 2.获取图片上下文
        img_context_list, img_name, img_path = self.get_img_context(
            md_path_img_list, content, md_path_img
        )
        # 3.获取图片摘要
        img_summary_list = self.get_img_abstract(img_context_list, img_name, img_path)
        return state

    def get_img(self, state: ImportGraphState):
        # 判定文件路径存在性
        md_path = self.validate_path(state.get("md_path"), level="error")
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 判定文件内容存在性
        if not content:
            logger.error("文件没有内容")
            raise ValueError("文件没有内容")
        # 判定图片文件夹存在性
        md_path_img = self.validate_path(md_path.parent / "images", level="warning")

        md_path_img_list = os.listdir(md_path_img)
        if not md_path_img_list:
            logger.info(f"md_path文件夹下面无内容")
        return md_path_img_list, content, md_path_img

    def get_img_context(self, md_path_img_list, content, md_path_img):
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
                    "img_path": (img_path := str(md_path_img / img_name)),
                }
            )
            # print(json_format(img_context_list))
        logger.info(f"{md_path_img}内部的图片上下文获取完毕")
        return img_context_list, img_name, img_path

    def get_img_abstract(self, img_context_list, img_name, img_path):
        # 初始化VLM模型
        llm = init_chat_model(
            model=LLMConfig.vlm_model,
            model_provider="openai",
            base_url=LLMConfig.base_url,
            api_key=LLMConfig.api_key,
            temperature=LLMConfig.temperature,
        )

        # 设计令牌桶,防止限流-----bug: 可能不能打满请求RPM的80% ,而且尚未考虑TPM限制
        bucket = deque(maxlen=30)
        current_time = time.time()
        for img_context in img_context_list:
            start_time = time.time()
            # 盲清一波队列
            while bucket and current_time - bucket[0] > 60:
                bucket.popleft()
            # 如果满员, 睡一定时间,睡完再出队第一个, 并入队新的请求时间戳(通过睡眠来控制后文的请求频率)
            if bucket and len(bucket) == deque.maxlen:
                time.sleep(60 - (current_time - bucket[0]))
                current_time = time.time()
                while bucket and current_time - bucket[0] > 60:
                    bucket.popleft()
            # 最开始, bucket为空队列, 可以快速打满30个请求, 并且append进去;(归根结底还是串行,而且不方便开协程优化)
            bucket.append(current_time)

            # 图片转Base64
            import base64

            with open(img_context.get("img_path"), "rb") as f:
                b_content = f.read()
                base64_code = base64.b64encode(b_content).decode("utf-8")
            # 构造提示词
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_code}",
                            },
                        },
                        {
                            "type": "text",
                            "text": f"""这是一张图片，图片上文部分为"{img_context.get("pre_context")}"，
                                下文部分为"{img_context.get("post_context")}"，请用中文简要总结这张图片的摘要,字数在50字以内。""",
                        },
                    ],
                },
            ]
            res = llm.invoke(
                input=messages
            ).content  # 假设模型处理一张图1s, 那么队列中的间隔都为1s, 实际RPM=1 request / s
            print("用时: ", time.time() - start_time, "s:", res)
            img_context["img_summary"] = res
        logger.info(f"{img_path}内部的图片摘要获取完毕")


if __name__ == "__main__":
    node_md_img = NodeMDImg()
    init_state = {
        "md_path": OUTPUT_DIR / "hak180产品安全手册" / "hak180产品安全手册.md",
    }
    res = node_md_img(init_state)
    logger.info(res)
