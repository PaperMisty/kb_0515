from requests import HTTPError
from atguigu.config.config import LLMConfig
from atguigu.config.config import ReRankerConfig
import dashscope
from http import HTTPStatus
from atguigu.tool.logger import logger

# 以下为华北2（北京）地域的配置，调用时请将{WorkspaceId}替换为真实的业务空间ID，各地域的配置不同。
dashscope.base_http_api_url = ReRankerConfig.reranker_base_url
dashscope.api_key = LLMConfig.api_key


def text_rerank(query: str, documents: list[str], top_n: int = 10) -> str:
    """
    文本重排
    :param query: 查询文本
    :param documents: 文档列表
    :param top_n: 返回的文档数量
    :return: 重排后的文档列表
    """
    # 过滤可能存在的 None 或空字符串，防止百炼 API 报错
    valid_documents = [doc for doc in documents if doc and isinstance(doc, str)]
    if not valid_documents:
        logger.warning("没有有效的文档可以进行重排序")
        return []
    
    # 确保 top_n 不超过有效文档数量
    actual_top_n = min(top_n, len(valid_documents))

    resp = dashscope.TextReRank.call(
        model="qwen3-vl-rerank",
        query=query,
        documents=valid_documents,
        top_n=actual_top_n,
        return_documents=False,  # 是否返回原文档; 没有必要,省token
        instruct="Given a web search query, retrieve relevant passages that answer the query.",
    )
    if resp.status_code == HTTPStatus.OK:
        result = resp.output.results
        return [{"index": item.index, "score": item.relevance_score} for item in result]
    else:
        # 记录详细日志以便排查问题
        logger.error(f"重排序API请求失败: status_code={resp.status_code}, code={resp.code}, message={resp.message}, documents_count={len(documents)}")
        raise Exception(f"重排序请求异常,状态码: {resp.status_code}, 错误信息: {resp.message}")


if __name__ == "__main__":
    print(
        text_rerank(
            query="关于hak180烫金机如何使用？",
            documents=[
                "HAK 180 烫金机\n\n产品安全手册（简体中文）\n\n感谢您购买 HAK 180 烫金机。\n\n在使用本设备之前，请先阅读本手册",
                "HAK 180 烫金机\n\为设备选择一个安全的位置\n\n![确保设备放置平稳，远离边缘，使用时勿将手伸入纸张边缘，搬运需双手托底，避免跌落造成伤害或损坏。",
                "HAK 180 烫金机\n\设备\n\n•\t请勿拆解本设备。拆解本设备可能会导致火灾或触电。",
                "HAK 180 烫金机 是一款工业设备, 经常用于xxx ",
            ],
        )
    )
