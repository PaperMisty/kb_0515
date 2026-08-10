from atguigu.tool.logger import logger
from langgraph.constants import START, END
from atguigu.import_process.nodes.node_entry import NodeEntry
from atguigu.import_process.state import ImportGraphState
from langgraph.graph import StateGraph
from atguigu.import_process.nodes.node_entry import NodeEntry
from atguigu.import_process.nodes.node_pdf_to_md import NodePDFToMD
from atguigu.import_process.nodes.node_md_img import NodeMDImg
from atguigu.import_process.nodes.node_document_split import NodeDocumentSplit
from atguigu.import_process.nodes.node_item_name_recognize import (
    NodeItemNameRecognition,
)
from atguigu.import_process.nodes.node_bge_embedding import NodeBGEEmbedding
from atguigu.import_process.nodes.node_import_milvus import NodeImportMilvus
from atguigu.tool.json_format_tool import json_format
from atguigu.config.config import RAW_DIR, OUTPUT_DIR


class GraphRunner:
    def __init__(self):
        self.builder = StateGraph(ImportGraphState)
        self.add_nodes()
        self.add_edges()
        self.graph = None

    def add_nodes(self):
        self.builder.add_node(NodeEntry.name, NodeEntry())
        self.builder.add_node(NodeMDImg.name, NodeMDImg())
        self.builder.add_node(NodePDFToMD.name, NodePDFToMD())
        self.builder.add_node(NodeDocumentSplit.name, NodeDocumentSplit())
        self.builder.add_node(NodeItemNameRecognition.name, NodeItemNameRecognition())
        self.builder.add_node(NodeBGEEmbedding.name, NodeBGEEmbedding())
        self.builder.add_node(NodeImportMilvus.name, NodeImportMilvus())

    # 路由初始节点(文件判断路由)
    def after_node_entry(self, state: ImportGraphState):
        is_md = state.get("is_md_read_enabled", False)
        is_pdf = state.get("is_pdf_read_enabled", False)
        if is_md:
            return NodeMDImg.name
        elif is_pdf:
            return NodePDFToMD.name
        else:
            raise ValueError("is_md_read_enabled和is_pdf_read_enabled不能同时为False")

    def add_edges(self):
        self.builder.add_edge(START, NodeEntry.name)
        self.builder.add_conditional_edges(NodeEntry.name, self.after_node_entry)
        self.builder.add_edge(NodePDFToMD.name, NodeMDImg.name)
        self.builder.add_edge(NodeMDImg.name, NodeDocumentSplit.name)
        self.builder.add_edge(NodeDocumentSplit.name, NodeItemNameRecognition.name)
        self.builder.add_edge(NodeItemNameRecognition.name, NodeBGEEmbedding.name)
        self.builder.add_edge(NodeBGEEmbedding.name, NodeImportMilvus.name)
        self.builder.add_edge(NodeItemNameRecognition.name, NodeBGEEmbedding.name)
        self.builder.add_edge(NodeBGEEmbedding.name, END)

    def run(self, init_state):
        # 如果有缓存, 就不再编译了,避免时间资源消耗(懒加载)
        if not self.graph:
            self.graph = self.builder.compile()
        res = self.graph.invoke(input=init_state)
        return res

    @classmethod
    def create_and_run(cls, state):
        return cls().run(state)


class MyCustomRunner(GraphRunner):
    # 重写了 run 方法以提供自定义逻辑
    def run(self, state):
        print("执行自定义 Runner")
        return super().run(state)


if __name__ == "__main__":

    init_state = {
        "local_file_path": str(RAW_DIR / "hak180产品安全手册.pdf"),
        "local_dir": str(OUTPUT_DIR),
    }
    res = GraphRunner.create_and_run(init_state)
    logger.info(json_format(res))
