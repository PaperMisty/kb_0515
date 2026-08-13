import sys
from pathlib import Path

# 将项目根目录添加到 python 搜索路径
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from pymilvus import DataType
from atguigu.tool.milvus_client_tool import get_milvus_client
from atguigu.tool.logger import logger


def run_l2_test():
    collection_name = "test_l2_demo"
    client = get_milvus_client()

    # 1. 如果集合已存在，先删除
    if client.has_collection(collection_name=collection_name):
        logger.info(f"集合 {collection_name} 已存在，正在删除...")
        client.drop_collection(collection_name=collection_name)

    # 2. 创建 schema
    logger.info("创建 Schema...")
    schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
    schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=2)

    # 3. 创建索引参数，指定使用 L2 距离
    logger.info("准备索引参数 (metric_type='L2')...")
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_name="vector_index",
        index_type="FLAT",  # FLAT 索引适合小数据集且精度最高
        metric_type="L2",
    )

    # 4. 创建 collection
    logger.info(f"创建集合 {collection_name}...")
    client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)

    # 5. 插入测试数据
    data = [
        {"id": 1, "vector": [1.0, 1.0]},
        {"id": 2, "vector": [4.0, 5.0]},  # 与 (1.0, 1.0) 的 L2 平方距离为 3^2 + 4^2 = 25
        {"id": 3, "vector": [10.0, 10.0]},  # 与 (1.0, 1.0) 的 L2 平方距离为 9^2 + 9^2 = 162
    ]
    logger.info(f"插入测试向量: {data}")
    client.insert(collection_name=collection_name, data=data)

    # 6. 进行检索测试
    # 测试向量 1: 完全重合的向量 [1.0, 1.0]
    query_vector_1 = [1.0, 1.0]
    logger.info(f"检索测试 1: 查询向量为与库中完全相同的 {query_vector_1}")
    res_1 = client.search(
        collection_name=collection_name,
        data=[query_vector_1],
        limit=3,
        anns_field="vector",
        search_params={"metric_type": "L2"},
        output_fields=["id"],
    )

    print("\n--- 检索 1 结果 ---")
    for hits in res_1:
        for hit in hits:
            print(f"ID: {hit['entity']['id']}, 距离 (distance): {hit['distance']}")

    # 测试向量 2: 非常遥远的向量 [100.0, 100.0]
    query_vector_2 = [100.0, 100.0]
    logger.info(f"检索测试 2: 查询一个非常远的向量 {query_vector_2}")
    res_2 = client.search(
        collection_name=collection_name,
        data=[query_vector_2],
        limit=3,
        anns_field="vector",
        search_params={"metric_type": "L2"},
        output_fields=["id"],
    )

    print("\n--- 检索 2 结果 ---")
    for hits in res_2:
        for hit in hits:
            print(f"ID: {hit['entity']['id']}, 距离 (distance): {hit['distance']}")

    # # 7. 清理集合
    # logger.info(f"正在删除临时集合 {collection_name}...")
    # client.drop_collection(collection_name=collection_name)
    # logger.info("测试完成并清理完毕。")


if __name__ == "__main__":
    run_l2_test()
