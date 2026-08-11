from pymilvus import WeightedRanker
from pymilvus import MilvusClient, AnnSearchRequest
from atguigu.config.config import MilvusConfig
from atguigu.tool.logger import logger


client = None


def get_milvus_client() -> MilvusClient:
    """获取MilvusClient实例"""
    global client
    if not client:
        try:
            client = MilvusClient(uri=MilvusConfig.milvus_url)
            logger.info("Milvus连接成功")
        except Exception as e:
            logger.error(f"Milvus连接失败: {e}")
            raise e
    return client


# 创建混合检索的两个 ANN Search Request
def create_reqs(
    dense_data,
    sparse_data,
    dense_ann_field=None,
    sparse_ann_field=None,
    dense_params=None,
    sparse_params=None,
    limit=10,
    expr=None,
) -> list:
    """
    创建混合检索的ANN Search Request

    Args:
        dense_data (list): 稠密向量数据
        sparse_data (list): 稀疏向量数据
        dense_ann_field (str, optional): 稠密向量搜索字段名. Defaults to None.
        sparse_ann_field (str, optional): 稀疏向量搜索字段名. Defaults to None.
        dense_params (dict, optional): 稠密向量参数. Defaults to None.
        sparse_params (dict, optional): 稀疏向量参数. Defaults to None.
        limit (int, optional): 返回结果数量. Defaults to 10.
        expr (str, optional): 标量搜索过滤表达式. Defaults to None.

    Returns:
        list: 混合检索请求
    """
    if dense_params is None:
        dense_params = {"metric_type": "COSINE"}
    if sparse_params is None:
        sparse_params = {"metric_type": "IP"}
    dense_ann_req = AnnSearchRequest(
        data=dense_data, anns_field=dense_ann_field, param=dense_params, limit=limit, expr=expr
    )
    sparse_ann_req = AnnSearchRequest(
        data=sparse_data, anns_field=sparse_ann_field, param=sparse_params, limit=limit, expr=expr
    )
    return [dense_ann_req, sparse_ann_req]


# 混合检索搜索
def hybrid_search(
    collection_name,
    reqs,
    ranker=[0.5, 0.5],
    limit=10,
    output_fields=None,
) -> list:
    """混合检索搜索, 采用分数归一化并加权方式进行融合排序

    Args:
        collection_name (str): 集合名称
        reqs (list): 混合检索请求
        ranker (list, optional): 混合检索权重. Defaults to [0.5, 0.5].
        limit (int, optional): 返回结果数量. Defaults to 10.
        output_fields (list, optional): 返回结果字段. Defaults to None.

    Returns:
        list: 混合检索结果
    """
    ranker = WeightedRanker(*ranker, norm_score=True)
    client = get_milvus_client()
    result = client.hybrid_search(
        collection_name=collection_name, reqs=reqs, ranker=ranker, limit=limit, output_fields=output_fields
    )
    logger.info(f"混合检索结果: {result}")
    return result


if __name__ == "__main__":
    get_milvus_client()
