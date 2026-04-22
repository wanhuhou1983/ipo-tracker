# -*- coding: utf-8 -*-
"""IPO Tracker 数据爬虫 - 最终版
数据源：
- A股新股/北交所：东方财富 RPTA_APP_IPOAPPLY
- 可转债：东方财富 RPT_BOND_CB_LIST  
- 港股新股：富途港股IPO页面
- 美股新股：NASDAQ IPO Calendar API
- REITs：东方财富基金代码库（fundcode_search.js）
"""
import httpx
import json
import re
from datetime import date, timedelta

EM_DC = "https://datacenter-web.eastmoney.com/api/data/v1/get"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/",
}


def _clean_date(s):
    """2026-01-01 00:00:00 -> 2026-01-01"""
    if s and isinstance(s, str):
        return s.replace(" 00:00:00", "").replace(" 00:00:00.000", "")[:10]
    return ""


def _get_em(report_name, filter_str=None, sort_col=None, page_size=50, sort_order="desc", page_number=1):
    """东方财富 datacenter 通用请求
    Args:
        page_number: 页码，从1开始
    """
    params = {
        "reportName": report_name,
        "columns": "ALL",
        "pageNumber": page_number, "pageSize": page_size,
        "source": "WEB", "client": "WEB",
    }
    if filter_str:
        params["filter"] = filter_str
    if sort_col:
        params["sortColumns"] = sort_col
        params["sortOrder"] = sort_order
    try:
        r = httpx.get(EM_DC, params=params, headers=HEADERS, timeout=15)
        d = r.json()
        return d.get("result", {}).get("data", []) or []
    except Exception as e:
        print(f"[em] {report_name} error: {e}")
        return []


def _get_em_all(report_name, filter_str=None, sort_col=None, page_size=100, sort_order="desc", max_pages=5):
    """东方财富 datacenter 翻页获取所有数据"""
    all_data = []
    for page in range(1, max_pages + 1):
        data = _get_em(report_name, filter_str, sort_col, page_size, sort_order, page)
        if not data:
            break
        all_data.extend(data)
        if len(data) < page_size:
            break
    return all_data


# ==================== A股新股 ====================
def get_ipo_a(days=90, bj=False):
    """统一获取A股/北交所新股
    Args:
        days: 查询天数
        bj: True返回北交所，False返回沪深A股
    """
    start = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    data = _get_em_all("RPTA_APP_IPOAPPLY",
                       filter_str=f"(APPLY_DATE>='{start}')",
                       sort_col="APPLY_DATE", page_size=100, max_pages=5)
    result = []
    for item in data:
        is_bj = str(item.get("TRADE_MARKET_CODE", "")) == "069001017"
        if bj != is_bj:
            continue
        result.append({
            "ts_code": item.get("SECUCODE", ""),
            "code": item.get("SECURITY_CODE", ""),
            "name": item.get("SECURITY_NAME_ABBR", ""),
            "apply_code": item.get("APPLY_CODE", ""),
            "apply_date": _clean_date(item.get("APPLY_DATE", "")),
            "listing_date": _clean_date(item.get("LISTING_DATE", "")),
            "online_issue_date": _clean_date(item.get("ONLINE_ISSUE_DATE", "")),
            "price": item.get("ISSUE_PRICE", ""),
            "pe": item.get("AFTER_ISSUE_PE", ""),
            "amount": item.get("ISSUE_NUM", ""),
            "funds": item.get("TOTAL_RAISE_FUNDS", ""),
            "ballot": item.get("BALLOT_NUM", ""),
            "market": item.get("MARKET", ""),
            "ld_open_premium": item.get("LD_OPEN_PREMIUM", ""),
        })
    return result


def get_ipo_china(days=90):
    """沪深A股新股（兼容旧接口）"""
    return get_ipo_a(days, bj=False)


# ==================== 可转债 ====================
def get_cb_new(days=90):
    start = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    data = _get_em_all("RPT_BOND_CB_LIST",
                       filter_str=f"(LISTING_DATE>='{start}')",
                       sort_col="LISTING_DATE", page_size=100, max_pages=3)
    result = []
    for item in data:
        result.append({
            "ts_code": item.get("SECUCODE", ""),
            "code": item.get("SECURITY_CODE", ""),
            "name": item.get("SECURITY_NAME_ABBR", ""),
            "stock_code": item.get("CONVERT_STOCK_CODE", ""),
            "stock_name": item.get("SECURITY_SHORT_NAME", ""),
            "listing_date": _clean_date(item.get("LISTING_DATE", "")),
            "value_date": _clean_date(item.get("VALUE_DATE", "")),
            "price": item.get("ISSUE_PRICE", ""),
            "size": item.get("ACTUAL_ISSUE_SCALE", ""),
            "rating": item.get("RATING", ""),
            "premium": item.get("TRANSFER_PREMIUM_RATIO", ""),
            "convert_price": item.get("INITIAL_TRANSFER_PRICE", ""),
        })
    return result


