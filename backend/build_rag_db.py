import json
import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

def build_vector_store():
    data_dir = "rag_data"
    json_path = os.path.join(data_dir, "manuals.json")
    
    # 1. 讀取 JSON 資料
    with open(json_path, "r", encoding="utf-8") as f:
        documents = json.load(f)

    # 2. 載入開源的中文 Embedding 模型
    print("載入 Embedding 模型中...")
    model = SentenceTransformer('shibing624/text2vec-base-chinese')

    # 3. 將 topic + content 組合成要向量化的文本
    texts_to_embed = [f"{doc['equipment']} {doc['topic']} {doc['content']}" for doc in documents]
    
    print(f"正在計算 {len(texts_to_embed)} 筆文本的向量...")
    embeddings = model.encode(texts_to_embed)
    
    # 4. 建立 FAISS 索引
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings).astype('float32'))
    
    # 5. 儲存 Index 與 Metadata
    faiss.write_index(index, os.path.join(data_dir, "index.faiss"))
    print("✅ FAISS 向量資料庫建立完成 (index.faiss)")

if __name__ == "__main__":
    build_vector_store()