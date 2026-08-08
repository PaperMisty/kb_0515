from atguigu.config.config import OUTPUT_DIR
import json
from rich import print

with open(OUTPUT_DIR / "hak180产品安全手册" / "hak180产品安全手册_new_chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

for idx, chunk in enumerate(chunks):
    print(chunk.items(), type(chunk.items()))
