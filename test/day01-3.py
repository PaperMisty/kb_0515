# 1.导包
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
load_dotenv()

# 2. 从环境变量读取硅基流动的配置
# 注意：在 .env 中配置了 siliconflow_dsv4 和 siliconflow_url
silicon_key = os.getenv("siliconflow_dsv4")
silicon_url = os.getenv("siliconflow_url")

# 3. 初始化 LangChain ChatOpenAI 模型（硅基流动接口兼容 OpenAI 规范）
llm = ChatOpenAI(
    api_key=silicon_key,
    base_url=silicon_url,
    model="deepseek-ai/DeepSeek-V3"  # 也可以换成 'deepseek-ai/DeepSeek-R1', 'Qwen/Qwen2.5-7B-Instruct' 等
)

# msg = [{"role":"system","content":"你是一个{role}"},
#     {"role":"user","content":"{content}"}]

# cpt = ChatPromptTemplate.invoke({"role":"幽默的玩梗者","content":"死神爱吃苹果"})
# resp = llm.invoke(input=msg,config=cpt)
# print(resp.content)
from pydantic import BaseModel
class Star(BaseModel):
  name:str
  age:int
  desc:str

class StarList(BaseModel):
  stars:list[Star]
# # 1.JsonOutputParser解析输出
jop = JsonOutputParser(pydantic_object=StarList)
msg = [{"role":"system","content":jop.get_format_instructions()},
    {"role":"user","content":"输出三个科学家信息"}]
# response = llm.invoke(input=msg)
# print(jop.parse(response.content))
# # 2.class形式输出

from langchain_community.callbacks.manager import get_openai_callback

new_llm = llm.with_structured_output(schema=StarList)

with get_openai_callback() as cb:
    response = new_llm.invoke(input=msg)
    print(response)
    print("*" * 40)
    print("Token 消耗详情:")
    print(f"总 Token: {cb.total_tokens}")
    print(f"输入 Token: {cb.prompt_tokens}")
    print(f"输出 Token: {cb.completion_tokens}")
    print("*" * 40)




# # # 1.以json形式返回
# jop = JsonOutputParser(pydantic_object=StarList)
# msg = [{'role':'system','content':jop.get_format_instructions()},
#     {'role':'user','content':'请输出中国三个女明星'}]
# resp = llm.invoke(input=msg)
# # print(resp,type(resp))
# data_json = jop.parse(resp.content)
# for k,v in data_json.items():
#   print(k,v)

# # # 2.以类的形式返回
# # new_llm = llm.with_structured_output(schema=StarList) # 给llm加结构化输出方法
# # msg = '举例中国三个漂亮女明星'
# # resp = new_llm.invoke(input=msg)
# # print(resp,type(resp))
# # for star in resp.stars:
# #   print(star.name,star.age,sep=' ')