# ==================== 港股新股 ====================
def get_ipo_hk(days=90):
    try:
        r = httpx.get("https://www.futunn.com/quote/ipo-hk",
                      headers={**HEADERS, "Referer": "https://www.futunn.com/"},
                      timeout=15, follow_redirects=True)
        if r.status_code == 200 and len(r.text) > 1000:
            # 从SSR数据中提取
            patterns = [
                r'"ipoList"\s*:\s*(\[.*?\])',
                r'"ipoData"\s*:\s*(\[.*?\])',
                r'"list"\s*:\s*(\[.*?\])',
            ]
            for pattern in patterns:
                match = re.search(pattern, r.text, re.S)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        result = []
                        for item in data[:50]:
                            code = item.get("stockCode", item.get("code", item.get("symbol", "")))
                            name = item.get("stockName", item.get("name", item.get("companyName", "")))
                            if not name:
                                continue
                            result.append({
                                "code": str(code),
                                "name": str(name),
                                "ipo_date": str(item.get("listingDate", item.get("pricingDate", item.get("expectedDate", ""))))[:10],
                                "price_min": item.get("priceMin", item.get("priceRange", "")),
                                "price_max": item.get("priceMax", ""),
                                "market": "港交所",
                            })
                        if result:
                            return result
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
                        print(f"[hk] JSON parse error: {e}")
    except Exception as e:
        print(f"[hk] error: {e}")
    return []


# ==================== 美股新股 ====================
def get_ipo_us(days=90):
    try:
        r = httpx.get("https://api.nasdaq.com/api/ipo/calendar",
                      headers={"User-Agent": HEADERS["User-Agent"], "Accept": "application/json"},
                      timeout=15)
        if r.status_code == 200:
            d = r.json()
            data = d.get("data") or {}
            if not data:
                return []
            result = []
            # 已上市 - priced可能是dict或list
            priced = data.get("priced")
            if priced:
                rows = priced.get("rows") if isinstance(priced, dict) else priced
                if rows:
                    for item in (rows or [])[:30]:
                        if not item:
                            continue
                        result.append({
                            "symbol": item.get("proposedTickerSymbol", item.get("symbol", "")),
                            "name": item.get("companyName", ""),
                            "ipo_date": str(item.get("pricedDate", ""))[:10],
                            "price": item.get("proposedSharePrice", item.get("price", "")),
                            "exchange": item.get("proposedExchange", item.get("exchange", "")),
                            "shares": item.get("sharesOffered", ""),
                            "dollar_value": item.get("dollarValueOfSharesOffered", ""),
                            "status": "已上市",
                        })
            # 即将上市
            upcoming = data.get("upcoming")
            if upcoming:
                rows = upcoming.get("rows") if isinstance(upcoming, dict) else upcoming
                if rows:
                    for item in (rows or [])[:30]:
                        if not item:
                            continue
                        result.append({
                            "symbol": item.get("proposedTickerSymbol", item.get("symbol", "")),
                            "name": item.get("companyName", ""),
                            "ipo_date": str(item.get("expectedPriceDate", item.get("expectedDate", "")))[:10],
                            "price": item.get("priceRange", ""),
                            "exchange": item.get("proposedExchange", item.get("exchange", "")),
                            "shares": item.get("sharesOffered", ""),
                            "dollar_value": item.get("dollarValueOfSharesOffered", ""),
                            "status": "待上市",
                        })
            return result
    except Exception as e:
        print(f"[us] error: {e}")
    return []


# ==================== 北交所新股 ====================
def get_ipo_bj(days=180):
    """北交所新股（使用合并后的get_ipo_a）"""
    return get_ipo_a(days, bj=True)


# ==================== REITs ====================
def get_reits(days=None):
    """获取REITs列表，days参数已废弃（基金代码库无日期信息）"""
    try:
        r = httpx.get("https://fund.eastmoney.com/js/fundcode_search.js",
                      headers=HEADERS, timeout=15)
        # 解析基金列表，筛选REITs
        items = re.findall(r'\["(\d+)",\s*"([^"]+)",\s*"([^"]*)"', r.text)
        result = []
        for code, name, pinyin in items:
            # 筛选中国公募REITs：代码508开头 或 180开头且名称含REIT
            pinyin_upper = pinyin.upper()
            name_upper = name.upper()
            is_reit = code.startswith("508") or (code.startswith("180") and "REIT" in pinyin_upper)
            # 增加名称二次校验，避免误筛
            is_reit = is_reit or ("REIT" in name_upper and (code.startswith("508") or code.startswith("180")))
            if is_reit:
                result.append({
                    "code": code,
                    "name": name,
                    "type": "公募REITs",
                })
        return result
    except Exception as e:
        print(f"[reits] error: {e}")
        return []


# ==================== 综合日历 ====================
def get_calendar(days=90):
    return {
        "A股新股": get_ipo_china(days),
        "可转债": get_cb_new(days),
        "港股新股": get_ipo_hk(days),
        "美股新股": get_ipo_us(days),
        "北交所": get_ipo_bj(days),
        "REITs": get_reits(),
    }


if __name__ == "__main__":
    print("=== A股新股 ===")
    d = get_ipo_china(90)
    print(f"获取到 {len(d)} 条")

    print("\n=== 可转债 ===")
    d = get_cb_new(90)
    print(f"获取到 {len(d)} 条")

    print("\n=== 港股新股 ===")
    d = get_ipo_hk(90)
    print(f"获取到 {len(d)} 条")
    if d:
        print(json.dumps(d[0], ensure_ascii=False, indent=2))

    print("\n=== 美股新股 ===")
    d = get_ipo_us(90)
    print(f"获取到 {len(d)} 条")
    if d:
        print(json.dumps(d[0], ensure_ascii=False, indent=2))

    print("\n=== 北交所 ===")
    d = get_ipo_bj(180)
    print(f"获取到 {len(d)} 条")

    print("\n=== REITs ===")
    d = get_reits()
    print(f"获取到 {len(d)} 条")
    if d:
        print(json.dumps(d[:3], ensure_ascii=False, indent=2))
