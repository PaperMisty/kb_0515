# atguigu/tool/logger.py

import logging
import colorlog

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }
))

# logger.handlers.clear()
logger.addHandler(handler)
if __name__ == "__main__":
    logger.info("这是一个信息级别的日志")
    logger.debug("这是一个调试级别的日志")
    logger.warning("这是一个警告级别的日志")
    logger.error("这是一个错误级别的日志")
    logger.critical("这是一个严重错误的日志")