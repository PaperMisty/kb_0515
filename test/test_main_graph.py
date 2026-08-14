import pytest
import importlib

# 提示：因为 main-graph.py 含有短横线 -，Python 的标准 import 语法会将其识别为减号。
# 因此我们在这里使用 importlib 动态载入它。在实际项目中，强烈建议将 main-graph.py 重命名为 main_graph.py。
main_graph_module = importlib.import_module("atguigu.import_process.main_graph")
GraphRunner = main_graph_module.GraphRunner

from atguigu.import_process.nodes.node_md_img import NodeMDImg
from atguigu.import_process.nodes.node_pdf_to_md import NodePDFToMD


def test_after_node_entry_md():
    """
    单元测试：验证当 md 读取被启用时，流转路由是否能正确指向 node_md_img
    """
    runner = GraphRunner()
    state = {"is_md_read_enabled": True, "is_pdf_read_enabled": False}
    next_node = runner.after_node_entry(state)
    assert next_node == NodeMDImg.name


def test_after_node_entry_pdf():
    """
    单元测试：验证当 pdf 读取被启用时，流转路由是否能正确指向 node_pdf_to_md
    """
    runner = GraphRunner()
    state = {"is_md_read_enabled": False, "is_pdf_read_enabled": True}
    next_node = runner.after_node_entry(state)
    assert next_node == NodePDFToMD.name


def test_after_node_entry_error():
    """
    单元测试：验证当 md, pdf 和 ppt 均未被启用时，是否如期抛出 ValueError 异常
    """
    runner = GraphRunner()
    state = {"is_md_read_enabled": False, "is_pdf_read_enabled": False, "is_ppt_read_enabled": False}
    # 验证是否会抛出指定错误，并捕获错误信息进行断言
    with pytest.raises(ValueError) as excinfo:
        runner.after_node_entry(state)

    assert "is_md_read_enabled、is_pdf_read_enabled和is_ppt_read_enabled不能同时为False" in str(
        excinfo.value
    )


def test_nodes_are_registered():
    """
    结构测试：验证图的构建器中是否成功注册了所有必须的逻辑节点
    """
    runner = GraphRunner()
    registered_nodes = runner.builder.nodes.keys()

    expected_nodes = [
        "node_entry",
        "node_md_img",
        "node_pdf_to_md",
        "node_ppt_to_md",
        "node_document_split",
        "node_item_name_recognition",
        "node_bge_embedding",
        "node_import_milvus",
    ]

    for node_name in expected_nodes:
        assert node_name in registered_nodes


def test_after_node_entry_ppt():
    """
    单元测试：验证当 ppt 读取被启用时，流转路由是否能正确指向 node_ppt_to_md
    """
    runner = GraphRunner()
    state = {"is_md_read_enabled": False, "is_pdf_read_enabled": False, "is_ppt_read_enabled": True}
    next_node = runner.after_node_entry(state)
    assert next_node == "node_ppt_to_md"
