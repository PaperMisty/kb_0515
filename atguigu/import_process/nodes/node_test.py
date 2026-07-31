from atguigu.tool.logger import logger
from atguigu.import_process.base import NodeBase
class NodeTest(NodeBase):
    name = "node_test"
    def process(self,state):
        logger.info("node_test开始执行了...")
        return state

if __name__ == "__main__":
    node_test = NodeTest()
    state = {}
    res = node_test(state)
    # logger.info(res)