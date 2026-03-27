import fitz  # PyMuPDF
import json
import os
import re

def process_pdf(pdf_path, equipment_name, prefix_id, img_output_dir):
    """
    解析單一 PDF，擷取每頁的文字與圖片，並回傳 RAG 格式的字典列表
    """
    doc = fitz.open(pdf_path)
    rag_data = []

    # 確保圖片輸出的資料夾存在
    os.makedirs(img_output_dir, exist_ok=True)

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        
        # 1. 擷取文字
        text = page.get_text("text").strip()
        if not text or len(text) < 20:
            continue  # 忽略空白頁或字數太少的頁面
            
        # 清洗文字 (去除多餘換行與特殊字元)
        text = re.sub(r'\n+', '\n', text)
        lines = text.split('\n')
        
        # 簡單推論：把該頁的第一行當作 Topic，剩下的當作 Content
        topic = lines[0] if lines else f"Page {page_num + 1}"
        content = text
        
        image_paths_for_json = [] # 🌟 改為陣列來存放多張圖片
        
        # 2. 擷取圖片 (支援多圖排序與過濾)
        image_list = page.get_images(full=True)
        valid_images = []
        
        if image_list:
            for img in image_list:
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    w = base_image["width"]
                    h = base_image["height"]
                    area = w * h
                    
                    # 【過濾規則】：長寬皆需大於 50 像素
                    if w > 50 and h > 50:
                        valid_images.append({
                            "area": area, 
                            "bytes": base_image["image"], 
                            "ext": base_image["ext"]
                        })
                except Exception as e:
                    continue
            
            # 不依照面積排序，直接使用 PDF 內部解析到的先後順序
            top_images = valid_images

            for idx, img_data in enumerate(top_images):
                # 檔名加上 _1, _2 來區分同頁的多張圖
                img_filename = f"{prefix_id}_page{page_num + 1}_{idx + 1}.{img_data['ext']}"
                img_filepath = os.path.join(img_output_dir, img_filename)
                
                with open(img_filepath, "wb") as img_file:
                    img_file.write(img_data["bytes"])
                    
                image_paths_for_json.append(f"/images/rag/{img_filename}")
                
        # 3. 組裝成 RAG 字典
        rag_data.append({
            "id": f"{prefix_id}_{page_num + 1:03d}",
            "equipment": equipment_name,
            "topic": topic,
            "content": content,
            "image_paths": image_paths_for_json  
        })
        
    print(f"✅ 成功解析 {equipment_name}：共處理 {len(rag_data)} 頁有效圖文。")
    return rag_data

def main():
    # --- 路徑設定 ---
    # 假設你的 pdf 放在 backend/pdfs 裡面 (請自行建立並放入檔案)
    pdf_dir = os.path.join(os.path.dirname(__file__), "pdfs")
    
    # 輸出的 JSON 路徑
    json_out_dir = os.path.join(os.path.dirname(__file__), "rag_data")
    os.makedirs(json_out_dir, exist_ok=True)
    json_out_path = os.path.join(json_out_dir, "manuals.json")
    
    # 輸出的圖片路徑 (自動放到前端 Next.js 的 public 裡面)
    # 這裡假設 backend 和 frontend 是並排在同一個父目錄下
    frontend_img_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "images", "rag")
    
    all_rag_data = []
    
    # --- 1. 處理 LRT 手冊 ---
    lrt_pdf = os.path.join(pdf_dir, "[LRT操作手冊].pdf")
    if os.path.exists(lrt_pdf):
        lrt_data = process_pdf(lrt_pdf, "LRT", "LRT", frontend_img_dir)
        all_rag_data.extend(lrt_data)
    else:
        print(f"找不到檔案: {lrt_pdf}")

    # --- 2. 處理 海德漢 TNC640 手冊 ---
    # heidenhain_pdf = os.path.join(pdf_dir, "海德漢TNC640操作手冊.pdf")
    # if os.path.exists(heidenhain_pdf):
    #     heidenhain_data = process_pdf(heidenhain_pdf, "Heidenhain TNC640", "TNC640", frontend_img_dir)
    #     all_rag_data.extend(heidenhain_data)
    # else:
    #     print(f"找不到檔案: {heidenhain_pdf}")
        
    # --- 3. 輸出最終 JSON ---
    if all_rag_data:
        with open(json_out_path, "w", encoding="utf-8") as f:
            json.dump(all_rag_data, f, ensure_ascii=False, indent=2)
        print(f"🎉 RAG 知識庫 JSON 建立完成！共 {len(all_rag_data)} 筆資料。")
        print(f"檔案已儲存至: {json_out_path}")

if __name__ == "__main__":
    main()