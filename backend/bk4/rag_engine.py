import json
import os
import re
import faiss
import asyncio
from sentence_transformers import SentenceTransformer
# 引入我們剛建好的 Neo4j Client
from bk4.neo4j_client import CausalGraphClient

# 可被辨識的誤差代碼（與 static_analyzer.py params key 一致）
_ERROR_CODE_PATTERN = re.compile(
    r'\b('
    r'XOC|YOC|ZOC|AOC|BOC|'
    r'XOA|YOA|ZOA|BOA|COA|'
    r'Runout_X_Amp|Runout_Y_Amp|Runout_Z_Amp|'
    r'Wobble_A_Amp|Wobble_B_Amp|'
    r'servo_mismatch|reversal_spike|gravity_deformation'
    r')\b'
)

# 中文別名 → 標準 error_code（讓使用者用中文問也能命中 seed）
_CN_ALIAS_MAP = {
    'XOC': 'XOC', 'YOC': 'YOC', 'ZOC': 'ZOC',
    'AOC': 'AOC', 'BOC': 'BOC',
    'YOA': 'YOA', 'ZOA': 'ZOA', 'BOA': 'BOA', 'COA': 'COA',
    'EXC': 'Runout_X_Amp', 'EYC': 'Runout_Y_Amp', 'EZC': 'Runout_Z_Amp',
    'EAC': 'Wobble_A_Amp', 'EBC': 'Wobble_B_Amp',
}


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

    def retrieve(self, query: str, top_k: int = 1,
                 equipment_filter: list | None = None) -> dict:
        """
        Hybrid Search: 先用 FAISS 找圖文，再用 Neo4j 找該段落的因果邏輯。
        equipment_filter: 允許的 equipment 名稱列表（例如 ["LRT", "Heidenhain"]），
                          None = 不限制。
        """
        # ==========================================
        # 階段一：Vector Search (FAISS)
        # ==========================================
        q_vec = self.model.encode([query]).astype('float32')
        # 多拉一些候選，以便在 equipment_filter 過濾後仍有結果
        search_k = max(top_k * 5, 10)
        distances, indices = self.index.search(q_vec, search_k)

        # 從候選中找第一個符合 equipment_filter 的結果
        best_match_idx = None
        best_match_dist = None
        for i in range(search_k):
            idx = indices[0][i]
            if idx < 0 or idx >= len(self.metadata):
                continue
            doc_candidate = self.metadata[idx]
            # 若有篩選條件，跳過不在清單中的 equipment
            if equipment_filter and doc_candidate.get('equipment') not in equipment_filter:
                continue
            best_match_idx = idx
            best_match_dist = distances[0][i]
            break

        if best_match_idx is None or best_match_dist > 800:
            return {
                "status": "not_found",
                "retrieved_info": "在手冊知識庫中找不到與您問題高度相關的操作步驟。"
            }

        doc = self.metadata[best_match_idx]
        chunk_id = doc['id']  # 取得命中段落的 ID (例如 LRT_002)

        # ==========================================
        # 階段二：Graph Search (Neo4j)
        # ==========================================

        # 2-A. 從 query 中提取誤差代碼（支援 XOC 格式與 EXC 別名）
        detected_codes = set(_ERROR_CODE_PATTERN.findall(query))
        for token in re.findall(r'[A-Z_]{2,}', query.upper()):
            if token in _CN_ALIAS_MAP:
                detected_codes.add(_CN_ALIAS_MAP[token])

        async def _get_graph_data():
            async with self.graph_client.driver.session() as session:
                # 2-B. 因果鏈查詢（沿用原有 Chunk → Event → CAUSAL_LINK）
                cypher_causal = """
                MATCH (c:Chunk {chunk_id: $chunk_id})-[:MENTIONS]->(cause:Event)-[r:CAUSAL_LINK]->(effect:Event)
                RETURN cause.text AS cause, r.reason AS reason, effect.text AS effect
                """
                causal_result = await session.run(cypher_causal, chunk_id=chunk_id)
                causal_data   = await causal_result.data()

                # 2-C. TNCFunction 查詢（透過 Chunk 的 PROCEDURE_STEP 邊）
                cypher_tnc_chunk = """
                MATCH (f:TNCFunction)-[:PROCEDURE_STEP]->(c:Chunk {chunk_id: $chunk_id})
                OPTIONAL MATCH (f)-[:REQUIRES_OPTION]->(o:SoftwareOption)
                OPTIONAL MATCH (f)-[:CONFIGURED_BY]->(m:MachineParameter)
                RETURN
                    f.name        AS function_name,
                    f.cycle_no    AS cycle_no,
                    f.description AS description,
                    collect(DISTINCT o.opt_id) AS opts,
                    collect(DISTINCT m.mp_id)  AS mps
                """
                tnc_result = await session.run(cypher_tnc_chunk, chunk_id=chunk_id)
                tnc_data   = await tnc_result.data()

                # 2-D. 直接走 ErrorType → TNCFunction（seed 資料路徑，不依賴 Chunk）
                if detected_codes:
                    cypher_tnc_direct = """
                    MATCH (e:ErrorType)-[:COMPENSATED_BY]->(f:TNCFunction)
                    WHERE e.code IN $codes
                    OPTIONAL MATCH (f)-[:REQUIRES_OPTION]->(o:SoftwareOption)
                    OPTIONAL MATCH (f)-[:CONFIGURED_BY]->(m:MachineParameter)
                    RETURN
                        f.name        AS function_name,
                        f.cycle_no    AS cycle_no,
                        f.description AS description,
                        collect(DISTINCT o.opt_id) AS opts,
                        collect(DISTINCT m.mp_id)  AS mps
                    """
                    direct_result = await session.run(
                        cypher_tnc_direct, codes=list(detected_codes)
                    )
                    direct_data = await direct_result.data()
                else:
                    direct_data = []

                # 合併去重（以 function_name 為 key）
                seen = {r['function_name'] for r in tnc_data}
                for r in direct_data:
                    if r['function_name'] not in seen:
                        tnc_data.append(r)
                        seen.add(r['function_name'])

            return causal_data, tnc_data

        # 安全地在同步函式中執行非同步的 Neo4j 查詢 (避免阻塞 FastAPI)
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            graph_records, tnc_records = loop.run_until_complete(_get_graph_data())
            loop.close()
        except Exception as e:
            print(f"⚠️ Graph 檢索失敗: {e}")
            graph_records = []
            tnc_records   = []

        # ==========================================
        # 階段三：Grounded Prompt Assembly (混合組裝)
        # ==========================================
        formatted_result = (
            f"以下是從原廠手冊檢索到的標準操作步驟：\n\n"
            f"【{doc['equipment']} - {doc['topic']}】\n"
            f"{doc['content']}\n"
        )

        # 因果鏈注入
        if graph_records:
            formatted_result += "\n> **【🔧 系統底層因果邏輯分析 (GraphRAG)】**\n"
            for idx, rec in enumerate(graph_records, 1):
                formatted_result += f"> {idx}. [{rec['cause']}] ──(原因：{rec['reason']})──> [{rec['effect']}]\n"

        # TNC 640 補償功能注入
        if tnc_records:
            formatted_result += "\n> **【⚙️ TNC 640 補償功能對映】**\n"
            for rec in tnc_records:
                opts = ", ".join(rec["opts"]) if rec["opts"] else "無需額外 Option"
                mps  = ", ".join(rec["mps"])  if rec["mps"]  else "無需特別 MP"
                formatted_result += (
                    f"> **{rec['function_name']}** ({rec['cycle_no']})\n"
                    f"> - {rec['description']}\n"
                    f"> - 需要授權：{opts}\n"
                    f"> - 相關 MP：{mps}\n"
                )

        # 組合圖片路徑
        image_paths = doc.get("image_paths", [])
        for img_path in image_paths:
            formatted_result += f"\n![{doc['topic']}]({img_path})\n"

        return {
            "status": "success",
            "distance": float(best_match_dist),
            "retrieved_info": formatted_result
        }