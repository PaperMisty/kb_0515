# atguigu/import_process/nodes/node_md_img.py
from atguigu.config.config import MinIOConfig
from atguigu.tool.minio_client_tool import get_minio_client
from atguigu.tool.minio_client_tool import minio_client
from collections import deque
from atguigu.tool.logger import logger
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.config.config import OUTPUT_DIR
from pathlib import Path
import os, re, time
from rich import print
from langchain.chat_models import init_chat_model
from atguigu.config.config import LLMConfig
from minio.deleteobjects import DeleteObject


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
        if not md_path_img_list:
            return state

        # 2.获取图片上下文
        img_context_list = self.get_img_context(md_path_img_list, content, md_path_img)
        if not img_context_list:
            return state

        # 3.获取图片摘要
        img_context_list = self.get_img_abstract(img_context_list)

        # 4.将图片传进minio
        md_content = self.upload_img_minio(
            img_context_list, content, state.get("md_path")
        )
        return {"md_content": md_content}

    def upload_img_minio(self, img_context_list, content, md_path):
        # 4.将图片传进minio
        minio_client = get_minio_client()
        # 幂等性删除图片
        img_obj_list = list(
            minio_client.list_objects(
                bucket_name=MinIOConfig.minio_bucket_name,
                prefix=MinIOConfig.minio_img_dir,
                recursive=True,
            )
        )  # 注意,生成器for一次后,就不能再for了,这也会导致没东西可删
        print("len(img_obj_list)= ", len(img_obj_list))
        for item in img_obj_list:
            print("img_obj: ", item)
        errors = minio_client.remove_objects(
            bucket_name=MinIOConfig.minio_bucket_name,
            delete_object_list=[
                DeleteObject(img_obj.object_name) for img_obj in img_obj_list
            ],
        )
        [logger.error(f"删除图片出错: {error}") for error in errors]

        for img_context in img_context_list:
            # 放图片进去
            img_name = img_context.get("img_name")
            minio_client.fput_object(
                bucket_name=MinIOConfig.minio_bucket_name,
                object_name=MinIOConfig.minio_img_dir + "/" + img_name,
                file_path=img_context.get("img_path"),
            )
            # 获取图片url
            img_context["url"] = (
                f"http://{MinIOConfig.minio_endpoint}/{MinIOConfig.minio_bucket_name}/{MinIOConfig.minio_img_dir}/{img_name}"
            )
            # print(img_context["url"])
            # 5.替换md_content图片链接的内容
            md_content = self.replace_md_content(img_context, content, md_path)
        return md_content

    def replace_md_content(self, img_context, content, md_path):
        # 5.替换md_content图片链接的内容
        pattern = re.compile(
            r"!\[.*?\]\(.*?" + re.escape(img_context.get("img_name")) + r"\)"
        )
        md_content = pattern.sub(
            f"![{img_context.get('img_summary')}])({img_context.get('url')})",
            content,
        )
        # 内容写进新文件
        new_md_path = md_path.parents[0] / (md_path.stem + "_new.md")
        print(new_md_path, type(new_md_path))
        with open(new_md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        return md_content

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
            logger.info(f"md的images文件夹下面无内容")
            return [], content, md_path_img
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
                    "post_context": post_context,  # 统一修改为 post_context，修复原先键值获取为 None 的 Bug
                    "img_path": str(md_path_img / img_name),
                }
            )
            # print(json_format(img_context_list))
        logger.info(f"{md_path_img}内部的图片上下文获取完毕")
        return img_context_list

    def get_img_abstract(self, img_context_list):
        # 3.获取图片摘要
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
        for img_context in img_context_list:
            start_time = time.time()
            # 盲清一波队列
            while bucket and time.time() - bucket[0] > 60:
                bucket.popleft()
            # 如果满员, 睡一定时间,睡完再出队第一个, 并入队新的请求时间戳(通过睡眠来控制后文的请求频率)
            if bucket and len(bucket) == bucket.maxlen:
                time.sleep(60 - (time.time() - bucket[0]))
                while bucket and time.time() - bucket[0] > 60:
                    bucket.popleft()
            # 最开始, bucket为空队列, 可以快速打满30个请求, 并且append进去;(归根结底还是串行,而且不方便开协程优化)
            bucket.append(time.time())

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
            ).content  # 假设网络+模型处理一张图1s, 那么队列中的间隔都为1s, 实际RPM=1 request / s ,可以abatch代替invoke实现,或者Celery用同一个队列
            print("用时: ", time.time() - start_time, "s:", res)
            img_context["img_summary"] = res
        logger.info("图片摘要获取完毕")
        return img_context_list


if __name__ == "__main__":
    start = time.time()
    node_md_img = NodeMDImg()
    init_state = {
        "md_path": OUTPUT_DIR / "hak180产品安全手册" / "hak180产品安全手册.md",
    }
    res = node_md_img(init_state)
    logger.info(res)
    print(f"{time.time()-start=}s")
