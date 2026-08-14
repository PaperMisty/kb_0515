# atguigu/import_process/nodes/node_ppt_to_md.py
import base64
import json
import os
import re
import shutil
import time
from pathlib import Path
from datetime import timedelta

import pythoncom
import win32com.client
from PIL import Image
from langchain.chat_models import init_chat_model

from atguigu.config.config import MinIOConfig, LLMConfig, OUTPUT_DIR, RAW_DIR
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.logger import logger
from atguigu.tool.minio_client_tool import get_minio_client
from atguigu.tool.validate_path import validate_path


class NodePPTToMD(NodeBase):
    """
    PPT 转 Markdown 节点：
    1. 将 PPT/PPTX 各页 Slide 转为图片 (通过 win32com 驱动 PowerPoint 或 WPS)
    2. 等比例限制最长边在 1024-2048 像素之间
    3. 上传图片至 MinIO，支持获取匿名直连 URL 或临时预签名 URL
    4. 调用 VLM (Base64) 识别每页 Slide 的标题与内容
    5. 组装成 Markdown 文档
    """

    name = "node_ppt_to_md"

    def __init__(self, use_presigned_url: bool = False):
        """
        Args:
            use_presigned_url (bool): 是否使用 MinIO 的预签名 URL 写入 Markdown。默认 False。
        """
        self.use_presigned_url = use_presigned_url

    def process(self, state: ImportGraphState) -> ImportGraphState:
        # 1. 校验输入路径
        ppt_path_str = state.get("ppt_path")
        local_dir_str = state.get("local_dir")

        if not ppt_path_str or not local_dir_str:
            raise ValueError("ppt_path 或 local_dir 不能为空")

        ppt_path = Path(ppt_path_str)
        local_dir = Path(local_dir_str)

        if not ppt_path.exists():
            raise FileNotFoundError(f"未找到指定的 PPT 文件: {ppt_path}")

        local_dir.mkdir(parents=True, exist_ok=True)
        file_title = state.get("file_title", ppt_path.stem)

        # 临时工作目录，用来存放 PPT 导出的原始图片与缩放后的图片
        temp_work_dir = local_dir / f"temp_{file_title}"
        if temp_work_dir.exists():
            shutil.rmtree(temp_work_dir)
        temp_work_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: PPT 导出图片
            raw_export_dir = temp_work_dir / "raw_slides"
            raw_export_dir.mkdir(parents=True, exist_ok=True)
            self._export_ppt_to_images(ppt_path, raw_export_dir)

            # 获取并按页码排序导出的图片
            raw_images = [
                f for f in os.listdir(raw_export_dir)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if not raw_images:
                raise RuntimeError("PPT 导出图片失败，未在导出目录中找到任何图片文件。")

            # 按照文件名中的数字进行排序，避免字符排序问题 (如 Slide10.JPG 排在 Slide2.JPG 前面)
            def get_slide_num(filename):
                nums = re.findall(r"\d+", filename)
                return int(nums[0]) if nums else 0

            raw_images.sort(key=get_slide_num)
            logger.info(f"成功导出 PPT，共有 {len(raw_images)} 页 Slide。")

            # Step 2 & 3 & 4: 尺寸缩放、上传 MinIO、VLM 识别
            processed_dir = temp_work_dir / "processed_slides"
            processed_dir.mkdir(parents=True, exist_ok=True)

            minio_client = get_minio_client()
            llm = init_chat_model(
                model=LLMConfig.vlm_model,
                model_provider="openai",
                base_url=LLMConfig.base_url,
                api_key=LLMConfig.api_key,
                temperature=LLMConfig.temperature,
            )

            # 幂等性清理 MinIO 中已存在的同名 PPT 图片目录
            self._clear_minio_ppt_dir(minio_client, file_title)

            markdown_sections = []

            for idx, img_name in enumerate(raw_images, 1):
                raw_img_path = raw_export_dir / img_name
                resized_img_path = processed_dir / f"{file_title}-{idx}.jpg"

                # 2. 等比例限制最长边在 1024-2048 像素之间
                self._resize_image(raw_img_path, resized_img_path)

                # 3. 上传到 MinIO
                object_name = f"{MinIOConfig.minio_img_dir}/{file_title}/{file_title}-{idx}.jpg"
                minio_client.fput_object(
                    bucket_name=MinIOConfig.minio_bucket_name,
                    object_name=object_name,
                    file_path=str(resized_img_path),
                )

                # 获取线上图片 URL (供最终 Markdown 引用)
                if self.use_presigned_url:
                    # 获取预签名 URL (此处设为 7 天有效期)
                    img_online_url = minio_client.presigned_get_object(
                        bucket_name=MinIOConfig.minio_bucket_name,
                        object_name=object_name,
                        expires=timedelta(days=7)
                    )
                else:
                    # 默认使用直连永久 URL (基于 Bucket 的 Anonymous Read-Only 策略)
                    img_online_url = (
                        f"http://{MinIOConfig.minio_endpoint}/"
                        f"{MinIOConfig.minio_bucket_name}/{object_name}"
                    )

                # 4. 调用 VLM 模型提取当前幻灯片标题与正文
                logger.info(f"开始利用 VLM 分析第 {idx} 页 Slide...")
                title, content = self._extract_slide_content(llm, resized_img_path)
                logger.info(f"第 {idx} 页分析完成. Title: '{title}'")

                # 5. 拼装当前 Slide 的 Markdown 内容
                slide_section = (
                    f"# Slide {idx}: {title}\n\n"
                    f"![{file_title}-{idx}]({img_online_url})\n\n"
                    f"{content}\n"
                )
                markdown_sections.append(slide_section)

            # 拼接完整的 Markdown 全文
            md_content = f"# {file_title}\n\n" + "\n---\n\n".join(markdown_sections)

            # 将组装后的 Markdown 写入磁盘
            md_dir = local_dir / file_title
            md_dir.mkdir(parents=True, exist_ok=True)
            target_md_path = md_dir / f"{file_title}.md"
            target_md_path.write_text(md_content, encoding="utf-8")
            logger.info(f"Markdown 文件已生成: {target_md_path}")

            return {
                "md_content": md_content,
                "md_path": str(target_md_path),
            }

        finally:
            # 清理临时工作目录
            if temp_work_dir.exists():
                shutil.rmtree(temp_work_dir)
                logger.info("已清理临时 PPT 图片转换目录。")

    def _export_ppt_to_images(self, ppt_path: Path, output_dir: Path) -> None:
        """调用 Windows PowerPoint/WPS 导出 PPT 为 JPG 图片"""
        pythoncom.CoInitialize()
        ppt_app = None
        presentation = None
        try:
            # 1. 尝试使用 Microsoft PowerPoint
            try:
                ppt_app = win32com.client.Dispatch("PowerPoint.Application")
            except Exception as e:
                logger.warning(f"无法启动 PowerPoint.Application，尝试 WPS: {e}")
                # 2. 尝试使用 WPS WPP 演示
                try:
                    ppt_app = win32com.client.Dispatch("Wpp.Application")
                except Exception as e_wps:
                    logger.error(f"无法启动 WPS Wpp.Application: {e_wps}")
                    raise RuntimeError("未检测到系统安装有 PowerPoint 或 WPS Office，无法导出 PPT 图片。")

            ppt_path_abs = str(ppt_path.resolve())
            output_dir_abs = str(output_dir.resolve())

            # Open 核心参数：Open(FileName, ReadOnly, Untitled, WithWindow)
            # WithWindow=False 代表在后台无窗口运行
            presentation = ppt_app.Presentations.Open(
                ppt_path_abs,
                ReadOnly=True,
                Untitled=False,
                WithWindow=False
            )
            # SaveAs(FileName, FileFormat): 17 代表 ppSaveAsJPG
            presentation.SaveAs(output_dir_abs, 17)
        finally:
            if presentation:
                try:
                    presentation.Close()
                except Exception:
                    pass
            if ppt_app:
                try:
                    ppt_app.Quit()
                except Exception:
                    pass
            pythoncom.CoUninitialize()

    def _resize_image(self, src_path: Path, dest_path: Path) -> None:
        """限制最长边在 1024-2048 像素之间，等比例缩放"""
        with Image.open(src_path) as img:
            width, height = img.size
            max_side = max(width, height)
            
            new_width, new_height = width, height
            if max_side > 2048:
                scale = 2048 / max_side
                new_width, new_height = int(width * scale), int(height * scale)
            elif max_side < 1024:
                scale = 1024 / max_side
                new_width, new_height = int(width * scale), int(height * scale)
                
            if (new_width, new_height) != (width, height):
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"图片缩放: 原尺寸 ({width}x{height}) -> 新尺寸 ({new_width}x{new_height})")

            # 强制转换为 RGB 并以 JPG 保存
            img.convert("RGB").save(dest_path, "JPEG", quality=90)

    def _clear_minio_ppt_dir(self, minio_client, file_title: str) -> None:
        """清理 MinIO 中已存在的同名 PPT 图片"""
        from minio.deleteobjects import DeleteObject
        prefix = f"{MinIOConfig.minio_img_dir}/{file_title}"
        try:
            objects_to_delete = minio_client.list_objects(
                bucket_name=MinIOConfig.minio_bucket_name,
                prefix=prefix,
                recursive=True
            )
            delete_list = [DeleteObject(obj.object_name) for obj in objects_to_delete]
            if delete_list:
                errors = minio_client.remove_objects(
                    bucket_name=MinIOConfig.minio_bucket_name,
                    delete_object_list=delete_list
                )
                for err in errors:
                    logger.error(f"删除 MinIO 历史图片失败: {err}")
        except Exception as e:
            logger.warning(f"清理 MinIO 历史 PPT 目录时发生异常: {e}")

    def _extract_slide_content(self, llm, img_path: Path) -> tuple[str, str]:
        """将图片转为 Base64 编码，调用 VLM (qwen3-vl-flash) 提取标题和内容"""
        with open(img_path, "rb") as f:
            base64_data = base64.b64encode(f.read()).decode("utf-8")

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_data}",
                        },
                    },
                    {
                        "type": "text",
                        "text": """请提取这张 PPT 幻灯片图片中的“标题 (title)”和“正文内容 (content)”。
请严格按照以下 JSON 格式输出，不要包含任何 markdown 格式标记（如 ```json 等），也不要包含任何其他解释性文本：
{
    "title": "这里是提取出来的标题",
    "content": "这里是提取出来的详细正文内容，若有多项列表请用换行或 bullet points 整理"
}
如果图片中没有明显的标题，则 title 返回空字符串，本格式必须返回合法的 JSON 格式。""",
                    },
                ],
            },
        ]

        try:
            response = llm.invoke(messages)
            content_str = response.content.strip()
            
            # 清理可能被大模型额外包裹的 Markdown ```json 代码块标记
            if content_str.startswith("```"):
                content_str = re.sub(r"^```[a-zA-Z]*\n", "", content_str)
                content_str = re.sub(r"\n```$", "", content_str)
            content_str = content_str.strip()

            data = json.loads(content_str)
            return data.get("title", ""), data.get("content", "")
        except Exception as e:
            logger.error(f"VLM 内容提取或 JSON 解析失败: {e}。将退化至将完整返回文本作为正文。")
            return "", response.content if 'response' in locals() else ""


if __name__ == "__main__":
    # 单节点调试
    import logging
    logging.basicConfig(level=logging.INFO)

    node = NodePPTToMD(use_presigned_url=False)
    
    # 模拟输入参数，请在您的电脑中确保有对应的测试 PPT 文件
    test_ppt = RAW_DIR / "测试PPT.pptx"
    
    # 如果不存在测试文件，则创建一个空测试
    if not test_ppt.exists():
        logger.info(f"未找到测试 PPT 文件，测试已跳过。路径为: {test_ppt}")
    else:
        init_state = {
            "ppt_path": str(test_ppt),
            "local_dir": str(OUTPUT_DIR),
            "file_title": "测试PPT",
        }
        res = node(init_state)
        print("测试返回状态：", res)
