from pathlib import Path

img_context = {
    "img_path": r'"D:\desktop\Markdown笔记\机器学习\langchain_tutorial\teacher_rag\kb_0515\.env.example"'
}
print(__file__, type(__file__))
new_path = Path(__file__).parent / (Path(__file__).stem + "_new.md")
# new_path = Path(img_context.get("img_path")).stem / "_new.md"
# print(new_path)


print(new_path, type(new_path))
