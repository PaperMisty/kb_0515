from fastapi.responses import StreamingResponse
from atguigu.tool.task_utils import TASK_STATUS_FAILED
from atguigu.tool.task_utils import TASK_STATUS_COMPLETED
from atguigu.tool.task_utils import get_task_info
from atguigu.tool.task_utils import TASK_STATUS_PROCESSING
from atguigu.tool.task_utils import update_task_status
import uuid
from fastapi import BackgroundTasks
from fastapi import Body
from atguigu.query_process.main_graph import QueryMainGraphRunner
from pydantic import Field
from pydantic import BaseModel
from atguigu.tool.mongo_client_tool import clear_history
from atguigu.tool.mongo_client_tool import get_recent_history_list
from fastapi import Path
import uvicorn, json, time
from fastapi import FastAPI
from queue import Queue
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="检索模块对应的接口", description="检索知识库, 回答用户问题", version="0.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 心跳请求
@app.get("/health")
async def health():
    return {"status": "ok"}


# 获取历史记录
@app.get("/history/{session_id}")
async def get_history(session_id: str = Path(..., description="会话ID")):
    """
    获取历史记录
    :param session_id: 会话ID
    :return: 会话历史记录列表
    """
    history_lst = get_recent_history_list(session_id, limit=10, reverse=False)
    # 需要将_id转换为字符串
    for item in history_lst:
        item["_id"] = str(item["_id"])
    print("get", session_id)
    return {"items": history_lst}


# 删除历史记录
@app.delete("/history/{session_id}")
async def delete_history(session_id: str = Path(..., description="会话ID")):
    """
    删除历史记录
    :param session_id: 会话ID
    :return: 删除结果
    """
    clear_history({"session_id": session_id})
    print("clear:", session_id)
    return {"status": "ok"}


# 发起提问
class Query(BaseModel):
    query: str = Field(..., description="问题")
    session_id: str = Field(..., description="会话ID")


queue_dict = {}


def run_main_graph(task_id, original_query, session_id):

    if not queue_dict.get(task_id):
        queue_dict[task_id] = Queue()
    q = queue_dict[task_id]
    init_state = {"task_id": task_id, "original_query": original_query, "session_id": session_id, "q": q}
    try:
        # 更新主图状态
        update_task_status(task_id, TASK_STATUS_PROCESSING)
        # 放入队列,前端可以监听这个队列,获取主图的状态
        q.put({"event": "progress", "data": get_task_info(task_id)})
        QueryMainGraphRunner.create_and_run(init_state)
        update_task_status(task_id, TASK_STATUS_COMPLETED)
        q.put({"event": "progress", "data": get_task_info(task_id)})
    except Exception as e:
        update_task_status(task_id, TASK_STATUS_FAILED)
        q.put({"event": "error", "data": get_task_info(task_id)})


@app.post("/query")
async def query(background_tasks: BackgroundTasks, query: Query = Body(..., description="查询请求体参数")):
    original_query = query.query
    session_id = query.session_id
    task_id = str(uuid.uuid4())
    # 添加任务到后台
    background_tasks.add_task(run_main_graph, task_id, original_query, session_id)
    # 将查询结果返回给前端
    return {"task_id": task_id, "original_query": original_query, "session_id": session_id}


# 生成流式内容加入队列, 并定期清除
def generate_stream(task_id):
    while not queue_dict.get(task_id):
        time.sleep(0.1)
    q = queue_dict.get(task_id)
    try:
        while True:
            data = q.get()
            yield f"event: {data.get('event')}\n"
            yield f"data: {json.dumps(data.get('data'), ensure_ascii=False)}\n\n"

            # 1. 安全提取属性，规避当 data["data"] 是字符串(如 event="final" 时为 "")而非 dict 时调用 .get("status") 导致的报错
            event_type = data.get("event")
            data_content = data.get("data")
            status = data_content.get("status") if isinstance(data_content, dict) else None

            # 2. 如果收到 error、final 事件或整个任务状态变为已完成/已失败，则主动退出流，结束连接
            if event_type == "error" or event_type == "final" or status in ["completed", "failed"]:
                break
    except GeneratorExit:
        # 当客户端主动断开连接（如刷新网页、关闭标签）或服务端关闭连接时，捕获此异常优雅关闭，不报取消错误
        pass
    except Exception as e:
        # 防止打印日志失败引起服务崩掉，安全记录
        try:
            from atguigu.tool.logger import logger
            logger.error(f"流式推送中遇到未知异常: {e}")
        except:
            pass
    finally:
        # 3. 无论何种情况结束，都释放队列，防止内存溢出泄露
        if task_id in queue_dict:
            del queue_dict[task_id]


@app.get("/stream/{task_id}")
async def stream(task_id: str = Path(..., description="任务ID")):
    return StreamingResponse(generate_stream(task_id), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run("query_service:app", port=8001, reload=True)
