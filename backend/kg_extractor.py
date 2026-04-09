import json
import os
import re
import sys
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
            # model="llama-3.3-70b-versatile", 
            model="openai/gpt-oss-120b",
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

    # 用 CLI 參數控制 equipment 過濾，預設處理全部
    # 用法：python kg_extractor.py                 → 全部
    #       python kg_extractor.py --equipment Heidenhain → 只處理 TNC640
    #       python kg_extractor.py --equipment LRT        → 只處理 LRT
    target_equipment = None
    if "--equipment" in sys.argv:
        idx = sys.argv.index("--equipment")
        if idx + 1 < len(sys.argv):
            target_equipment = sys.argv[idx + 1]

    if target_equipment:
        target_manuals = [d for d in manuals if d.get("equipment") == target_equipment]
        print(f"📦 篩選 equipment={target_equipment}，共 {len(target_manuals)} 筆（總計 {len(manuals)} 筆）")
    else:
        target_manuals = manuals
        print(f"📦 處理全部 {len(target_manuals)} 筆手冊資料...")

    # TNCFunction 關鍵字對映表（用於自動建立 PROCEDURE_STEP 邊，含中英文）
    FUNCTION_KEYWORDS = {
        "KinematicsOpt": [
            "kinematicsopt", "kinematics opt", "cycle 48", "opt 48",
            "運動學最佳化", "運動學補償", "旋轉軸補償",
        ],
        "CTC": [
            "ctc", "cycle 990", "circular table compensation", "opt 141",
            "循環表格補償", "轉台補償", "圓形工作台補償",
        ],
        "PAC": [
            "pac", "position adaptive control", "opt 142",
            "位置自適應", "位置調適控制",
        ],
        "LAC": [
            "lac", "load adaptive control", "opt 143",
            "負載自適應", "負載調適控制",
        ],
        "ACC": [
            "acc", "active chatter control", "opt 145",
            "主動震顫控制", "主動顫振控制", "震顫抑制",
        ],
        "M144": ["m144"],
        "TCPM": [
            "tcpm", "m128", "tool center point management",
            "刀尖點控制", "刀尖點管理",
        ],
    }

    # 3. 逐筆處理並寫入 Neo4j
    for doc in target_manuals:
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
                await graph_client.ingest_chunk_causality(
                    doc_id=equipment,
                    chunk_id=chunk_id,
                    cause_text=cause,
                    effect_text=effect,
                    reason=reason
                )
                print(f"  🔗 寫入圖譜: ({cause}) -[{reason}]-> ({effect})")

        # 掃描 chunk 文字，自動建立 TNCFunction -[PROCEDURE_STEP]-> Chunk 邊
        content_lower = content.lower()
        for func_name, keywords in FUNCTION_KEYWORDS.items():
            if any(kw in content_lower for kw in keywords):
                await graph_client.link_function_to_chunk(func_name, chunk_id, step_index=0)
                print(f"  ⚙️  連結 {func_name} → {chunk_id}")

    await graph_client.close()
    print("\n🎉 知識圖譜抽取與寫入全部完成！")

if __name__ == "__main__":
    asyncio.run(main())