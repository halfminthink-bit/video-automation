from openai import OpenAI
import os
k = os.getenv("OPENAI_API_KEY") or ""
print("len:", len(k), "repr_head:", repr(k[:12]))
client = OpenAI(api_key=k.strip())  # 前後の空白/改行を除去
resp = client.models.list()
print("OK models:", len(resp.data))
