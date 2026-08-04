# atguigu/import_process/nodes/node_pdf_to_md.py
import requests
import time
from atguigu.config.config import MineruConfig, RAW_DIR, OUTPUT_DIR
from atguigu.import_process import state
from pathlib import Path
from atguigu.tool.logger import logger
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.validate_path import validate_path


class NodePDFToMD(NodeBase):
    """
    PDF 转 Markdown 节点：PDF结构化解析
    """

    name = "node_pdf_to_md"

    def __init__(self):
        self.token = MineruConfig.mineru_token
        self.base_url = MineruConfig.mineru_base_url
        self.header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    def process(self, state: ImportGraphState):
        # 校验输入路径
        pdf_path = state.get("pdf_path", None)
        pdf_path_obj = validate_path(pdf_path, "error")
        # 校验输出路径
        local_path = state.get("local_dir", None)
        local_path_obj = validate_path(local_path, "debug")
        if not local_path_obj.exists():
            # parents=True表示如果父目录不存在,也一并创建
            # exist_ok=True表示如果目录已存在,不抛出异常
            local_path_obj.mkdir(parents=True, exist_ok=True)
        urls, batch_id = self.verify_token(pdf_path_obj)
        self.upload_files(urls, pdf_path, batch_id)
        zip_content = self.ask_for_results(batch_id)
        self.write_zip_and_rename(local_path_obj, pdf_path_obj, zip_content)

    def verify_token(self, pdf_path_obj: Path) -> tuple[list[str], str]:

        # 第一阶段:服务器验证您的 Token 之后，并没有在这个阶段接收您的文件内容，
        # 而是返回了一个专门供您上传该文件的临时链接（预签名 URL / Presigned URL）
        url = f"{self.base_url}/file-urls/batch"

        data = {
            "files": [{"name": pdf_path_obj.name, "data_id": "abcd"}],
            "model_version": "vlm",
        }
        response = requests.post(url, headers=self.header, json=data)
        # 第一阶段的三层判断
        if response.status_code != 200:
            logger.error(f"申请上传文件请求失败")
            raise ValueError("申请上传文件请求失败")
        logger.info(f"申请上传文件成功")
        result = response.json()

        if result["code"] != 0:
            logger.error("申请上传文件数据失败")
            raise ValueError("申请上传文件数据失败")

        batch_id = result["data"]["batch_id"]
        urls = result["data"]["file_urls"]
        logger.info("申请上传文件数据成功")
        return urls, batch_id

    def upload_files(self, urls: list[str], file_path: str, batch_id: str) -> None:
        # 第二阶段:拿着上一步拿到的临时链接，开始执行实际的文件上传操作
        for i in range(0, len(urls)):
            with open(file_path[i], "rb") as f:
                res_upload = requests.put(
                    urls[i], data=f
                )  # 对象存储服务的标准中，使用 PUT 方法上传文件是非常标准且合理的做法, 寓意本地资源放置在云端去。PUT是幂等的/POST不是幂等的
                if res_upload.status_code == 200:
                    logger.info(f"{urls[i]} upload success")
                else:
                    logger.info(f"{urls[i]} upload failed")
        # print(f"{batch_id=}")

    def ask_for_results(self, batch_id: str) -> bytes:
        # 第三阶段:轮询结果
        url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
        zip_url = None
        while True:
            res = requests.get(url, headers=self.header)  # 返回Response对象
            if res.status_code != 200:
                logger.error(f"获取解析结果失败,状态码：{res.status_code}")
                raise ValueError("获取解析结果失败")

            result = res.json()  # 解析为字典
            if result["code"] != 0:
                logger.error("获取解析结果数据失败")
                raise ValueError("获取解析结果数据失败")

            data = result["data"]["extract_result"][0]
            if data["state"] != "done":
                logger.debug(f"解析状态不是完成状态，当前状态为: {data['state']}")
                time.sleep(2)  # 稍微延长一点时间，避免请求过频
            else:
                zip_url = data["full_zip_url"]
                break

        # 下载zip文件
        logger.info(f"解析完成，开始下载 Zip 文件: {zip_url}")
        res_zip = requests.get(zip_url)
        if res_zip.status_code != 200:
            logger.error("下载zip文件失败")
            raise ValueError("下载zip文件失败")
        zip_content = res_zip.content
        return zip_content

    def write_zip_and_rename(
        self, local_path_obj: Path, pdf_path_obj: Path, zip_content: bytes
    ) -> ImportGraphState:
        # zip写进磁盘
        zip_file_path = local_path_obj / f"{pdf_path_obj.stem}.zip"
        with open(zip_file_path, "wb") as f:
            f.write(zip_content)

        # 解压zip
        import zipfile, shutil

        unzip_content_path_obj = (
            local_path_obj / pdf_path_obj.stem
        )  # zip文件解压的目标路径
        # 保持解压幂等性
        if unzip_content_path_obj.exists():
            shutil.rmtree(unzip_content_path_obj)
        with zipfile.ZipFile(zip_file_path, "r") as unzip_content:
            unzip_content.extractall(unzip_content_path_obj)

        # 重命名full.md为pdf_path_obj.stem + ".md"
        target_md = (
            unzip_content_path_obj / f"{pdf_path_obj.stem}.md"
        )  # stem会去掉路径,也去掉后缀
        full_md = unzip_content_path_obj / "full.md"
        if full_md.exists():
            if target_md.exists():
                target_md.unlink()  # 目标文件若已存在则删除，避免 Windows 下 rename 抛错
            full_md.rename(target_md)

        # 读取md文本内容
        with open(target_md, "r", encoding="utf-8") as f:
            md_content = f.read()

        # 返回md文件路径与内容
        return {
            "md_content": md_content,
            "md_path": str(target_md),
        }


if __name__ == "__main__":
    node_pdf_to_md = NodePDFToMD()
    init_state = {
        "pdf_path": str(RAW_DIR / "hak180产品安全手册.pdf"),
        "local_dir": str(OUTPUT_DIR),
    }
    res = node_pdf_to_md(init_state)

    logger.info(res)
