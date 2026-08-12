# atguigu/query_process/nodes/node_search_embedding.py

from atguigu.tool.json_format_tool import json_format
from atguigu.tool.milvus_client_tool import weighted_hybrid_search
from atguigu.config.config import MilvusConfig
from atguigu.tool.milvus_client_tool import create_reqs
from atguigu.tool.bgem3_client_tool import get_bgem3_embedding
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.logger import logger
import json
from rich import print


class NodeSearchEmbedding(NodeBase):
    """
    节点功能：基于已确认主体名+改写后的用户问题，执行Milvus向量数据库混合检索
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_search_embedding"

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
        embedding_chunks = self.search_chunks(rewritten_query, item_names, source="local")
        return {"embedding_chunks": embedding_chunks}

    def search_chunks(self, query, item_names, source, limit=10):
        # 将重写问题转换成embedding向量
        vecs = get_bgem3_embedding([query])
        # 标量搜索依然很重要, 不过expr逐渐推荐用filter代替了
        expr = f"item_name in {json.dumps(item_names, ensure_ascii=False)}"  # json.dumps 自身已具备完美的自动转义机制
        reqs = create_reqs(
            dense_data=vecs["dense"][0],
            sparse_data=vecs["sparse"][0],
            dense_ann_field="dense",
            sparse_ann_field="sparse",
            expr=expr,
        )
        collection_name = MilvusConfig.chunks_collection
        res = weighted_hybrid_search(
            collection_name=collection_name,
            reqs=reqs,
            limit=limit,
            output_fields=["id", "file_title", "section_title", "chunk_content", "item_name"],
        )
        # print(json_format(res))

        # 组装检索出的chunk信息
        embedding_chunks = []
        for search_result in res[0]:
            embedding_chunks.append({**search_result["entity"], "score": search_result["distance"], "source": source})
        return embedding_chunks


if __name__ == "__main__":
    node = NodeSearchEmbedding()
    init_state = {"item_names": ["兄弟HAK180烫金机"], "rewritten_query": "兄弟HAK180烫金机咋用？"}
    res = node(init_state)
    print(json_format(res))
