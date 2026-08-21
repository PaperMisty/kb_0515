from atguigu.tool.task_utils import TASK_STATUS_FAILED
from atguigu.tool.task_utils import TASK_STATUS_COMPLETED
from atguigu.tool.task_utils import TASK_STATUS_PROCESSING
from atguigu.tool.task_utils import update_task_status
from atguigu.tool.task_utils import get_task_info
from atguigu.tool.task_utils import add_done_task
from atguigu.tool.task_utils import add_running_task
from atguigu.config.config import OUTPUT_DIR
from atguigu.import_process.main_graph import GraphRunner
from fastapi import BackgroundTasks
from atguigu.config.config import MinIOConfig
from datetime import datetime
import uuid
import aiofiles
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from atguigu.config.config import RAW_DIR, STATIC_DIR
from atguigu.tool.minio_client_tool import get_minio_client
from atguigu.tool.logger import logger
from fastapi.responses import FileResponse

# 知识库导入处理模块
app = FastAPI(
    title="RAG导入模块",
    description="处理PDF、网页、文本导入知识库、生成摘要、向量化、存储到向量数据库的模块",
    version="0.0.1",
)
# 解决跨域问题
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 挂载静态目录

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "import.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


def run_main_graph(task_id: str, file_path: str, file_path_output: str):
    try:
        init_state = {"task_id": task_id, "local_file_path": file_path, "local_dir": file_path_output}
        update_task_status(task_id, TASK_STATUS_PROCESSING)
        GraphRunner.create_and_run(init_state)
        update_task_status(task_id, TASK_STATUS_COMPLETED)
    except Exception as e:
        # 修改任务状态: 主图执行完毕
        update_task_status(task_id, TASK_STATUS_FAILED)
        logger.error(f"主图执行失败,错误信息:{e}")
        raise Exception(f"主图执行失败,错误信息:{e}")


@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(..., description="文件描述")):
    # 1.生成task_id
    task_id = str(uuid.uuid4())

    # 修改任务状态: 上传中
    background_tasks.add_task(add_running_task, task_id, "upload_file")

    # 2.保存指定位置
    upload_dir = RAW_DIR / datetime.now().strftime("%Y%m%d")
    upload_dir.mkdir(parents=True, exist_ok=True)  # 如果路径不存在 → 创建目录;如果路径已存在 → 静默忽略，不做任何改变
    file_path = upload_dir / file.filename
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            await f.write(chunk)
    logger.info(f"文件上传服务器成功:{file_path}")

    # 修改任务状态: 上传完成

    background_tasks.add_task(add_done_task, task_id, "upload_file")

    # 3.备份文件到MinIO
    minio_client = get_minio_client()
    minio_client.fput_object(
        bucket_name=MinIOConfig.minio_bucket_name,
        object_name=f"pdf_file/{datetime.now().strftime('%Y%m%d')}/{task_id}/{file.filename}",
        file_path=str(file_path),
    )

    logger.info(
        f"文件上传到MinIO成功,路径: {MinIOConfig.minio_bucket_name + '/' + 'pdf_file' + '/' + datetime.now().strftime('%Y%m%d') + '/' + task_id + '/' + file.filename}"
    )

    # 4. 跑后台任务:主图
    dir_name = OUTPUT_DIR / datetime.now().strftime("%Y%m%d")
    dir_name.mkdir(parents=True, exist_ok=True)

    file_path_output = OUTPUT_DIR / dir_name
    background_tasks.add_task(run_main_graph, task_id, str(file_path), str(file_path_output))

    # 前端只需要task_id
    return {"task_id": task_id}


# 实现前端轮询的接口
@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    # 安全获取指定任务的总体运行状态，若不存在则返回空字符串
    return get_task_info(task_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("import_process:app", port=8000, reload=True, reload_excludes=["*.pdf", "*.md", ".jpg", "**/data/**"])
