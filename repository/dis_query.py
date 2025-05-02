import requests, json
import pandas as pd

def dis_query(query):
    DIS_API_URL = "https://api-dis-dis-ews002.mfg.wise-paas.com"
    # genieai
    DIS_USER = "dis.user@advantech.com.tw"
    DIS_PASSWORD = "Dashboard@1234"
    session = requests.session()
    # Login
    url = f"{DIS_API_URL}/api/v1/login"
    r = session.post(url, json={"username": DIS_USER, "password": DIS_PASSWORD}, timeout=60)
    r = r.json()
    # Check login success
    if 'message' not in r:
        return {"error": "Login failed"}, 401
    # Search
    url = f"{DIS_API_URL}/api/v1/data/preview"
    r = session.post(url, json={"sql": query}, timeout=60)
    res = r.json()
    # Data
    if 'rows' not in res:
        return []
    target_data = []
    for row in res["rows"]:
        row_data = {column["name"]: row["row"][i]["v"] for i, column in enumerate(res["columns"])}
        target_data.append(row_data)
    # Convert to DataFrame
    df = pd.DataFrame(target_data) if target_data else pd.DataFrame()
    return df
