from atguigu.config.config import TEST_DIR
import re

md_path_obj = str(TEST_DIR / "demo.md")
print(type(md_path_obj))
with open(md_path_obj, "r", encoding="utf-8") as f:
    md_content = f.read()
md_content.replace("\r\n", "\n").replace("\n\n", "\n")
# 用换行符切割
md_content_list = md_content.split("\n")
# 判定是否处于代码块
is_block = False
signer = None
title_pattern = r"^(`{3,}|~{3,})"

for line in md_content_list:
    line = line.strip()
    matched = re.match(title_pattern, line)
    if matched:
        if not is_block:
            is_block = True
            signer = matched.group(1)
            print(f"{line}")
        elif signer == matched.group(1):
            is_block = False
            signer = None
            print(f"{line}")
