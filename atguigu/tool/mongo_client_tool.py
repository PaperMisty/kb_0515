from bson import ObjectId
from atguigu.config.config import MongoConfig
from atguigu.tool.logger import logger
import pymongo
import datetime
from rich import print

client = None


# 获取客户端
def get_mongo_client():
    global client
    if not client:
        client = pymongo.MongoClient(host=MongoConfig.mongo_url)
    return client


db = None
collection = None


# 获取表collection
def get_collection():
    global db, collection
    client = get_mongo_client()
    if db is None:  # PyMongo 从设计上禁止将 Database 对象直接进行布尔真值测试,所以用None
        db = client[MongoConfig.mongo_db_name]
    if collection is None:
        collection = db["chat_history"]
        collection.create_index([("session_id", 1), ("ts", -1)])  # 联合索引
    return collection


# 实现CRUD
# 查:最近历史对话记录
def get_recent_history_list(session_id, limit=10) -> list:
    """获取特定会话的最近10条记录

    Args:
        session_id (_type_): 会话id
        limit (int, optional): 按时间降序的前n条. Defaults to 10.

    Returns:
        list:会话内容列表
    """
    collection = get_collection()
    res = collection.find({"session_id": session_id}).sort("ts", -1).limit(limit)
    return list(res)


# 增加or更新数据
def add_or_update_data(data_dict: dict, _id: ObjectId = None) -> str:
    """根据是否有_id传入或data_dict中是否含_id, 决定更改还是增添数据

    Args:
        data_dict (dict): 包含session_id,role,text,rewritten_query,item_names,ts等字段;最好不要包含_id
        _id (optional): 如果更改数据, 传入更改的_id值

    Returns:
        int: 返回操作的数据的_id
    """
    collection = get_collection()
    target_id = _id or data_dict.get("_id")
    session_id = data_dict.get("session_id", "unknown")

    if target_id:
        # 将 _id 从更新数据中剔除，防止触发修改主键 _id 的报错，并用 $set 包裹实现局部更新
        # upsert 保持默认的 False：如果找不到 target_id，直接不更新且不会发生静默新增，保证了业务语义的安全
        update_content = {k: v for k, v in data_dict.items() if k != "_id"}
        collection.update_one({"_id": target_id}, {"$set": update_content})
        logger.info(f"Session {session_id} history updated (ID: {target_id}).")
        return target_id
    else:
        # 显式调用 insert_one 仅用于新增插入，确保新建语义清晰纯粹
        res = collection.insert_one(data_dict)
        logger.info(f"Session {session_id} history added (ID: {res.inserted_id}).")
        return res.inserted_id
    #     return res.inserted_id


# 清除指定会话的数据
def clear_history(session_id):
    collection = get_collection()
    collection.delete_many({"session_id": session_id})
    logger.info(f"Session {session_id} history cleared.")


# 更新指定会话的特定字段
def update_item_name_and_query(session_id, rewritten_query: str, item_names: list[str], limit=10):
    """更新指定会话的特定字段, 用于意图识别后的回写, 默认回写最新10条

    Args:
        session_id (str): 会话id
        rewritten_query (str): 改写后的查询
        item_names (list[str]): 识别的物料名称列表
        limit (int, optional): 默认回写最新10条. Defaults to 10.
    """
    collection = get_collection()
    # 按时间戳排序,取最新limit条
    id_lst = collection.find({"session_id": session_id}).sort("ts", -1).limit(limit)

    collection.update_many(
        {"session_id": session_id, "_id": {"$in": [item["_id"] for item in id_lst]}},
        {"$set": {"rewritten_query": rewritten_query, "item_names": item_names}},
    )
    logger.info(f"Session {session_id} rewritten_query and item_names updated.")


