import re

s = """![](D:/desktop/sth/sth.jpg)
xxx
yyy
![](D:/desktop/demo/sth.jpg)
zzz
![](D:/desktop/sth/sth.jpg)
111
"""
img_name = "D:/desktop/sth/sth.jpg"
pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(img_name) + r"\)")
# 使用 re.finditer 查找所有匹配项
matches = list(re.finditer(pattern, s))
print(f"共找到 {len(matches)} 个匹配项：")
for i, match in enumerate(matches, 1):
    print(f"匹配 {i}: {match.group()}，位置: {match.span()}")
