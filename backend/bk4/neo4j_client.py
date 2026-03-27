import logging
import hashlib
import asyncio
import warnings
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
from neo4j.warnings import Neo4jWarning

# 忽略 Neo4j 的警告訊息
warnings.filterwarnings("ignore", category=Neo4jWarning)

# 載入環境變數
load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "raptor_password123")

logger = logging.getLogger(__name__)

class CausalGraphClient:
    def __init__(self, uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self):
        await self.driver.close()

    def _generate_hash(self, text: str) -> str:
        """產生固定長度的 Hash 值，確保文字完全相同的事件擁有相同的 ID"""
        return hashlib.md5(text.strip().encode('utf-8')).hexdigest()

    async def setup_schema(self):
        """初始化資料庫的 Constraints (確保冪等性與檢索效能)"""
        schema_queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.hash_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Summary) REQUIRE s.summary_id IS UNIQUE"
        ]
        async with self.driver.session() as session:
            for query in schema_queries:
                await session.run(query)
        logger.info("Neo4j Schema and Constraints initialized successfully.")

    async def ingest_extracted_causality(self, doc_id: str, cause_text: str, effect_text: str, reason: str):
        """將 LLM 萃取出的因果關係寫入圖譜 (具備雙層 Hash 防呆)"""
        cause_hash = self._generate_hash(cause_text)
        effect_hash = self._generate_hash(effect_text)

        query = """
        MERGE (d:Document {doc_id: $doc_id})
        MERGE (c:Event {hash_id: $cause_hash})
        ON CREATE SET c.text = $cause_text
        MERGE (e:Event {hash_id: $effect_hash})
        ON CREATE SET e.text = $effect_text
        MERGE (c)-[:OCCURRED_IN]->(d)
        MERGE (e)-[:OCCURRED_IN]->(d)
        MERGE (c)-[:CAUSAL_LINK {reason: $reason}]->(e)
        """
        async with self.driver.session() as session:
            await session.run(
                query, doc_id=doc_id, cause_hash=cause_hash, cause_text=cause_text,
                effect_hash=effect_hash, effect_text=effect_text, reason=reason
            )

    async def ingest_raptor_hierarchy(self, doc_id: str, summary_id: str, summary_text: str, level: int, child_chunks: list):
        """將 RAPTOR 的階層化結構寫入圖譜。"""
        query = """
        MERGE (d:Document {doc_id: $doc_id})
        MERGE (s:Summary {summary_id: $summary_id})
        ON CREATE SET s.text = $summary_text, s.level = $level
        MERGE (s)-[:BELONGS_TO]->(d)
        WITH d, s
        UNWIND $child_chunks AS child
        MERGE (c:Chunk {chunk_id: child.chunk_id})
        ON CREATE SET
            c.text               = child.text,
            c.sequence_index     = child.sequence_index,
            c.timestamp          = child.timestamp,
            c.prepended_context  = child.prepended_context
        ON MATCH SET
            c.sequence_index     = child.sequence_index,
            c.timestamp          = child.timestamp,
            c.prepended_context  = child.prepended_context
        MERGE (c)-[:BELONGS_TO]->(d)
        MERGE (c)-[:SUMMARIZES]->(s)
        """
        try:
            async with self.driver.session() as session:
                await session.run(
                    query, doc_id=doc_id, summary_id=summary_id, summary_text=summary_text,
                    level=level, child_chunks=child_chunks
                )
        except Exception as e:
            logger.error(f"寫入 RAPTOR 階層時發生錯誤: {e}")

    async def ingest_chunk_causality(self, doc_id: str, chunk_id: str, cause_text: str, effect_text: str, reason: str):
        """將提取出的因果關係 (Event) 直接與它所屬的文本區塊 (Chunk) 綁定。"""
        cause_hash = self._generate_hash(cause_text)
        effect_hash = self._generate_hash(effect_text)

        query = """
        MERGE (d:Document {doc_id: $doc_id})
        MERGE (chunk:Chunk {chunk_id: $chunk_id})
        MERGE (chunk)-[:BELONGS_TO]->(d)
        MERGE (cause:Event {hash_id: $cause_hash})
        ON CREATE SET cause.text = $cause_text
        MERGE (effect:Event {hash_id: $effect_hash})
        ON CREATE SET effect.text = $effect_text
        MERGE (chunk)-[:MENTIONS]->(cause)
        MERGE (chunk)-[:MENTIONS]->(effect)
        MERGE (cause)-[:CAUSAL_LINK {reason: $reason}]->(effect)
        """
        try:
            async with self.driver.session() as session:
                await session.run(
                    query, doc_id=doc_id, chunk_id=chunk_id, cause_hash=cause_hash,
                    cause_text=cause_text, effect_hash=effect_hash, effect_text=effect_text, reason=reason
                )
        except Exception as e:
            logger.error(f"綁定 Chunk 與因果鏈時發生錯誤: {e}")

    async def create_temporal_link(self, prev_chunk_id: str, current_chunk_id: str, prev_seq: int, curr_seq: int):
        """在相鄰的兩個 Chunk 之間建立 TEMPORAL_NEXT 時序邊"""
        query = """
        MERGE (prev:Chunk {chunk_id: $prev_chunk_id})
        ON CREATE SET prev.sequence_index = $prev_seq
        ON MATCH SET  prev.sequence_index = $prev_seq
        MERGE (curr:Chunk {chunk_id: $current_chunk_id})
        ON CREATE SET curr.sequence_index = $curr_seq
        ON MATCH SET  curr.sequence_index = $curr_seq
        MERGE (prev)-[:TEMPORAL_NEXT]->(curr)
        """
        try:
            async with self.driver.session() as session:
                await session.run(query, prev_chunk_id=prev_chunk_id, current_chunk_id=current_chunk_id, prev_seq=prev_seq, curr_seq=curr_seq)
        except Exception as e:
            logger.error(f"建立 TEMPORAL_NEXT 時發生錯誤: {e}")

    async def create_causal_link(self, cause_id: str, effect_id: str, reason: str):
        """建立因果邊界 (CAUSAL_LINK)"""
        query = """
        MATCH (cause {chunk_id: $cause_id})
        MATCH (effect {chunk_id: $effect_id})
        MERGE (cause)-[:CAUSAL_LINK {reason: $reason}]->(effect)
        """
        async with self.driver.session() as session:
            await session.run(query, cause_id=cause_id, effect_id=effect_id, reason=reason)

    async def retrieve_causal_path(self, doc_id: str) -> list:
        """根據 doc_id 檢索該文件內的所有因果邏輯鏈（不含時序排序）。"""
        query = """
        MATCH (d:Document {doc_id: $doc_id})<-[:BELONGS_TO]-(:Chunk)-[:MENTIONS]->(cause:Event)
        MATCH (cause)-[r:CAUSAL_LINK]->(effect:Event)
        RETURN DISTINCT cause.text AS cause, r.reason AS reason, effect.text AS effect
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, doc_id=doc_id)
                return await result.data()
        except Exception as e:
            logger.error(f"檢索因果路徑時發生錯誤: {e}")
            return []

    async def retrieve_temporal_causal_path(self, doc_id: str) -> list:
        """【時序 + 因果整合查詢】"""
        query = """
        MATCH (d:Document {doc_id: $doc_id})<-[:BELONGS_TO]-(chunk:Chunk)
        OPTIONAL MATCH (chunk)-[:TEMPORAL_NEXT]->(next_chunk:Chunk)
        OPTIONAL MATCH (chunk)-[:MENTIONS]->(cause:Event)-[r:CAUSAL_LINK]->(effect:Event)
        RETURN DISTINCT
            chunk.chunk_id       AS chunk_id,
            chunk.sequence_index AS sequence_index,
            chunk.timestamp      AS timestamp,
            cause.text           AS cause,
            r.reason             AS reason,
            effect.text          AS effect,
            next_chunk.chunk_id  AS next_chunk_id
        ORDER BY chunk.sequence_index ASC
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, doc_id=doc_id)
                return await result.data()
        except Exception as e:
            logger.error(f"檢索時序因果路徑時發生錯誤: {e}")
            return []

    async def retrieve_macro_raptor_context(self, summary_id: str) -> list:
        """【立體檢索】給定 Summary ID，向下鑽取所有 Chunk 及其因果鏈。"""
        query = """
        MATCH (s:Summary {summary_id: $summary_id})
        OPTIONAL MATCH (c:Chunk)-[:SUMMARIZES]->(s)
        OPTIONAL MATCH (c)-[:MENTIONS]->(cause:Event)-[r:CAUSAL_LINK]->(effect:Event)
        RETURN
            s.text       AS macro_summary,
            c.chunk_id   AS chunk_id,
            cause.text   AS cause,
            r.reason     AS reason,
            effect.text  AS effect
        ORDER BY c.chunk_id
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, summary_id=summary_id)
                return await result.data()
        except Exception as e:
            logger.error(f"檢索立體圖譜時發生錯誤: {e}")
            return []

# 獨立測試區塊
async def main():
    logging.basicConfig(level=logging.INFO)
    client = CausalGraphClient()
    try:
        await client.setup_schema()
        print("🎉 Neo4j Connected & Schema Ready!")
    except Exception as e:
        print(f"❌ 連線失敗: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())