if __name__ == "__main__":
    session_id = "test_001"
    # 测试:清除指定session_id的数据
    clear_history(session_id)

    # 测试:添加数据
    # data_dict = {
    #     "session_id": session_id,
    #     "role": "user",
    #     "text": "咨询下烫金机。",
    #     "rewritten_query": None,
    #     "item_names": None,
    #     "ts": datetime.datetime.now(),
    # }
    # add_or_update_data(data_dict)

    # data_dict = {
    #     "session_id": session_id,
    #     "role": "assistant",
    #     "text": "您好。请问是哪个型号",
    #     "rewritten_query": None,
    #     "item_names": None,
    #     "ts": datetime.datetime.now(),
    # }
    # add_or_update_data(data_dict)

    # data_dict = {
    #     "session_id": session_id,
    #     "role": "user",
    #     "text": "hak180",
    #     "rewritten_query": None,
    #     "item_names": None,
    #     "ts": datetime.datetime.now(),
    # }
    # add_or_update_data(data_dict)

    # data_dict = {
    #     "session_id": session_id,
    #     "role": "assistant",
    #     "text": "具体有什么问题呢？",
    #     "rewritten_query": None,
    #     "item_names": None,
    #     "ts": datetime.datetime.now(),
    # }
    # add_or_update_data(data_dict)

    # 测试: 查询数据
    history_list = get_recent_history_list(session_id)
    for history in history_list:
        print(history)

    # 测试:更新数据
    # data_dict = {
    #     "_id": ObjectId("6a79b96ce49f5d11e1c7fd44"),
    #     "rewritten_query": "查询 hak180 烫金机的问题",
    #     "item_names": ["hak180", "烫金机"],
    # }
    # print(add_or_update_data(data_dict))

    # 测试:更新会话特定字段数据
    # update_item_name_and_query(session_id, "查询 hak180 烫金机的问题_test", ["hak180_test", "烫金机_test"])

"""
================================================================================
【排查记录与重构总结】

在此前的开发和测试中，遇到了以下关键问题及对应的解决方案：

1. Database 对象的布尔值测试报错 (NotImplementedError)
   - 问题：原先使用 `if not db` 和 `if not collection` 来检测全局连接对象。在 PyMongo 中，
     Database 和 Collection 对象不支持直接作布尔测试，否则会抛出 NotImplementedError 异常。
   - 解决：重构为与 None 显式对比，即使用 `if db is None:` 和 `if collection is None:`。

2. 复合（联合）索引设计不合理与拼写 Bug
   - 问题：原先建立的联合索引为 `[("_id", 1), ("ts", -1), ("session_id", 1)]`。由于主键 _id 放在最左侧，
     在执行 find({"session_id": ...}) 时无法命中索引（且 _id 默认自带唯一索引，此项联合设计多余）。
     同时在查询中将 session_id 拼错为了 "sesstion_id"。
   - 解决：根据 MongoDB 的 ESR（等值匹配在前，排序在后）规则，重构索引为更合理的 `[("session_id", 1), ("ts", -1)]`。
     同时在所有的 find、delete 和 update 查询中修正了 session_id 的拼写。

3. upsert无法直接实现自动识别是更新还是插入
   - 问题：原先使用 update_one(..., upsert=True) 来实现自动识别是更新还是插入，但是会产生错误_id传入导致新增数据的bug
                 后来使用 uodate_one({'_id':target_id} if target_id else {}, {...},upsert=False if target_id else True)的模式,发现使用{}这个filter, update此刻会对表进行覆写
   - 解决：重构为 if-else 结构，先判断 _id 是否存在，如果存在则更新，否则插入。

4. 意图更新方法 update_item_name_and_query 的语法嵌套错误
   - 问题：原 collection.update_one 中 $and / $or 错误写成了双大括号的形式（如 {{$or: ...}}），导致 Python 报 SyntaxError。
   - 解决：将其改写为了标准的 PyMongo 字典和列表嵌套表达形式，并采用 update_many 提高意图重写时的覆盖稳健度。

5. 数据库不可进行布尔测试
   - 问题：原先使用 `if not db` 和 `if not collection` 来检测全局连接对象。在 PyMongo 中，
     Database 和 Collection 对象不支持直接作布尔测试，否则会抛出 NotImplementedError 异常。
   - 解决：重构为与 None 显式对比，即使用 `if db is None:` 和 `if collection is None:`。

================================================================================
"""
