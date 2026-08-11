# atguigu/query_process/nodes/node_item_name_confirm.py
from atguigu.tool.mongo_client_tool import add_or_update_data
import json
import datetime
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.logger import logger


class NodeItemNameConfirm(NodeBase):
    """
    节点功能：确认用户问题中的核心商品名称。
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_item_name_confirm"

    def process(self, state: QueryGraphState):
        """
        节点逻辑
        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """

        logger.info(f"【{self.name}】节点逻辑")

        return state


if __name__ == "__main__":
    session_id = "test_001"
    # 测试:添加数据
    data_dict = {
        "session_id": session_id,
        "role": "user",
        "text": "咨询下烫金机。",
        "rewritten_query": None,
        "item_names": None,
        "ts": datetime.datetime.now(),
    }
    add_or_update_data(data_dict)

    data_dict = {
        "session_id": session_id,
        "role": "assistant",
        "text": "您好。请问是哪个型号",
        "rewritten_query": None,
        "item_names": None,
        "ts": datetime.datetime.now(),
    }
    add_or_update_data(data_dict)

    data_dict = {
        "session_id": session_id,
        "role": "user",
        "text": "hak180",
        "rewritten_query": None,
        "item_names": None,
        "ts": datetime.datetime.now(),
    }
    add_or_update_data(data_dict)

    data_dict = {
        "session_id": session_id,
        "role": "assistant",
        "text": "具体有什么问题呢？",
        "rewritten_query": None,
        "item_names": None,
        "ts": datetime.datetime.now(),
    }
    add_or_update_data(data_dict)
