# atguigu/query_process/nodes/node_web_search_mcp.py

import asyncio
from atguigu.config.config import LLMConfig
from atguigu.tool.json_format_tool import json_format
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.logger import logger
from rich import print
import json
from atguigu.config.config import MCPConfig
from agents.mcp import MCPServerStreamableHttp


class NodeWebSearchMcp(NodeBase):
    """
    节点功能，调用外部搜索引擎补充信息
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_web_search_mcp"

    def process(self, state: QueryGraphState):
        """
        用MCP工具搜索重写问题的网络答案,结构化输出
        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """

        logger.info(f"【{self.name}】节点逻辑")
        rewritten_query = state.get("rewritten_query")
        if not rewritten_query:
            logger.error(f"【{self.name}】节点的处理数据为空")
            raise ValueError(f"【{self.name}】节点的处理数据为空")

        web_search_docs = asyncio.run(self.mcp_run(rewritten_query))
        if not web_search_docs:
            logger.warning(f"搜索结果为空")
            raise ValueError("搜索结果为空")
        # 取核心内容
        web_search_docs = json.loads(web_search_docs.content[0].text).get("pages")
        return {
            "web_search_docs": [
                {
                    "title": item.get("title"),
                    "content": item.get("snippet"),
                    "url": item.get("url"),
                    "source": "web",
                }
                for item in web_search_docs
            ]
        }

    async def mcp_run(self, query, limit=10) -> None:
        token = LLMConfig.api_key
        url = MCPConfig.mcp_dashscope_base_url
        async with MCPServerStreamableHttp(
            name="Streamable HTTP Python Server",
            params={
                "url": url,
                "headers": {"Authorization": f"Bearer {token}"},
                "timeout": 10,
            },
            cache_tools_list=True,
            max_retry_attempts=3,
            client_session_timeout_seconds=30,
        ) as server:
            result = await server.call_tool("bailian_web_search", arguments={"query": query, "count": limit})
            return result


if __name__ == "__main__":

    init_state = {"rewritten_query": "关于BrotherHAK180烫金机如何使用"}

    # 执行节点的业务调用
    node_web_search_mcp = NodeWebSearchMcp()
    result = node_web_search_mcp(init_state)
    logger.info(json_format(result))
