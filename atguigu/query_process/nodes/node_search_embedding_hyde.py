# atguigu/query_process/nodes/node_search_embedding_hyde.py

from atguigu.config.config import PromptConfig
from atguigu.config.config import LLMConfig
from atguigu.config.config import MilvusConfig
from langchain.chat_models import init_chat_model
from atguigu.query_process.nodes.node_search_embedding import NodeSearchEmbedding
from atguigu.tool.json_format_tool import json_format
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.logger import logger


class NodeSearchEmbeddingHyde(NodeBase):
    """
    节点功能：HyDE (Hypothetical Document Embedding)
    先让 LLM 生成假设性答案，再对答案进行向量检索，提高召回率。
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_search_embedding_hyde"

    def process(self, state: QueryGraphState):
        """
        节点逻辑
        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """

        logger.info(f"【{self.name}】节点逻辑")
        item_names = state.get("item_names")
        rewritten_query = state.get("rewritten_query")
        if not item_names or not rewritten_query:
            logger.error(f"缺少主体名称或改写后的问题{item_names=},{rewritten_query=}")
            raise ValueError(f"缺少主体名称或改写后的问题{item_names=},{rewritten_query=}")

        llm = init_chat_model(
            model=LLMConfig.item_model,
            model_provider=LLMConfig.model_provider,
            base_url=LLMConfig.base_url,
            api_key=LLMConfig.api_key,
            temperature=LLMConfig.temperature,
        )
        msg = [
            {"role": "system", "content": "你是专业AI助手，严谨简洁，不要编造信息"},
            {"role": "user", "content": PromptConfig.HYDE_PROMPT.format(rewritten_query=rewritten_query)},
        ]

        hybrid_answer = llm.invoke(input=msg).content
        print(f"{hybrid_answer=}")

        hyde_embedding_chunks = NodeSearchEmbedding().search_chunks(hybrid_answer, item_names, source="local")

        # return state
        return {"hyde_embedding_chunks": hyde_embedding_chunks}


if __name__ == "__main__":
    node = NodeSearchEmbeddingHyde()
    init_state = {"item_names": ["兄弟HAK180烫金机"], "rewritten_query": "兄弟HAK180烫金机咋用？"}
    res = node(init_state)
    print(json_format(res))
