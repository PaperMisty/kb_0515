# import time
# from functools import wraps
# import random


# def rate_limiter(max_calls: int, period: float):
#     """
#     限流装饰器（固定时间窗口）
#     :param max_calls: 周期内最大允许调用次数
#     :param period: 时间窗口，单位：秒
#     """

#     def decorator(func):
#         # 保存每次调用的时间戳，闭包变量
#         call_records = []

#         @wraps(func)
#         def wrapper(*args, **kwargs):
#             now = time.time()
#             # 清除窗口外过期的时间戳
#             nonlocal call_records
#             call_records = [
#                 t for t in call_records if now - t <= period
#             ]  # 每次重新 筛出后面那些仍在时限(比如6s)内的数据,判定是否可以执行函数

#             if len(call_records) >= max_calls:
#                 raise RuntimeError(f"触发限流！{period}秒内最多调用{max_calls}次")

#             call_records.append(now)
#             return func(*args, **kwargs)

#         return wrapper

#     return decorator


# # ========== 测试 ==========
# # 示例：6秒内最多调用3次
# @rate_limiter(max_calls=3, period=6)
# def test_api():
#     print("函数执行成功")


# if __name__ == "__main__":
#     for i in range(40):
#         try:
#             test_api()
#         except Exception as e:
#             print(e)
#         time.sleep(random.random())
import time
from collections import deque

current_time = time.time()
img_context_list = range(30)
bucket = deque(maxlen=5)

for idx, img_context in enumerate(img_context_list):
    print(f"{idx}: {bucket=}")
    # 盲清一波队列
    while bucket and current_time - bucket[0] > 60:
        bucket.popleft()
    # 如果满员, 睡一定时间,睡完再出队第一个, 并入队新的请求时间戳(通过睡眠来控制后文的请求频率)
    print(f"{len(bucket)=},{bucket.maxlen=}")

    if bucket and len(bucket) == bucket.maxlen:
        time.sleep(60 - (time.time() - bucket[0]))
        while bucket and time.time() - bucket[0] > 60:
            bucket.popleft()
    # 最开始, bucket为空队列, 可以快速打满30个请求, 并且append进去;(归根结底还是串行,而且不方便开协程优化)
    bucket.append(time.time())

    time.sleep(0.5)
