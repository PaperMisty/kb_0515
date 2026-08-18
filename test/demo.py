# atguigu/test/myfastapi/mount_static.py

from fastapi import Depends
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi import FastAPI, Request

app = FastAPI()

# 当前文件目录
BASE_DIR = Path(__file__).parent
print("当前文件目录：", BASE_DIR)
static_dir = BASE_DIR / "static"

# 挂载静态文件
# 第一个参数：所有以 /static 开头的请求都交给这个模块处理
# 第二个参数：指定静态文件的存放目录
# 第三个参数：给挂载点起个名字（路由的名字）
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
# 用户访问：http://127.0.0.1:8000/static/image.png
#      ↓
# FastAPI 看到 "/static" 开头
#      ↓
# 交给 StaticFiles 处理
#      ↓
# StaticFiles 去 {static_dir} 找文件
#      ↓
# 返回给用户


@app.get("/testheader")
def testheader(request: Request):
    AcceptEncoding = request.headers.get("Accept-Encoding")
    print(AcceptEncoding)
    return {"Accept-Encoding": AcceptEncoding}


from fastapi import FastAPI

app = FastAPI()


# 情况1：使用普通类
class User:
    def __init__(self, name: str, age: int):
        self.name = name
        self.age = age


@app.post("/users")
def create_user(user: User = Depends(User)):  # ❌ 这会报错！
    return {"name": user.name, "age": user.age}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("demo:app", host="127.0.0.1", port=8001, reload=True)
