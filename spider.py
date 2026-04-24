# -*- coding: utf-8 -*-
"""IPO Tracker 数据爬虫
数据源：
- A股新股/北交所：东方财富 RPTA_APP_IPOAPPLY
- 可转债：东方财富 RPT_BOND_CB_LIST  
- 港股新股：东方财富港股频道HTML页面解析 (hk.eastmoney.com/ipolist.html)
- 美股新股：NASDAQ IPO Calendar API
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
    Returns:
        list: 数据列表
        None: 请求异常（网络错误等）
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
        print(f"[em] {report_name} page={page_number} error: {e}")
        return None  # 返回None表示请求异常


def _get_em_all(report_name, filter_str=None, sort_col=None, page_size=100, sort_order="desc", max_pages=5, max_retries=2):
    """东方财富 datacenter 翻页获取所有数据
    Args:
        max_retries: 每页最大重试次数
    """
    all_data = []
    for page in range(1, max_pages + 1):
        data = _get_em(report_name, filter_str, sort_col, page_size, sort_order, page)
        if data is None:
            # 首次失败，进入重试
            for retry in range(1, max_retries + 1):
                print(f"[em] {report_name} page={page} retry {retry}/{max_retries}")
                data = _get_em(report_name, filter_str, sort_col, page_size, sort_order, page)
                if data is not None:
                    break
        
        if data is None:
            # 重试全部失败，记录警告
            print(f"[em] {report_name} page={page} failed after {max_retries} retries, aborting")
            break
        if not data:
            # 空结果，正常结束
            break
        all_data.extend(data)
        if len(data) < page_size:
            break
    return all_data


# ==================== A股新股 ====================
def get_ipo_a(days=90, include_bj=False):
    """获取A股新股（沪深为主，可选包含北交所）
    Args:
        days: 查询天数
        include_bj: True时包含北交所，默认只返回沪深A股
    Returns:
        list: 每条数据带 market 字段，北交所为 "北交所"，沪深为 "主板"/"创业板"/"科创板"
    """
    start = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    data = _get_em_all("RPTA_APP_IPOAPPLY",
                       filter_str=f"(APPLY_DATE>='{start}')",
                       sort_col="APPLY_DATE", page_size=100, max_pages=5)
    result = []
    for item in data:
        is_bj = str(item.get("TRADE_MARKET_CODE", "")) == "069001017"
        if is_bj and not include_bj:
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
            "market": "北交所" if is_bj else item.get("MARKET", ""),
            "ld_open_premium": item.get("LD_OPEN_PREMIUM", ""),
        })
    return result


def get_ipo_china(days=90):
    """A股新股（含北交所），合并返回"""
    return get_ipo_a(days, include_bj=True)


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
    """港股新股 - 从东方财富港股IPO页面HTML解析
    数据源: http://hk.eastmoney.com/ipolist.html
    表格字段: 序号, 股票代码, 股票名称, 招股价, 招股数(股), 募集资金(港元), 招股日期, 上市日期
    """
    try:
        r = httpx.get("http://hk.eastmoney.com/ipolist.html",
                      headers=HEADERS, timeout=15, follow_redirects=True)
        if r.status_code != 200:
            print(f"[hk] page status={r.status_code}")
            return []

        text = r.text
        # 提取表格
        tables = re.findall(r'<table[^>]*>(.*?)</table>', text, re.DOTALL)
        if not tables:
            print("[hk] no table found in page")
            return []

        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tables[0], re.DOTALL)
        start = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = []

        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) < 7:
                continue
            # 清理HTML标签
            clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            # clean: [序号, 股票代码, 股票名称, 招股价, 招股数, 募集资金, 招股日期, 上市日期]
            code = clean[1]
            name = clean[2]
            price = clean[3]
            shares = clean[4]
            funds = clean[5]
            apply_date = clean[6]  # 招股日期
            listing_date = clean[7] if len(clean) > 7 else ""  # 上市日期

            # 跳过表头行
            if code == "股票代码" or not code or not name:
                continue

            # 按日期过滤
            date_check = listing_date or apply_date
            if date_check and date_check < start:
                continue

            result.append({
                "code": code,
                "name": name,
                "apply_date": apply_date,
                "listing_date": listing_date,
                "price": price,
                "shares": shares,
                "funds": funds,
                "market": "港交所",
            })

        return result
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
            priced = data.get("priced") or {}
            if priced:
                rows = priced.get("rows", []) if isinstance(priced, dict) else (priced or [])
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
            upcoming = data.get("upcoming") or {}
            if upcoming:
                rows = upcoming.get("rows", []) if isinstance(upcoming, dict) else (upcoming or [])
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



# ==================== 综合日历 ====================
def get_calendar(days=90):
    return {
        "A股新股": get_ipo_china(days),
        "可转债": get_cb_new(days),
        "港股新股": get_ipo_hk(days),
        "美股新股": get_ipo_us(days),
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
    d = get_ipo_a(180, include_bj=False)
    print(f"获取到 {len(d)} 条沪深A股（不含北交所）")
    d_bj = get_ipo_a(180, include_bj=True)
    bj_list = [x for x in d_bj if x.get("market") == "北交所"]
    print(f"获取到 {len(bj_list)} 条北交所")

    print("\n=== REITs ===")
    d = get_reits()
    print(f"获取到 {len(d)} 条")
    if d:
        print(json.dumps(d[:3], ensure_ascii=False, indent=2))
