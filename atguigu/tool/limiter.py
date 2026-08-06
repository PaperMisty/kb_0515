from collections import deque
import time
import asyncio
from functools import wraps


def async_rate_limiter(max_calls: int, period: float):
    """
    异步阻塞式限流装饰器（滑动窗口）
    当触发限流时，会自动等待（sleep）直到有空余额度，而不是抛出异常。
    """

    def decorator(func):
        # 保存调用时间戳的闭包变量
        bucket = deque(maxlen=max_calls)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal bucket  # 可变对象,可以不加nonlocal

            while True:
                now = time.time()
                # 清理窗口外过期的时间戳
                while bucket and time.time() - bucket[0] > period:
                    bucket.popleft()

                # 如果当前窗口内调用次数没超限，允许调用
                if len(bucket) < max_calls:
                    bucket.append(now)
                    return await func(*args, **kwargs)

                # 如果超限了，计算需要等待多久（最早的一次调用滑出窗口的时间）
                sleep_time = period - (now - bucket[0]) + 0.1
                if sleep_time > 0:
                    # 异步休眠，不阻塞其他协程
                    await asyncio.sleep(sleep_time)

        return wrapper

    return decorator
