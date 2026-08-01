# 定义一个基础节点接口，所有节点都继承这个接口
from atguigu.tool.logger import logger
from abc import abstractmethod
from abc import ABC


class NodeBase(ABC):
    name = "Node_name"

    def __init__(self):
        if self.name == NodeBase.name:
            raise ValueError(f"子类{self.__class__.__name__} 的Node name 必须被设置")

    @abstractmethod
    def process(self, state):
        pass

    def __call__(self, state):
        try:
            logger.info(f"{self.name}开始执行了...")
            res = self.process(state)
            logger.info(f"{self.name}执行结束了...")
            return res
        except Exception as e:
            logger.error(f"{self.name}执行失败了...")
            raise e
