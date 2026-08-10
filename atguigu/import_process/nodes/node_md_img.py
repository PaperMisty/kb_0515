# atguigu/import_process/nodes/node_md_img.py
from atguigu.tool.json_format_tool import json_format
import asyncio
from atguigu.config.config import MinIOConfig, LLMConfig, OUTPUT_DIR
from atguigu.tool.minio_client_tool import get_minio_client, minio_client
from collections import deque
from atguigu.tool.logger import logger
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.validate_path import validate_path
from atguigu.tool.limiter import async_rate_limiter
from pathlib import Path
import os, re, time, base64
from rich import print
from langchain.chat_models import init_chat_model
from minio.deleteobjects import DeleteObject


class NodeMDImg(NodeBase):
    """MarkDown图片处理节点：多模态图片理解

    Args:
        NodeBase (_type_): _description_

    Raises:
        ValueError: _description_
    """

    name = "node_md_img"
    RPM = 3000
    PERIOD = 60
    llm_batch = 30

    def process(self, state: ImportGraphState) -> ImportGraphState:
        # 1.获取图片
        md_img_path_list, md_content, md_img_path = self.get_img(state)
        if not md_img_path_list:
            return state

        # 2.获取图片上下文
        img_context_list = self.get_img_context(md_img_path_list, md_content, md_img_path)
        if not img_context_list:
            return state

        # 3.获取图片摘要
        img_context_list = self.get_img_abstract(img_context_list)

        # 4.将图片传进minio
        img_context_list = self.upload_img_minio(img_context_list, Path(state.get("md_path", "")))
        # 5. Markdown文档内部图片url替换为线上url
        md_path_obj = Path(state.get("md_path", ""))
        md_content = self.replace_md_content(img_context_list, md_content, md_path_obj)
        new_md_path = md_path_obj.parents[0] / (md_path_obj.stem + "_new.md")
        return {"md_content": md_content, "md_path": str(new_md_path)}

    def get_img(self, state: ImportGraphState) -> tuple[list[dict], str, Path]:
        """获取Markdown文档的图片内容

        Args:
            state (ImportGraphState): 主图状态

        Raises:
            ValueError: 文件不存在

        Returns:
            tuple[list[dict], str, Path]: 图片路径,文档内容, 文档路径
        """
        # 判定文件路径存在性
        md_path_obj = Path(state.get("md_path", ""))
        md_path_obj = validate_path(md_path_obj, level="error")
        with open(md_path_obj, "r", encoding="utf-8") as f:
            md_content = f.read()
        # 判定文件内容存在性
        if not md_content:
            logger.error("文件没有内容")
            raise ValueError("文件没有内容")
        # 判定图片文件夹存在性
        md_img_path = validate_path(md_path_obj.parent / "images", level="warning")

        md_img_path_list = os.listdir(md_img_path)
        if not md_img_path_list:
            logger.info(f"md的images文件夹下面无内容")
            return [], md_content, md_img_path
        return md_img_path_list, md_content, md_img_path

    def get_img_context(self, md_img_path_list: list[dict], md_content: str, md_img_path: Path) -> list[dict]:
        """根据图片获取上下文

        Args:
            md_img_path_list (list[dict]): 图片路径,文档内容, 文档路径
            md_content (str): 文档内容
            md_img_path (Path): 文档路径

        Returns:
            list[dict]: 图片相关信息
        """
        IMG_SUFFIX_SET = {".jpg", ".png", ".jpeg", ".gif", ".webp", ".bmp"}
        MAX_CONTEXT = 250
        img_context_list = []
        for img_name in md_img_path_list:
            if Path(img_name).suffix.lower() not in IMG_SUFFIX_SET:
                logger.warning(f"图片格式不支持:{img_name=}")
                continue

            # 取图片的上下文
            pattern = re.compile(
                r"!\[.*?\]\(.*?" + re.escape(img_name) + r"\)"
            )  # re.escape作用是把img_name的.字符转义,避免被re当做元字符
            context_match = list(
                re.finditer(pattern, md_content)
            )  # 如果用re.search 只能找到第一次出现的位置,如果后面二次引用,上下文就不对了

            if not context_match:
                logger.warning("image文件夹内的图片未被md引用")
                continue

            # 遍历所有的匹配项
            for _match in context_match:
                # 取上下文
                start, end = _match.span()
                pre_context = md_content[max(start - MAX_CONTEXT, 0) : start]
                post_context = md_content[
                    end : end + MAX_CONTEXT
                ]  # 切片可以越下界,但不推荐越上界,越上界会出现负数,导致从末尾开始索引;

                img_context_list.append(
                    {
                        "img_name": img_name,
                        "pre_context": pre_context,
                        "post_context": post_context,  # 统一修改为 post_context，修复原先键值获取为 None 的 Bug
                        "img_path": str(md_img_path / img_name),
                        "span": (start, end),
                    }
                )
        logger.info(f"{md_img_path}内部的图片上下文获取完毕")
        return img_context_list

    #  设计令牌桶/限流器,防止服务端限流报错-----尚未考虑TPM限制
    @async_rate_limiter(max_calls=(RPM // llm_batch), period=PERIOD)
    async def chat_batch(self, llm, messages) -> list[str]:
        """异步批量处理图片摘要请求, 提高RPM

        Args:
            llm (_type_): 模型对象
            messages (_type_): 提词列表

        Returns:
            list[str]: 响应列表
        """
        start_time = time.time()
        res_list = await llm.abatch(
            inputs=messages
        )  # 假设网络+模型处理一张图1s, 那么队列中的间隔都为1s, 实际RPM=1 request / s ,可以abatch代替invoke实现,或者Celery用同一个队列
        print("abatch用时: ", time.time() - start_time, "s:")
        return res_list

    def get_img_abstract(self, img_context_list: list[dict]) -> list[dict]:
        """获取图片摘要

        Args:
            img_context_list (list[dict]): 图片相关信息

        Returns:
            list[dict]: 图片相关信息(含图片摘要)
        """

        # 初始化VLM模型
        llm = init_chat_model(
            model=LLMConfig.vlm_model,
            model_provider="openai",
            base_url=LLMConfig.base_url,
            api_key=LLMConfig.api_key,
            temperature=LLMConfig.temperature,
        )

        messages_list = []
        batch_contexts = []  # 增加一个临时列表，存放当前批次的 img_context 字典引用

        for idx, img_context in enumerate(img_context_list):

            with open(img_context.get("img_path"), "rb") as f:
                b_content = f.read()
                base64_code = base64.b64encode(b_content).decode(
                    "utf-8"
                )  # b64encode是把[二进制:bytes] 转 [ASCII码对应的字节:bytes]
                # decode 是把[ASCII码对应的字节:bytes] 转 [字符串:str] ,因为字符串才能在json里面进行网络传输

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
            messages_list.append(messages)
            batch_contexts.append(img_context)  # 将当前字典对象存入临时列表

            # 判断是否达到 llm_batch 个，或者是最后一个元素
            if len(messages_list) == self.llm_batch or idx == len(img_context_list) - 1:
                res_list = asyncio.run(self.chat_batch(llm, messages_list))

                for inner_idx, res in enumerate(res_list):
                    # 直接通过临时列表对字典赋值，修改会同步反映到原始 img_context_list 中, 这是存在一个引用传递特性的
                    batch_contexts[inner_idx]["img_summary"] = res.content

                # 关键：处理完当前批次后，必须清空临时列表和消息列表
                messages_list = []
                batch_contexts = []
        logger.info("图片摘要获取完毕")

        return img_context_list

    def upload_img_minio(self, img_context_list: list[dict], md_path_obj: Path) -> list[dict]:
        """将图片传进minio , 拼接图片的线上url

        Args:
            img_context_list (list[dict]): 图片相关信息的列表
            md_content (str): Markdown文档内容
            md_path_obj (Path): Markdown文件路径Path对象

        Returns:
            str: 替换后的Markdown文档内容
        """
        minio_client = get_minio_client()
        # 幂等性删除图片
        img_obj_list = list(
            minio_client.list_objects(
                bucket_name=MinIOConfig.minio_bucket_name,
                prefix=MinIOConfig.minio_img_dir
                + "/"
                + md_path_obj.stem,  # 给单个文档独立的图片空间,避免误删其他文档的
                recursive=True,  # 递归删除文件夹内部内容, 否则不会删
            )
        )  # 注意,生成器for一次后,就不能再for了,这也会导致没东西可删
        # for item in img_obj_list:
        #     print("img_obj: ", item)
        errors = minio_client.remove_objects(
            bucket_name=MinIOConfig.minio_bucket_name,
            delete_object_list=[DeleteObject(img_obj.object_name) for img_obj in img_obj_list],
        )
        [logger.error(f"删除图片出错: {error}") for error in errors]

        for img_context in img_context_list:
            # 放图片进去
            img_name = img_context.get("img_name")
            minio_client.fput_object(
                bucket_name=MinIOConfig.minio_bucket_name,
                object_name=MinIOConfig.minio_img_dir + "/" + md_path_obj.stem + "/" + img_name,
                file_path=img_context.get("img_path"),
            )
            # 获取图片url
            img_context["url"] = (
                f"http://{MinIOConfig.minio_endpoint}/{MinIOConfig.minio_bucket_name}/{MinIOConfig.minio_img_dir}/{md_path_obj.stem}/{img_name}"
            )

        return img_context_list

    def replace_md_content(self, img_context_list: list[dict], md_content: str, md_path_obj: Path) -> str:
        """替换Markdown文件图片链接的内容

        Args:
            img_context_list (dict): 图片上下文列表
            md_content (str): Markdown文档内容
            md_path_obj (Path): Markdown文档路径Path对象

        Returns:
            str: 替换后的Markdown文档内容
        """
        # 从后往前替换, 避免替换后影响后续索引,导致(start,end)索引失效
        img_context_list = sorted(img_context_list, key=lambda x: x["span"][0], reverse=True)

        for img_context in img_context_list:
            start, end = img_context["span"]
            replacement = f"![{img_context.get('img_summary')}]({img_context.get('url')})"
            md_content = md_content[:start] + replacement + md_content[end:]

        # 内容写进新文件
        new_md_path = md_path_obj.parents[0] / (md_path_obj.stem + "_new.md")
        with open(new_md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info(f"{new_md_path}文档内容写入成功")
        return md_content


if __name__ == "__main__":
    start = time.time()
    node_md_img = NodeMDImg()
    init_state = {
        "md_path": str(OUTPUT_DIR / "hak180产品安全手册" / "hak180产品安全手册.md"),
    }
    # init_state = {
    #     "md_path": str(OUTPUT_DIR / "demo" / "demo.md"),
    # }
    res = node_md_img(init_state)
    print(f"整个流程: {time.time()-start=}s")
    logger.info(json_format(res))
