import json
import os
import re
import asyncio
from groq import AsyncGroq  # 假設你目前系統使用的是 Groq API
from dotenv import load_dotenv

# 引入你剛才設定好的 Neo4j Client
from bk4.neo4j_client import CausalGraphClient

load_dotenv()

# 初始化 Groq Client (請確認你的 .env 中有 GROQ_API_KEY)
# 若你使用其他 LLM，請自行替換此處的呼叫邏輯
client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

# 定義萃取 Prompt
EXTRACTION_PROMPT = """你是一個精準的工業知識萃取系統。
請閱讀以下的工具機操作手冊段落，並從中萃取出「動作與結果」或「先後步驟」的因果關聯。

你【必須】嚴格輸出 JSON Array 格式，不要包含任何其他文字或 Markdown 標記。
JSON 格式範例：
[
  {
    "cause": "將球透鏡模組鎖固於工作台中心",
    "effect": "完成C軸旋轉中心定位",
    "reason": "設備架設需求"
  },
  {
    "cause": "按下 [程式編輯與測試] 模式鍵",
    "effect": "控制器進入測試模式",
    "reason": "模式切換"
  }
]

請處理以下文本：
"""

async def extract_causality(text: str) -> list:
    """呼叫 LLM 進行因果關係萃取 (具備 Regex 強制擷取與防呆機制)"""
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[
                {"role": "system", "content": "You are a data extraction bot. You must output ONLY a valid JSON array. No explanations."},
                {"role": "user", "content": f"{EXTRACTION_PROMPT}\n{text}"}
            ],
            temperature=0.0  # 將溫度降到 0，讓格式最穩定
        )
        
        content = response.choices[0].message.content.strip()
        
        # 使用正則表達式暴力擷取 [ ] 之間的內容 (包含換行符號)
        match = re.search(r'\[.*\]', content, re.DOTALL)
        
        if match:
            json_str = match.group(0)
            return json.loads(json_str)
        else:
            print(f"  ⚠️ LLM 沒有輸出陣列格式，略過此段。原始輸出：\n{content}")
            return []
            
    except json.JSONDecodeError as e:
        # 如果還是報錯，就把 LLM 亂吐的原文印出來看是哪裡壞掉
        print(f"  ❌ JSON 解析失敗: {e}\n  🚨 嫌犯原文:\n{content}")
        return []
    except Exception as e:
        print(f"  ❌ API 呼叫失敗: {e}")
        return []

async def main():
    # 1. 初始化 Neo4j Client
    graph_client = CausalGraphClient()
    
    # 2. 讀取我們先前建立的 manuals.json
    json_path = os.path.join(os.path.dirname(__file__), "rag_data", "manuals.json")
    if not os.path.exists(json_path):
        print("找不到 manuals.json，請確認路徑。")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        manuals = json.load(f)

    print(f"📦 開始處理 {len(manuals)} 筆手冊資料...")

    # 3. 逐筆處理並寫入 Neo4j
    for doc in manuals:
        chunk_id = doc["id"]
        equipment = doc["equipment"]
        content = doc["content"]
        
        print(f"\n🧠 正在萃取 [{equipment}] {chunk_id} ...")
        
        # 呼叫 LLM 萃取因果關係
        extracted_relations = await extract_causality(content)
        
        for relation in extracted_relations:
            cause = relation.get("cause", "")
            effect = relation.get("effect", "")
            reason = relation.get("reason", "")
            
            if cause and effect:
                # 呼叫你實習時寫好的神級方法：綁定 Chunk 與因果鏈
                await graph_client.ingest_chunk_causality(
                    doc_id=equipment,
                    chunk_id=chunk_id,
                    cause_text=cause,
                    effect_text=effect,
                    reason=reason
                )
                print(f"  🔗 寫入圖譜: ({cause}) -[{reason}]-> ({effect})")

    await graph_client.close()
    print("\n🎉 知識圖譜抽取與寫入全部完成！")

if __name__ == "__main__":
    asyncio.run(main())