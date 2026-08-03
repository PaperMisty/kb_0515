import time
import zipfile
import shutil
import requests
from pathlib import Path
from atguigu.config.config import MineruConfig
from atguigu.tool.logger import logger
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState


# =====================================================================
# 1. 业务逻辑层：高内聚的 Mineru 转换器（只关注 PDF -> MD 的具体技术细节）
# =====================================================================
class MineruPDFConverter:
    """专职与 Mineru API 交互并处理文件的工具类"""

    def __init__(self, token: str, base_url: str):
        self.token = token
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    def convert(self, pdf_path: Path, output_dir: Path) -> Path:
        """主入口：输入 PDF，输出 MD 文件路径"""
        # 1. 申请上传链接
        batch_id, upload_urls = self._apply_for_upload_urls(pdf_path.name)
        # 2. 直传文件
        self._upload_file(pdf_path, upload_urls)
        # 3. 轮询并获取 ZIP 下载地址
        zip_url = self._poll_for_zip_url(batch_id)
        # 4. 下载并解压
        md_file_path = self._download_and_extract(zip_url, pdf_path.stem, output_dir)

        return md_file_path

    def _apply_for_upload_urls(self, file_name: str) -> tuple[str, list[str]]:
        url = f"{self.base_url}/file-urls/batch"
        data = {
            "files": [{"name": file_name, "data_id": "abcd"}],
            "model_version": "vlm",
        }
        res = requests.post(url, headers=self.headers, json=data)
        if res.status_code != 200 or res.json().get("code") != 0:
            raise RuntimeError("申请 Mineru 上传文件链接失败")

        result_data = res.json()["data"]
        return result_data["batch_id"], result_data["file_urls"]

    def _upload_file(self, file_path: Path, upload_urls: list[str]):
        # 直传第一阶段拿到的链接
        for url in upload_urls:
            with open(file_path, "rb") as f:
                res = requests.put(url, data=f)
                if res.status_code != 200:
                    raise RuntimeError(f"直传文件失败，S3响应码: {res.status_code}")
        logger.info("PDF 文件直传成功")

    def _poll_for_zip_url(self, batch_id: str, max_retries: int = 30) -> str:
        url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"

        for _ in range(max_retries):
            res = requests.get(url, headers=self.headers)
            if res.status_code == 200 and res.json().get("code") == 0:
                data = res.json()["data"]["extract_result"][0]
                if data["state"] == "done":
                    return data["full_zip_url"]
                logger.debug(f"Mineru 解析中，当前状态: {data['state']}")
            time.sleep(2)

        raise TimeoutError("等待 Mineru 解析超时")

    def _download_and_extract(
        self, zip_url: str, file_stem: str, output_dir: Path
    ) -> Path:
        # 下载 ZIP
        res = requests.get(zip_url)
        if res.status_code != 200:
            raise RuntimeError("下载结果 ZIP 包失败")

        # 写入 ZIP 临时文件
        zip_file = output_dir / f"{file_stem}.zip"
        zip_file.write_bytes(res.content)

        # 清理旧目录并解压
        extract_dir = output_dir / file_stem
        if extract_dir.exists():
            shutil.rmtree(extract_dir)

        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        # 自动重命名 full.md 为指定名字
        full_md = extract_dir / "full.md"
        target_md = extract_dir / f"{file_stem}.md"
        if full_md.exists():
            if target_md.exists():
                target_md.unlink()
            full_md.rename(target_md)

        # 清理临时 zip 文件
        if zip_file.exists():
            zip_file.unlink()

        return target_md


# =====================================================================
# 2. 工作流节点层：低耦合的 LangGraph 节点（只关注 Graph 的输入输出转换）
# =====================================================================
class NodePDFToMD(NodeBase):
    name = "node_pdf_to_md"

    def process(self, state: ImportGraphState):
        # 1. 解析并校验输入状态
        pdf_path, local_dir = self._validate_and_parse_state(state)

        # 2. 实例化转换器并执行转换 (核心职责委派)
        converter = MineruPDFConverter(
            token=MineruConfig.mineru_token, base_url=MineruConfig.mineru_base_url
        )
        md_path = converter.convert(pdf_path, local_dir)

        # 3. 读取结果
        md_content = md_path.read_text(encoding="utf-8")

        # 4. 返回更新后的状态字典
        return {
            "md_content": md_content,
            "md_path": str(md_path),
        }

    def _validate_and_parse_state(self, state: ImportGraphState) -> tuple[Path, Path]:
        """专门负责解析与校验输入状态"""
        pdf_path_str = state.get("pdf_path")
        local_dir_str = state.get("local_dir")

        if not pdf_path_str or not local_dir_str:
            raise ValueError("pdf_path 或 local_dir 不能为空")

        pdf_path = Path(pdf_path_str)
        local_dir = Path(local_dir_str)

        if not pdf_path.exists():
            raise FileNotFoundError(f"未找到指定的 PDF 文件: {pdf_path}")

        local_dir.mkdir(parents=True, exist_ok=True)
        return pdf_path, local_dir
