from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import requests
import os
import shutil
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from repository.mongo_repo import *
from repository.pg_repo import *
from repository.dis_query import *
from crawler.crawler_csv import *
from crawler.csv2pg import *
import schedule
import time as t
import pandas as pd
from pytz import timezone


# 設定時區為 Asia/Taipei
local_tz = timezone("Asia/Taipei")
local_time = datetime.now(local_tz)
print("Local time:", local_time)

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


def main():
    # 文件保存路徑
    folder_path = 'downloads/'
    SAVE_DIR = "downloads"
    SAVE_DIR_BAK = "downloads_bak"
    os.makedirs(SAVE_DIR, exist_ok=True)
    os.makedirs(SAVE_DIR_BAK, exist_ok=True)

    # 1. 到datainsight的genieai查詢MPN清單
    dis_sql = '''
                SELECT DISTINCT MPN FROM `genieai.HRI_Command_S` 
            '''
    df = dis_query(dis_sql)
    mpn_list = df['MPN'].tolist()
    print(mpn_list)

    # 2. 依據MPN下載csv
    # test_list = ['IAM-20680', 'LTM4625IY#PBF', 'BQ24190RGER', 'STM32H750IBK6', 'STM32F103VCT6', 'TPS2483PWR', 'LTM4700EY#PBF', 'SDINBDG4-16G-ZA', 'TLC7733QD']
    crawler_csv(mpn_list)

    # 3. CSV 下載成功，開始寫入 PostgreSQL
    import_csvs_to_pg()

    # 移動 csv 檔案到 downloads_bak
    for file_name in os.listdir(SAVE_DIR):
        if file_name.endswith(".csv"):
            src_path = os.path.join(SAVE_DIR, file_name)
            dst_path = os.path.join(SAVE_DIR_BAK, f"{file_name}")
            shutil.move(src_path, dst_path)
            logging.info(f"移動檔案 {src_path} 到 {dst_path}")

if __name__ == '__main__':
    execution_count = 0  # 初始化執行次數計數器

    while True:
        try:
            execution_count += 1  # 每次執行前增加計數
            logging.info(f"開始執行第 {execution_count} 次 main()")
            main()  # 執行 main 函數
            logging.info(f"第 {execution_count} 次 main() 執行完成")
        except Exception as e:
            logging.error(f"執行第 {execution_count} 次 main() 時發生錯誤: {str(e)}")
        
        # 可選：在每次執行完成後加入延遲，避免過於頻繁的執行
        t.sleep(1800)  # 延遲 1800 秒後重新執行


    # schedule.every(2).minutes.do(main)  # 每 2 分鐘執行一次 main 函數
    # schedule.every().friday.at("18:00").do(main)  # 每週五下午 6:00 執行一次 main 函數
    # schedule.every().day.at("17:30").do(main)  # 每天下午 5:30 執行一次 main 函數

    # while True:
    #     schedule.run_pending()
    #     t.sleep(1)