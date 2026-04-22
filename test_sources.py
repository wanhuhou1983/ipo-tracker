# -*- coding: utf-8 -*-
"""测试港股/美股/REITs替代数据源"""
import httpx
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/",
}

EM_DC = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# ========== 1. 港股IPO - 东方财富多个reportName尝试 ==========
print("=" * 60)
print("=== 港股IPO - 东方财富接口探测 ===")
for rn in ["RPT_HK_IPO_NEW", "RPTA_APP_IPOAPPLY_HK", "RPT_HK_IPOAPPLY", "RPT_IPO_HK_LIST"]:
    try:
        r = httpx.get(EM_DC, params={
            "reportName": rn,
            "columns": "ALL",
            "pageNumber": 1,
            "pageSize": 3,
            "source": "WEB",
            "client": "WEB",
        }, headers=HEADERS, timeout=10)
        d = r.json()
        code = d.get("returnCode", -1)
        msg = d.get("message", "")
        cnt = len(d.get("result", {}).get("data", []))
        print(f"  {rn}: code={code}, msg={msg}, count={cnt}")
        if cnt > 0:
            print(f"    sample: {json.dumps(d['result']['data'][0], ensure_ascii=False)[:200]}")
    except Exception as e:
        print(f"  {rn}: error - {e}")

# ========== 2. A股IPO filter尝试港股market code ==========
print("\n=== 港股 - 用A股接口filter市场代码 ===")
for mc in ["069001009", "069001010", "069001011", "069001005"]:
    try:
        r = httpx.get(EM_DC, params={
            "reportName": "RPTA_APP_IPOAPPLY",
            "columns": "ALL",
            "pageNumber": 1,
            "pageSize": 3,
            "source": "WEB",
            "client": "WEB",
            "filter": f"(TRADE_MARKET_CODE='{mc}')",
        }, headers=HEADERS, timeout=10)
        d = r.json()
        cnt = len(d.get("result", {}).get("data", []))
        msg = d.get("message", "")
        print(f"  market_code={mc}: count={cnt}, msg={msg}")
        if cnt > 0:
            print(f"    sample: {json.dumps(d['result']['data'][0], ensure_ascii=False)[:200]}")
    except Exception as e:
        print(f"  market_code={mc}: error - {e}")

# ========== 3. REITs - push2不同板块 ==========
print("\n=== REITs - push2不同板块代码 ===")
PUSH2 = "https://push2.eastmoney.com/api/qt/clist/get"
for fs in ["b:MK0404", "b:MK0405", "b:MK0401", "b:MK0402", "b:MK0411", "b:MK0420"]:
    try:
        r = httpx.get(PUSH2, params={
            "pn": 1, "pz": 50,
            "fs": fs,
            "fields": "f12,f14,f2,f3",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2, "invt": 2, "fid": "f3", "po": 1, "nc": 1,
        }, headers=HEADERS, timeout=10)
        d = r.json()
        diff = d.get("data", {}).get("diff", {})
        if isinstance(diff, dict):
            items = list(diff.values())
        else:
            items = diff if isinstance(diff, list) else []
        # 统计508开头的
        reits = [i for i in items if str(i.get("f12", "")).startswith("508")]
        print(f"  {fs}: total={len(items)}, reits(508)={len(reits)}")
        if reits:
            print(f"    sample: {json.dumps(reits[0], ensure_ascii=False)}")
    except Exception as e:
        print(f"  {fs}: error - {e}")

# ========== 4. NASDAQ IPO calendar ==========
print("\n=== 美股IPO - NASDAQ Calendar ===")
try:
    r = httpx.get("https://api.nasdaq.com/api/ipo/calendar", headers={
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "application/json",
        "Referer": "https://www.nasdaq.com/market-activity/ipos",
    }, timeout=15)
    print(f"  Status: {r.status_code}")
    d = r.json()
    print(f"  Keys: {list(d.keys())}")
    data = d.get("data", {})
    if data:
        print(f"  Data keys: {list(data.keys())}")
        # 检查是否有upcoming字段
        for k in ["upcoming", "priced", "filed"]:
            section = data.get(k, {})
            if isinstance(section, dict):
                print(f"  {k}: has keys {list(section.keys())[:10]}")
                rows = section.get("rows", [])
                if rows:
                    print(f"  {k}: {len(rows)} rows, sample: {json.dumps(rows[0], ensure_ascii=False)[:200]}")
            elif isinstance(section, list):
                print(f"  {k}: list with {len(section)} items")
except Exception as e:
    print(f"  Error: {e}")

# ========== 5. 东方财富新股申购页面（HTML解析） ==========
print("\n=== A股新股 - 东方财富网页HTML解析 ===")
try:
    from bs4 import BeautifulSoup
    r = httpx.get("https://data.eastmoney.com/xg/xg/default.html", headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    # 查找表格
    tables = soup.find_all("table")
    print(f"  找到 {len(tables)} 个表格")
    # 查找包含新股信息的元素
    for tag in soup.find_all(attrs={"class": True}):
        cls = " ".join(tag.get("class", []))
        if "ipo" in cls.lower() or "xg" in cls.lower() or "new" in cls.lower() or "申购" in str(tag.text)[:30]:
            print(f"  相关元素: <{tag.name} class='{cls}'> text={str(tag.text)[:80]}")
            if len([t for t in soup.find_all(attrs={"class": True}) if "申购" in str(t.text)[:30]]) > 5:
                break
except Exception as e:
    print(f"  Error: {e}")

print("\n=== 测试完成 ===")
