# test/test_ppt_pipeline.py
import importlib
import sys
from pathlib import Path

# 添加当前工作目录到路径
sys.path.insert(0, str(Path(__file__).parents[1]))

from atguigu.config.config import RAW_DIR, OUTPUT_DIR
from atguigu.tool.logger import logger
from atguigu.tool.json_format_tool import json_format

# 动态载入 main_graph.py
main_graph_module = importlib.import_module("atguigu.import_process.main_graph")
GraphRunner = main_graph_module.GraphRunner

def run_ppt_test():
    # 使用 RAW_DIR 下的其中一个 PPTX 文件进行全链路集成测试
    test_ppt_path = RAW_DIR / "【第一版】DK2509-10前后盘包装方案及捆包成本检讨.pptx"
    
    if not test_ppt_path.exists():
        logger.error(f"测试文件不存在: {test_ppt_path}")
        return

    init_state = {
        "local_file_path": str(test_ppt_path),
        "local_dir": str(OUTPUT_DIR),
    }

    logger.info(f"开始运行 PPT 集成测试，文件: {test_ppt_path.name}")
    try:
        res = GraphRunner.create_and_run(init_state)
        logger.info("PPT 集成测试成功完成！")
        
        # 验证输出的 chunk_dict_list 结构
        chunks = res.get("chunk_dict_list", [])
        logger.info(f"共生成了 {len(chunks)} 个分片。")
        for i, chunk in enumerate(chunks[:5], 1):
            logger.info(f"分片 {i} 详情:\n{json_format(chunk)}\n{'-'*30}")
            
    except Exception as e:
        logger.error(f"运行 PPT 导入图流转时发生错误: {e}", exc_info=True)

if __name__ == "__main__":
    run_ppt_test()
