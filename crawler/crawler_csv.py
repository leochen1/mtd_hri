import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import pandas as pd
import time
import random
import urllib3
from requests.exceptions import Timeout


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def download_csv_file(url, session, file_path, headers, retries=3):
    """
    通用下載函式，用於下載文件並保存到指定路徑，帶有重試機制。
    """
    for attempt in range(retries):
        try:
            logging.info(f"開始下載文件，URL: {url}，嘗試次數: {attempt + 1}")
            response = session.get(url, headers=headers, timeout=30, verify=False)
            if response.status_code == 200:
                with open(file_path, 'wb') as file:
                    file.write(response.content)
                logging.info(f"文件已成功保存到: {file_path}")
                return True
            else:
                logging.error(f"下載失敗，狀態碼: {response.status_code}")
        except Exception as e:
            logging.error(f"下載過程中發生錯誤: {str(e)}")
        time.sleep(2)  # 每次重試間隔
    return False

def crawler_csv(mpn_list: list):
    SAVE_DIR = "downloads"
    SAVE_DIR_BAK = "downloads_bak"
    os.makedirs(SAVE_DIR, exist_ok=True)
    os.makedirs(SAVE_DIR_BAK, exist_ok=True)

    # 真實瀏覽器 Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-TW,zh;q=0.9",
        "Sec-CH-UA": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-CH-UA-Arch": '"x86"',
        "Sec-CH-UA-Full-Version-List": '"Chromium";v="136.0.7103.48", "Google Chrome";v="136.0.7103.48", "Not.A/Brand";v="99.0.0.0"',
        "Sec-CH-UA-Model": '""',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.mouser.tw/",
    }

    not_found_btn3_list = []
    found_btn3_list = []
    MAX_HTML_RETRY = 3

    # 初始化 Session
    with requests.Session() as session:
        session.headers.update(headers)

        for query in mpn_list:           
            url = f"https://www.mouser.tw/c/?q={query}"  # 184.30.10.45
            logging.info(f"[{query}] 組合目標 URL: {url}")

            html_retry = 0
            html_ok = False

            while html_retry < MAX_HTML_RETRY and not html_ok:
                try:
                    # 隨機延遲
                    time.sleep(random.uniform(2, 5))

                    logging.info(f"[{query}] 正在訪問 URL: {url} (第{html_retry+1}次嘗試)")
                    response = session.get(url, timeout=30, verify=False)

                    # 自動更新 Cookies
                    logging.info(f"[{query}] 當前請求使用的 Cookies: {session.cookies.get_dict()}")

                    if response.status_code == 200:
                        text = response.text

                        # 判斷內容是否疑似被擋（如只有 script 或內容過短或含有 challenge script）
                        is_html = "<html" in text
                        is_too_short = len(text) < 1000
                        is_challenge = (
                            "<script" in text and
                            "window.XMLHttpRequest.prototype.send" in text and
                            "location.reload(true);" in text
                        )
                        if is_html and not is_too_short and not is_challenge:
                            html_ok = True
                        else:
                            logging.warning(f"[{query}] 取得的 HTML 內容異常或被反爬蟲擋住，重試中...")
                            html_retry += 1
                            
                            # 隨機延遲
                            sleep_time = random.uniform(30, 60)
                            logging.info(f"[{query}] 第 {html_retry} 次重試，sleep {sleep_time} 秒")
                            time.sleep(sleep_time)

                            # # 漸進式增加 sleep 時間
                            # sleep_time = [30, 1200, 1200, 1200][min(html_retry, 3)]
                            # logging.info(f"[{query}] 第 {html_retry} 次重試，sleep {sleep_time} 秒")
                            # time.sleep(sleep_time)
                    else:
                        logging.error(f"[{query}] 無法訪問頁面，狀態碼: {response.status_code}")
                        html_retry += 1
                except Timeout:
                    logging.error(f"[{query}] 請求超時（超過 30 秒）")
                    html_retry += 1
                except Exception as e:
                    logging.error(f"[{query}] 發生錯誤: {str(e)}")
                    html_retry += 1
        
            if not html_ok:
                logging.error(f"[{query}] 多次嘗試後仍無法取得完整 HTML")
                not_found_btn3_list.append(query)
                continue

            # 解析 HTML 並嘗試找到下載連結
            logging.info(f"[{query}] 初始頁面請求成功")
            soup = BeautifulSoup(response.text, 'html.parser')
            download_link = soup.find('a', id='btn3')

            if download_link:
                found_btn3_list.append(query)
                href_value = download_link.get("href")
                download_url = href_value if href_value.startswith("http") else f"https://www.mouser.tw{href_value}"
                logging.info(f"[{query}] 找到下載連結: {download_url}")
            else:
                logging.warning(f"[{query}] 未找到 id='btn3' 的下載按鈕")
                not_found_btn3_list.append(query)
                continue


            # 下載 CSV
            current_time = datetime.now().strftime("%Y%m%d%H%M%S")
            csv_file_name = f"{query}_{current_time}.csv"
            csv_file_path = os.path.join(SAVE_DIR, csv_file_name)
            if download_csv_file(download_url, session, csv_file_path, headers):
                logging.info(f"[{query}] CSV 文件已成功下載並保存在 '{csv_file_path}'")
                logging.info(f"[{query}] 完整的下載連結為: {download_url}")
            else:
                logging.error(f"[{query}] 下載 CSV 文件失敗")


            # 每次請求後隨機 sleep
            sleep_time = random.uniform(10, 20)
            logging.info(f"[{query}] 請求結束，隨機延遲 {sleep_time:.2f} 秒以避免被封鎖")
            time.sleep(sleep_time)

        print("有找到 btn3 的清單：", found_btn3_list)
        logging.info(f"有找到 btn3 的清單：{found_btn3_list}")
        print("未找到 btn3 的清單：", not_found_btn3_list)
        logging.info(f"未找到 btn3 的清單：{not_found_btn3_list}")

