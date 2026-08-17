import json
import numpy as np

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        # 兼容 NumPy 整数和浮点数
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        
        # 兼容 MongoDB ObjectId 类型，防止 JSON 序列化失败
        if obj.__class__.__name__ == "ObjectId":
            return str(obj)
            
        # 如果是其他 numpy 标量类型，尝试通过 .item() 转换
        if hasattr(obj, "item") and callable(obj.item):
            return obj.item()
            
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


def json_format(data):
    return json.dumps(data, cls=CustomEncoder, ensure_ascii=False, indent=4)
