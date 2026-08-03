<<<<<<< HEAD
import time
from functools import wraps
import random


def rate_limiter(max_calls: int, period: float):
    """
    限流装饰器（固定时间窗口）
    :param max_calls: 周期内最大允许调用次数
    :param period: 时间窗口，单位：秒
    """

    def decorator(func):
        # 保存每次调用的时间戳，闭包变量
        call_records = []

        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            # 清除窗口外过期的时间戳
            nonlocal call_records
            call_records = [
                t for t in call_records if now - t <= period
            ]  # 每次重新 筛出后面那些仍在时限(比如6s)内的数据,判定是否可以执行函数

            if len(call_records) >= max_calls:
                raise RuntimeError(f"触发限流！{period}秒内最多调用{max_calls}次")

            call_records.append(now)
            return func(*args, **kwargs)

        return wrapper

    return decorator


# ========== 测试 ==========
# 示例：6秒内最多调用3次
@rate_limiter(max_calls=3, period=6)
def test_api():
    print("函数执行成功")


if __name__ == "__main__":
    for i in range(40):
        try:
            test_api()
        except Exception as e:
            print(e)
        time.sleep(random.random())
=======
a = {"name": "Alice"}
a["age"] = 18
print(a)
>>>>>>> e3c7ccd18ccd3713b063fd6722011b10640c7370
