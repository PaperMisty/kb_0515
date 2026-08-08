from pymilvus import MilvusClient
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


if __name__ == "__main__":
    get_milvus_client()
