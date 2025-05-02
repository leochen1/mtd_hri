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
    # 1. 到datainsight的genieai查詢MPN清單
    dis_sql = '''
                SELECT DISTINCT MPN FROM `genieai.HRI_Command_S`
            '''
    df = dis_query(dis_sql)
    mpn_list = df['MPN'].tolist()
    
    # print(df)
    print(mpn_list)


    # 2. 依據MPN下載csv
    # test_list = ['IAM-20680', 'LTM4625IY#PBF', 'BQ24190RGER', 'STM32H750IBK6', 'STM32F103VCT6', 'TPS2483PWR', 'LTM4700EY#PBF', 'SDINBDG4-16G-ZA']
    crawler_csv(mpn_list)

    # 3. 將csv寫到pg
    import_csvs_to_pg()



if __name__ == '__main__':
    # main()

    # schedule.every(2).minutes.do(main)  # 每 2 分鐘執行一次 main 函數
    schedule.every().friday.at("17:30").do(main)  # 每週五下午 5:30 執行一次 main 函數
    
    while True:
        schedule.run_pending()
        t.sleep(1)