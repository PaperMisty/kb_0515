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
        pdf_path_obj = Path(state.get("pdf_path", ""))
        pdf_path_obj = validate_path(pdf_path_obj, "error")
        # 校验输出路径
        local_path_obj = Path(state.get("local_dir", ""))
        local_path_obj = validate_path(local_path_obj, "debug")
        if not local_path_obj.exists():
            # parents=True表示如果父目录不存在,也一并创建
            # exist_ok=True表示如果目录已存在,不抛出异常
            local_path_obj.mkdir(parents=True, exist_ok=True)
        urls, batch_id = self.verify_token(pdf_path_obj)
        self.upload_files(urls, pdf_path_obj)
        zip_content = self.ask_for_results(batch_id)
        return self.write_zip_and_rename(local_path_obj, pdf_path_obj, zip_content)

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

    def upload_files(self, urls: list[str], file_path: Path) -> None:
        # 第二阶段:拿着上一步拿到的临时链接，开始执行实际的文件上传操作
        for i in range(0, len(urls)):
            with open(file_path, "rb") as f:  # 原始写法是file_path是个路径的列表,实现多个文件的上传;
                res_upload = requests.put(
                    urls[i], data=f
                )  # 对象存储服务的标准中，使用 PUT 方法上传文件是非常标准且合理的做法, 寓意本地资源放置在云端去。PUT是幂等的/POST不是幂等的
                if res_upload.status_code == 200:
                    logger.info(f"{urls[i]} upload success")
                else:
                    logger.info(f"{urls[i]} upload failed")

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
        zip_content = None
        try:
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            res_zip = requests.get(zip_url, verify=False, proxies={"http": None, "https": None}, timeout=30)
            if res_zip.status_code == 200:
                zip_content = res_zip.content
            else:
                logger.warning(f"requests下载zip文件返回状态码: {res_zip.status_code}，尝试使用系统 curl 下载...")
        except Exception as e:
            logger.warning(f"requests下载zip发生异常: {e}，尝试使用系统 curl 下载...")

        if zip_content is None:
            # Fallback 方案: 使用系统 curl 进程下载
            import subprocess
            import tempfile
            import os

            temp_dir = tempfile.gettempdir()
            temp_zip_path = os.path.join(temp_dir, f"mineru_{batch_id}.zip")
            try:
                logger.info("正在通过系统 curl 进程拉取 ZIP 文件...")
                # Windows 10/11 系统均默认内置 curl.exe
                res = subprocess.run(["curl", "-L", "-o", temp_zip_path, zip_url], capture_output=True, text=True)
                if res.returncode == 0 and os.path.exists(temp_zip_path) and os.path.getsize(temp_zip_path) > 0:
                    with open(temp_zip_path, "rb") as f:
                        zip_content = f.read()
                    os.remove(temp_zip_path)
                    logger.info("系统 curl 进程下载成功！")
                else:
                    logger.error(f"curl 进程下载失败，返回码: {res.returncode}, 错误信息: {res.stderr}")
            except Exception as curl_err:
                logger.error(f"调用系统 curl 发生错误: {curl_err}")

        if zip_content is None:
            logger.error("下载zip文件失败")
            raise ValueError(
                "下载zip文件失败，requests 与 curl 均无法拉取该文件，请检查您的代理软件分流规则中是否拦截了 cdn-mineru.openxlab.org.cn 域名。"
            )

        return zip_content

    def write_zip_and_rename(self, local_path_obj: Path, pdf_path_obj: Path, zip_content: bytes) -> ImportGraphState:
        # zip写进磁盘
        zip_file_path = local_path_obj / f"{pdf_path_obj.stem}.zip"
        with open(zip_file_path, "wb") as f:
            f.write(zip_content)

        # 解压zip
        import zipfile, shutil

        unzip_content_path_obj = local_path_obj / pdf_path_obj.stem  # zip文件解压的目标路径
        # 保持解压幂等性
        if unzip_content_path_obj.exists():
            shutil.rmtree(unzip_content_path_obj)
        with zipfile.ZipFile(zip_file_path, "r") as unzip_content:
            unzip_content.extractall(unzip_content_path_obj)

        # 重命名full.md为pdf_path_obj.stem + ".md"
        target_md = unzip_content_path_obj / f"{pdf_path_obj.stem}.md"  # stem会去掉路径,也去掉后缀
        full_md = unzip_content_path_obj / "full.md"
        if full_md.exists():
            if target_md.exists():
                target_md.unlink()  # 目标文件若已存在则删除，避免 Windows 下 rename 抛错
            full_md.rename(target_md)

        # 读取md文本内容
        with open(target_md, "r", encoding="utf-8") as f:
            md_content = f.read()

        logger.info(f"{str(target_md)}路径已经提供")
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
