from pathlib import Path
from atguigu.tool.logger import logger


def validate_path(path: Path, level: str) -> Path:
    # 判定路径是否可得
    if not path or (not path.exists()):
        if level == "error":
            logger.error(f"路径无法读取/无内容:{path=}")
            raise FileNotFoundError("路径无法读取")
        elif level == "warning":
            logger.warning(f"路径无法读取/无内容:{path=}")
        elif level == "info":
            logger.info(f"路径无法读取/无内容:{path=}")
        elif level == "debug":
            logger.debug(f"路径无法读取/无内容:{path=}")
    return path
