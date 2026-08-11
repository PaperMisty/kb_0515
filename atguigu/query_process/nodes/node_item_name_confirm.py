# atguigu/query_process/nodes/node_item_name_confirm.py
from atguigu.tool.mongo_client_tool import update_item_name_and_query
from atguigu.tool.mongo_client_tool import clear_history
from atguigu.config.config import MilvusConfig
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.milvus_client_tool import weighted_hybrid_search
from atguigu.tool.milvus_client_tool import create_reqs
from atguigu.tool.bgem3_client_tool import get_bgem3_embedding
from atguigu.config.config import LLMConfig, PromptConfig
from langchain.chat_models import init_chat_model
from atguigu.tool.mongo_client_tool import get_recent_history_list
from atguigu.tool.mongo_client_tool import add_or_update_data
import json, time
from rich import print
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.logger import logger


class NodeItemNameConfirm(NodeBase):
    """
    节点功能：确认用户问题中的核心商品名称。
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_item_name_confirm"

    def process(self, state: QueryGraphState):
        """
        节点逻辑
        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """

        logger.info(f"【{self.name}】节点逻辑")
        # 取对话id
        session_id = state.get("session_id", "")
        if not session_id:
            logger.error("session_id 为空")
            raise ValueError("session_id 为空")

        # 取用户的问题
        original_query = state.get("original_query", "")
        if not original_query:
            logger.error("用户问题为空")
            raise ValueError("用户问题为空")

        # 最新对话写入mongodb
        message_id = add_or_update_data(
            {
                "session_id": session_id,
                "role": "user",
                "text": original_query,
                "rewritten_query": None,
                "item_names": None,
                "ts": time.time(),
            }
        )
        logger.info(f"最新对话写入mongodb,message_id: {message_id}")

        # ===意图识别===
        # 取最近历史对话记录
        recent_history_list = get_recent_history_list(session_id, limit=3)
        if not recent_history_list:
            logger.warning("最近历史对话记录为空")
            return state

        # 将最近历史对话记录格式化为字符串
        context = "\n".join([f"{item['role']}: {item['text']}" for item in recent_history_list])

        llm = init_chat_model(
            model=LLMConfig.item_model,
            model_provider=LLMConfig.model_provider,
            base_url=LLMConfig.base_url,
            api_key=LLMConfig.api_key,
        )

        # 让LLM提取意图内容
        msg = [
            {"role": "system", "content": PromptConfig.ITEM_NAME_EXTRACT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": PromptConfig.ITEM_NAME_EXTRACT_TEMPLATE.format(
                    history_text=context, original_query=original_query
                ),
            },
        ]

        response = llm.invoke(msg)
        content = response.content

        # 如果返回的json存在垃圾字符,消除
        if content.startswith("```json"):
            content = content[6:-3]
        if not content.startswith("{"):
            logger.error(f"llm返回结果不合法:{content}")
            raise ValueError(f"llm返回结果不合法:{content}")
        # 将llm的返回结果清洗和解析为字典
        content_json = json.loads(content)

        # - 这里没有采用default [], 是因为可能存在item_names this key,但是key无内容,导致返回值不是列表[], 而是空字符串了
        rewritten_query = content_json.get("rewritten_query", "")
        item_names = content_json.get("item_names", "")

        # 核心对齐控制变量初始化，防御 item_names 为空时发生 NameError/UnboundLocalError
        final_item_lst = []
        choosed_item_lst = []
        optional_item_lst = []
        answer = ""

        # - 防御没有提取到意图重写内容
        if not rewritten_query:
            logger.warning("未提取到意图重写内容，直接使用原查询")
            rewritten_query = original_query

        # - 防御没有提取到商品名称
        if not item_names:
            logger.warning("未提取到商品名称")
            content_json["item_names"] = []
        else:
            # 去除item_names中的空格,以及换行符,制表符
            item_names = [item.replace(" ", "").replace("\n", "").replace("\t", "") for item in item_names]
            content_json["item_names"] = item_names

            # ===根据LLM提取的主体,依次去数据库检索相关主体===
            # 取item_names的向量化
            vecs = get_bgem3_embedding(item_names)
            for idx, item_name in enumerate(item_names):
                # 取稀疏和稠密向量的检索请求
                reqs = create_reqs(
                    dense_data=vecs["dense"][idx],
                    sparse_data=vecs["sparse"][idx],
                    dense_ann_field="dense",
                    sparse_ann_field="sparse",
                    limit=10,
                )
                # 从milvus中混合检索最相关的向量id
                result = weighted_hybrid_search(
                    collection_name=MilvusConfig.item_name_collection,
                    reqs=reqs,
                    ranker=[0.8, 0.2],
                    limit=10,
                    output_fields=["item_name"],  # milvus的item_name是字符串 ,mongo的item_names才是列表
                )
                # print(json_format(result))

                # ===取出数据库相关主体的信息,与用户意图商品名称对齐===
                if not result:
                    logger.warning(f"商品[{item_name}]在数据库中没有搜索到相关内容")
                    continue
                else:
                    searched_item_lst = result[0]
                    for item_info in searched_item_lst:
                        # 混合检索返回的结果中，商品名称位于 entity 字典中，需先通过 entity 获取
                        item_name_val = item_info.get("entity", {}).get("item_name")
                        if not item_name_val:
                            continue

                        distance = item_info.get("distance", 0.0)  # 这里的distance实际是cos余弦值[-1,1]
                        if distance >= 0.85:
                            choosed_item_lst.append(item_name_val)
                        elif 0.6 < distance < 0.85:
                            optional_item_lst.append(item_name_val)

            # ===根据对齐情况, 决定如何更新历史对话===
            logger.info(f"choosed_item_lst: {choosed_item_lst}, optional_item_lst: {optional_item_lst}")
            if choosed_item_lst:
                final_item_lst = choosed_item_lst
            elif optional_item_lst:
                # 修复 optional_item_lst 元素为字符串时的拼接与格式错误
                tmp = "\t".join(optional_item_lst)
                answer = f"您想咨询的是以下哪一个? \n: {tmp} "
            else:
                answer = "数据库中未找到相关内容, 请重新输入"

            # 如果需要助手做出确认/警告回复，将回复内容新增到对话历史中，并更新 message_id
            if answer:
                data_dict = {
                    "session_id": session_id,
                    "role": "assistant",
                    "text": answer,
                    "rewritten_query": rewritten_query,
                    "item_names": final_item_lst,
                    "ts": time.time(),
                }
                message_id = add_or_update_data(data_dict)
                logger.info(f"助手回复写入mongodb,message_id: {message_id}")

            # 无论置信度高低（只要提取了意图），都对最近的历史记录回写 rewritten_query 与已对齐的商品名称列表
            # 这样保证多轮对话上下文的一致性
            update_item_name_and_query(session_id, rewritten_query, final_item_lst)
            logger.info(f"回写主体信息: rewritten_query: {rewritten_query}, item_names: {final_item_lst}")

        return {
            "message_id": message_id,
            "original_query": original_query,
            "rewritten_query": rewritten_query,
            "item_names": final_item_lst,
        }


if __name__ == "__main__":
    session_id = "test_001"
    # 清理记录
    clear_history(session_id)
    # 添加数据
    data_dict = {
        "session_id": session_id,
        "role": "user",
        "text": "咨询下烫金机。",
        "rewritten_query": None,
        "item_names": None,
        "ts": time.time(),
    }
    add_or_update_data(data_dict)

    data_dict = {
        "session_id": session_id,
        "role": "assistant",
        "text": "您好。请问是哪个型号",
        "rewritten_query": None,
        "item_names": None,
        "ts": time.time(),
    }
    add_or_update_data(data_dict)

    data_dict = {
        "session_id": session_id,
        "role": "user",
        "text": "hak180",
        "rewritten_query": None,
        "item_names": None,
        "ts": time.time(),
    }
    add_or_update_data(data_dict)

    data_dict = {
        "session_id": session_id,
        "role": "assistant",
        "text": "具体有什么问题呢？",
        "rewritten_query": None,
        "item_names": None,
        "ts": time.time(),
    }
    add_or_update_data(data_dict)
    # 初始化图状态
    init_state = {"session_id": "test_001", "original_query": "咋用？"}

    # 创建节点对象
    node_item_name_confirm = NodeItemNameConfirm()
    # 执行节点的单元测试
    result = node_item_name_confirm(init_state)
    # 将返回的图状态进行json序列化
    # logger.info(json_format(result))
    print(result)
