from flask import Flask, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup
from gevent import pywsgi
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import requests
import os
import shutil
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from repository.mongo_repo import * 

# 加載 .env 文件中的環境變數
load_dotenv()

# 確保 logs 資料夾存在
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# 設定日誌，使用 RotatingFileHandler
LOG_FILE = os.path.join(LOG_DIR, "app.log")
handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[handler, logging.StreamHandler()]
)

app = Flask(__name__)
CORS(app)  # 啟用 CORS 支持

# 配置 ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# 模擬瀏覽器的 Headers
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.mouser.tw/",
    "Sec-CH-UA": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Host": "www.mouser.tw"  # 添加 Host 標頭
}

# 文件保存路徑
folder_path = 'downloads/'
SAVE_DIR = "downloads"
SAVE_DIR_BAK = "downloads_bak"
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(SAVE_DIR_BAK, exist_ok=True)

# 從環境變數讀取 MongoDB 連接參數 (default : ews003)
mongo_uri = os.getenv('MONGO_URI', 'mongodb://02ffe07c-aab4-4647-bac0-062ed906ec6a:X40IVUWSP3NcHciWvqZTa3N0@172.22.1.54:27017/f683e44e-5c9b-4c0a-8980-b7014f4a2efd')
logging.info(f"使用的 MongoDB URI: {mongo_uri}")
db_name = os.getenv('DB_NAME', 'f683e44e-5c9b-4c0a-8980-b7014f4a2efd')
logging.info(f"使用的資料庫名稱: {db_name}")
log_collection = 'mtd.hri.import_logs'

def download_file(url, session, file_path, headers, retries=3):
    """
    通用下載函式，用於下載文件並保存到指定路徑，帶有重試機制。
    """
    for attempt in range(retries):
        try:
            logging.info(f"開始下載文件，URL: {url}，嘗試次數: {attempt + 1}")
            response = session.get(url, headers=headers, timeout=10, verify=False)
            if response.status_code == 200:
                with open(file_path, 'wb') as file:
                    file.write(response.content)
                logging.info(f"文件已成功保存到: {file_path}")
                return True
            else:
                logging.error(f"下載失敗，狀態碼: {response.status_code}")
        except Exception as e:
            logging.error(f"下載過程中發生錯誤: {str(e)}")
    return False

@app.after_request
def add_log_separator(response):
    """
    在每次 API 呼叫結束後，於日誌中加入分隔線。
    """
    logging.info("-" * 100)
    return response

@app.route('/', methods=['GET'])
def index():
    logging.info("訪問首頁路由 '/'")
    return "HRI API..."

@app.route('/api/search', methods=['GET'])
def search():
    """
    接收使用者輸入的查詢參數，訪問目標網站並返回結果。
    :param query: 使用者輸入的查詢字串，例如 "IAM-20680"
    """
    query = request.args.get('query')
    if not query:
        logging.warning("缺少查詢參數 'query'")
        return jsonify({"error": "缺少查詢參數 'query'"}), 400

    # 組合目標 URL，使用 IP 地址
    url = f"https://184.30.10.45/c/?q={query}"  # 使用 www.mouser.tw 的 IP 地址
    logging.info(f"[{query}] 組合目標 URL: {url}")

    # 使用 Session 管理 Cookies
    session = requests.Session()

    try:
        # 初始請求以獲取最新的 Cookies
        logging.info(f"[{query}] 正在訪問 URL: {url}")
        initial_response = session.get(url, headers=headers, timeout=10, verify=False)
        if initial_response.status_code == 200:
            logging.info(f"[{query}] 初始頁面請求成功")
            # 使用 BeautifulSoup 解析 HTML
            soup = BeautifulSoup(initial_response.text, 'html.parser')

            # 找到 id 為 "btn3" 的 <a> 標籤
            download_link = soup.find('a', id='btn3')

            if download_link:
                # 提取 href 屬性的值
                href_value = download_link.get('href')
                download_url = f"https://184.30.10.45{href_value}"  # 使用 IP 地址
                logging.info(f"[{query}] 找到下載連結: {download_url}")

                # 生成帶有當下時間的 HTML 文件名稱
                current_time = datetime.now().strftime("%Y%m%d%H%M%S")

                # 生成帶有當下時間的 CSV 文件名稱
                csv_file_name = f"{query}_{current_time}.csv"
                csv_file_path = os.path.join(SAVE_DIR, csv_file_name)

                # 發送下載請求並保存 CSV 文件
                if download_file(download_url, session, csv_file_path, headers):
                    logging.info(f"[{query}] CSV 文件已成功下載並保存在 '{csv_file_path}'")
                    logging.info(f"[{query}] 完整的下載連結為: {download_url}")

                    # 將 csv 寫入 mongo
                    import_all_csvs_to_mongodb(folder_path, mongo_uri, db_name, log_collection)

                    # 根據文件名稱生成 MongoDB collection 名稱
                    source_file = os.path.basename(csv_file_path)
                    collection_name_part = source_file.split('_')[0]
                    data_collection_name = f"mtd.hri.{collection_name_part}"
                    
                    # 移動 csv 檔案到 downloads_bak
                    bak_file_path = os.path.join(SAVE_DIR_BAK, csv_file_name)
                    try:
                        shutil.move(csv_file_path, bak_file_path)
                        logging.info(f"[{query}] 已將 CSV 檔案移動到備份資料夾: {bak_file_path}")
                    except Exception as e:
                        logging.error(f"[{query}] 移動 CSV 檔案到備份資料夾失敗: {e}")

                    # 返回成功訊息，包含 MongoDB 寫入的 collection 名稱和狀態
                    return jsonify({
                        "message": f"CSV 文件已成功下載並保存在 '{bak_file_path}'，MongoDB 寫入 '{data_collection_name}' 成功",
                        "status": "OK"
                    })
                else:
                    logging.error(f"[{query}] 下載 CSV 文件失敗")
                    return jsonify({"error": "下載 CSV 文件失敗"}), 500
            else:
                logging.warning(f"[{query}] 未找到 id='btn3' 的下載按鈕")
                return jsonify({"error": "未找到 id='btn3' 的下載按鈕"}), 404
        else:
            logging.error(f"[{query}] 無法訪問頁面，狀態碼: {initial_response.status_code}")
            return jsonify({"error": f"無法訪問頁面，狀態碼: {initial_response.status_code}"}), initial_response.status_code
    except requests.exceptions.Timeout:
        logging.error(f"[{query}] 請求超時")
        return jsonify({"error": "請求超時，請稍後重試"}), 504
    except Exception as e:
        logging.error(f"[{query}] 發生錯誤: {str(e)}")
        return jsonify({"error": f"發生錯誤: {str(e)}"}), 500

if __name__ == '__main__':
    logging.info("伺服器啟動中，監聽 0.0.0.0:9981")
    server = pywsgi.WSGIServer(('0.0.0.0', 9981), app)
    server.serve_forever()