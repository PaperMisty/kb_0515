# 定义一个基础节点接口，所有节点都继承这个接口
from atguigu.tool.task_utils import update_task_status
from atguigu.tool.task_utils import add_running_task, add_done_task, add_node_duration
from atguigu.tool.logger import logger
from abc import abstractmethod
from abc import ABC
import time


class NodeBase(ABC):
    name = "Node_name"

    def __init__(self):
        if self.name == NodeBase.name:
            raise ValueError(
                f"子类{self.__class__.__name__} 的Node name 必须被设置"
            )  # 在compile之前就可以报错,不会浪费资源

    @abstractmethod
    def process(self, state):
        pass

    def __call__(self, state):
        task_id = state["task_id"]
        try:
            start_time = time.time()
            logger.info(f"{self.name}开始执行了...")

            # 修改节点的执行状态列表
            add_running_task(task_id, self.name)

            res = self.process(state)
            logger.info(f"{self.name}执行结束了...")

            # 修改节点的完成状态列表
            add_done_task(task_id, self.name)

            # 修改节点的耗时列表
            end_time = time.time()
            add_node_duration(task_id, self.name, end_time - start_time)
            return res
        except Exception as e:
            logger.error(f"{self.name}执行失败了...")
            raise e
