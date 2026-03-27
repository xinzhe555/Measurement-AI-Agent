import json
import os
import faiss
import numpy as np
import asyncio
from sentence_transformers import SentenceTransformer
# 引入我們剛建好的 Neo4j Client
from bk4.neo4j_client import CausalGraphClient

class ManualRetriever:
    def __init__(self, data_dir="rag_data"):
        # 1. 初始化 FAISS 向量資料庫
        base_dir = os.path.join(os.path.dirname(__file__), '..', data_dir)
        self.json_path = os.path.join(base_dir, "manuals.json")
        self.index_path = os.path.join(base_dir, "index.faiss")
        
        with open(self.json_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
            
        self.index = faiss.read_index(self.index_path)
        self.model = SentenceTransformer('shibing624/text2vec-base-chinese')
        
        # 2. 初始化 Neo4j 連線資訊
        self.graph_client = CausalGraphClient()

    def retrieve(self, query: str, top_k: int = 1) -> dict:
        """
        Hybrid Search: 先用 FAISS 找圖文，再用 Neo4j 找該段落的因果邏輯
        """
        # ==========================================
        # 階段一：Vector Search (FAISS)
        # ==========================================
        q_vec = self.model.encode([query]).astype('float32')
        distances, indices = self.index.search(q_vec, top_k)
        
        best_match_idx = indices[0][0]
        best_match_dist = distances[0][0]
        
        # 距離過大代表不相關
        if best_match_dist > 800: 
            return {
                "status": "not_found",
                "retrieved_info": "在手冊知識庫中找不到與您問題高度相關的操作步驟。"
            }
            
        doc = self.metadata[best_match_idx]
        chunk_id = doc['id']  # 取得命中段落的 ID (例如 LRT_002)

        # ==========================================
        # 階段二：Graph Search (Neo4j)
        # ==========================================
        async def _get_graph_data():
            # 專門針對命中的 Chunk，查詢其專屬的因果鏈
            cypher_query = """
            MATCH (c:Chunk {chunk_id: $chunk_id})-[:MENTIONS]->(cause:Event)-[r:CAUSAL_LINK]->(effect:Event)
            RETURN cause.text AS cause, r.reason AS reason, effect.text AS effect
            """
            async with self.graph_client.driver.session() as session:
                result = await session.run(cypher_query, chunk_id=chunk_id)
                return await result.data()

        # 安全地在同步函式中執行非同步的 Neo4j 查詢 (避免阻塞 FastAPI)
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            graph_records = loop.run_until_complete(_get_graph_data())
            loop.close()
        except Exception as e:
            print(f"⚠️ Graph 檢索失敗: {e}")
            graph_records = []

        # ==========================================
        # 階段三：Grounded Prompt Assembly (混合組裝)
        # ==========================================
        formatted_result = (
            f"以下是從原廠手冊檢索到的標準操作步驟：\n\n"
            f"【{doc['equipment']} - {doc['topic']}】\n"
            f"{doc['content']}\n"
        )
        
        # 🌟 將抽取的因果圖譜邏輯，以顯眼的方式注入給 Agent！
        if graph_records:
            formatted_result += "\n> **【🔧 系統底層因果邏輯分析 (GraphRAG)】**\n"
            for idx, rec in enumerate(graph_records, 1):
                formatted_result += f"> {idx}. [{rec['cause']}] ──(原因：{rec['reason']})──> [{rec['effect']}]\n"

        # 組合圖片路徑
        image_paths = doc.get("image_paths", [])
        for img_path in image_paths:
            formatted_result += f"\n![{doc['topic']}]({img_path})\n"

        return {
            "status": "success",
            "distance": float(best_match_dist),
            "retrieved_info": formatted_result
        }