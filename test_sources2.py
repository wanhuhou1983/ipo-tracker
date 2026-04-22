# -*- coding: utf-8 -*-
"""精确测试美股IPO和REITs数据源"""
import httpx
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://www.nasdaq.com/market-activity/ipos",
}

# ========== 1. NASDAQ IPO - 完整数据结构 ==========
print("=" * 60)
print("=== 美股IPO - NASDAQ完整数据 ===")
try:
    r = httpx.get("https://api.nasdaq.com/api/ipo/calendar", headers=HEADERS, timeout=15)
    d = r.json()
    data = d.get("data", {})
    
    # priced (已上市)
    priced_rows = data.get("priced", {}).get("rows", [])
    print(f"\n[priced] 已上市: {len(priced_rows)} 条")
    if priced_rows:
        print(json.dumps(priced_rows[0], ensure_ascii=False, indent=2))
    
    # upcoming 
    upcoming_data = data.get("upcoming", {}).get("upcomingTable", {})
    upcoming_rows = upcoming_data.get("rows", []) if isinstance(upcoming_data, dict) else []
    print(f"\n[upcoming] 即将上市: {len(upcoming_rows)} 条")
    if upcoming_rows:
        print(json.dumps(upcoming_rows[0], ensure_ascii=False, indent=2))
    
    # filed (已申报)
    filed_rows = data.get("filed", {}).get("rows", [])
    print(f"\n[filed] 已申报: {len(filed_rows)} 条")
    if filed_rows:
        print(json.dumps(filed_rows[0], ensure_ascii=False, indent=2))
        
except Exception as e:
    import traceback
    traceback.print_exc()

# ========== 2. REITs - 尝试直接用证券代码前缀搜索 ==========
print("\n" + "=" * 60)
print("=== REITs - 东方财富基金行情 ===")
PUSH2 = "https://push2.eastmoney.com/api/qt/clist/get"

# 方案A: 场内基金板块
for fs, desc in [
    ("b:MK0404", "LOF"),
    ("b:MK0403", "ETF"),
    ("b:MK0406", "封闭式"),
    ("b:MK0410", "分级基金"),
]:
    try:
        r = httpx.get(PUSH2, params={
            "pn": 1, "pz": 500,
            "fs": fs,
            "fields": "f12,f14,f2,f3",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2, "invt": 2, "fid": "f12", "po": 1, "nc": 1,
        }, headers=HEADERS, timeout=10)
        d = r.json()
        diff = d.get("data", {}).get("diff", {})
        if isinstance(diff, dict):
            items = list(diff.values())
        else:
            items = diff if isinstance(diff, list) else []
        reits = [i for i in items if str(i.get("f12", "")).startswith("508")]
        if reits:
            print(f"  {fs}({desc}): 找到 {len(reits)} 个REITs!")
            for r_item in reits[:3]:
                print(f"    {r_item.get('f12')} {r_item.get('f14')} 价格={r_item.get('f2')}")
        else:
            # 看看有什么代码
            codes = [str(i.get("f12",""))[:3] for i in items[:20]]
            print(f"  {fs}({desc}): 无REITs, 代码前缀样例: {set(codes)}")
    except Exception as e:
        print(f"  {fs}: error - {e}")

# 方案B: 直接用代码段搜索REITs
print("\n=== REITs - 用证券代码段搜索 ===")
try:
    r = httpx.get(PUSH2, params={
        "pn": 1, "pz": 100,
        "fs": "m:0+t:8+f:!2,m:0+t:23+f:!2,m:1+t:23+f:!2",  # 基金
        "fields": "f12,f14,f2,f3",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2, "invt": 2, "fid": "f12", "po": 1, "nc": 1,
    }, headers=HEADERS, timeout=10)
    d = r.json()
    diff = d.get("data", {}).get("diff", {})
    if isinstance(diff, dict):
        items = list(diff.values())
    else:
        items = diff if isinstance(diff, list) else []
    reits = [i for i in items if str(i.get("f12", "")).startswith("508")]
    print(f"  基金搜索: total={len(items)}, reits(508)={len(reits)}")
    if reits:
        for r_item in reits[:5]:
            print(f"    {r_item.get('f12')} {r_item.get('f14')}")
except Exception as e:
    print(f"  error: {e}")

# 方案C: 直接搜索508开头
print("\n=== REITs - 直接指定508代码段 ===")
try:
    r = httpx.get(PUSH2, params={
        "pn": 1, "pz": 100,
        "fs": "m:0+t:8+f:!2,m:0+t:6+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2",
        "fields": "f12,f14,f2,f3",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2, "invt": 2, "fid": "f12", "po": 1, "nc": 1,
    }, headers=HEADERS, timeout=10)
    d = r.json()
    diff = d.get("data", {}).get("diff", {})
    if isinstance(diff, dict):
        items = list(diff.values())
    else:
        items = diff if isinstance(diff, list) else []
    reits_508 = [i for i in items if str(i.get("f12", "")).startswith("508")]
    reits_180 = [i for i in items if str(i.get("f12", "")).startswith("180")]
    print(f"  总计={len(items)}, 508开头={len(reits_508)}, 180开头={len(reits_180)}")
    # 看看代码分布
    prefixes = {}
    for i in items:
        code = str(i.get("f12", ""))[:3]
        prefixes[code] = prefixes.get(code, 0) + 1
    top5 = sorted(prefixes.items(), key=lambda x: -x[1])[:10]
    print(f"  代码前缀TOP10: {top5}")
except Exception as e:
    print(f"  error: {e}")

# ========== 3. 港股 - 东方财富港股新股中心API ==========
print("\n" + "=" * 60)
print("=== 港股 - 东方财富API探测 ===")
try:
    # 尝试港股datacenter不同reportName
    rnames = ["RPT_HK_IPONEW", "RPT_HK_IPO_NEW", "RPT_HK_IPOAPPLY",
              "RPTA_HK_IPO_LIST", "RPTA_HK_IPO", "RPT_HK_IPO_LIST",
              "HK_IPO_LIST", "RPTA_WEB_HK_IPO"]
    for rn in rnames:
        try:
            r = httpx.get("https://datacenter-web.eastmoney.com/api/data/v1/get", params={
                "reportName": rn,
                "columns": "ALL",
                "pageNumber": 1,
                "pageSize": 3,
                "source": "WEB",
                "client": "WEB",
            }, headers={
                **HEADERS,
                "Referer": "https://www.eastmoney.com/",
            }, timeout=10)
            d = r.json()
            result = d.get("result")
            if result and result.get("data"):
                cnt = len(result["data"])
                print(f"  {rn}: ✅ {cnt} 条!")
                print(f"    sample: {json.dumps(result['data'][0], ensure_ascii=False)[:200]}")
            else:
                msg = d.get("message", "no message")
                print(f"  {rn}: ❌ {msg}")
        except Exception as e:
            print(f"  {rn}: error - {e}")
except Exception as e:
    print(f"  error: {e}")

# 方案B: 东方财富港股IPO数据接口（不同域名）
print("\n=== 港股 - 东方财富港股中心 ===")
hk_urls = [
    "https://quote.eastmoney.com/center/boardlist.html#hk_ipo",
    "https://data.eastmoney.com/hk/ipo/",
]
for url in hk_urls:
    try:
        r = httpx.get(url, headers=HEADERS, timeout=10)
        print(f"  {url}: status={r.status_code}, len={len(r.text)}")
    except Exception as e:
        print(f"  {url}: error - {e}")

print("\n=== 测试完成 ===")
