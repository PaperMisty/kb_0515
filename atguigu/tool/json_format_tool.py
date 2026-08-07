import json
import numpy as np


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        # 如果是其他 numpy 标量类型，尝试通过 .item() 转换为 Python 原生类型
        if hasattr(obj, "item") and callable(obj.item):
            return obj.item()
        return super().default(obj)


def json_format(data):
    return json.dumps(data, ensure_ascii=False, indent=4)
