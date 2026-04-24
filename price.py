# -*- coding: utf-8 -*-
"""实时行情获取模块
用于计算浮动盈亏
"""
import httpx
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}


def get_price_ah(stock_code):
    """获取A股/港股实时价格
    Args:
        stock_code: 股票代码，如 000001（A股）、00700（港股）
    Returns:
        dict: {price, change_pct}
    """
    # A股：沪市600/601/688开头，深市000/001/002/003开头
    # 港股：5位数字
    is_hk = len(stock_code) == 5 or (len(stock_code) == 4 and stock_code.isdigit())
    
    if is_hk:
        # 港股
        return _get_hk_price(stock_code)
    else:
        # A股
        return _get_a_stock_price(stock_code)


def _get_a_stock_price(stock_code):
    """获取A股价格"""
    # 判断交易所
    if stock_code.startswith(("600", "601", "603", "605", "688")):
        secid = f"1.{stock_code}"
    elif stock_code.startswith(("000", "001", "002", "003", "300")):
        secid = f"0.{stock_code}"
    else:
        return None
    
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "invt": "2",
            "fltt": "2",
            "fields": "f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,f57,f58,f59,f60,f116,f117,f162,f167,f168,f169,f170,f171,f173,f177",
            "secid": secid,
            "_": "1621834887000",
        }
        r = httpx.get(url, params=params, headers=HEADERS, timeout=10)
        d = r.json()
        data = d.get("data", {})
        if data:
            price = data.get("f43")  # 最新价
            if price:
                price = price / 100  # 东财价格单位是分
                change = data.get("f170")  # 涨跌幅
                return {"price": price, "change_pct": change}
    except Exception as e:
        print(f"[a-stock] {stock_code} error: {e}")
    return None


def _get_hk_price(stock_code):
    """获取港股价格"""
    try:
        # 港股代码前面加0
        hk_code = stock_code.zfill(5)
        url = f"https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "invt": "2",
            "fltt": "2",
            "fields": "f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,f57,f58,f59,f60,f116,f117,f162,f167,f168,f169,f170,f171,f173,f177",
            "secid": f"116.{hk_code}",
            "_": "1621834887000",
        }
        r = httpx.get(url, params=params, headers=HEADERS, timeout=10)
        d = r.json()
        data = d.get("data", {})
        if data:
            price = data.get("f43")
            if price:
                price = price / 100
                change = data.get("f170")
                return {"price": price, "change_pct": change}
    except Exception as e:
        print(f"[hk-stock] {stock_code} error: {e}")
    return None


def get_price_us(stock_code):
    """获取美股实时价格
    Args:
        stock_code: 美股代码，如 AAPL, TSLA
    Returns:
        dict: {price, change_pct}
    """
    try:
        url = "https://stock.us.eastmoney.com/api/qt/stock/get"
        params = {
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "invt": "2",
            "fltt": "2",
            "fields": "f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,f57,f58,f59,f60,f116,f117,f162,f167,f168,f169,f170,f171,f173,f177",
            "secid": f"105.{stock_code}",
        }
        r = httpx.get(url, params=params, headers=HEADERS, timeout=10)
        d = r.json()
        data = d.get("data", {})
        if data:
            price = data.get("f43")
            if price:
                price = price / 100
                change = data.get("f170")
                return {"price": price, "change_pct": change}
    except Exception as e:
        print(f"[us-stock] {stock_code} error: {e}")
    return None


def get_price(stock_code, market):
    """统一获取价格接口"""
    if market == "美股":
        return get_price_us(stock_code)
    else:
        return get_price_ah(stock_code)


def calculate_pnl(portfolio):
    """计算持仓浮动盈亏
    Args:
        portfolio: 合并后的持仓列表
    Returns:
        dict: 按A股/港股/美股分组的盈亏数据
    """
    result = {
        "A股": {"positions": [], "total_pnl": 0, "total_market_value": 0},
        "港股": {"positions": [], "total_pnl": 0, "total_market_value": 0},
        "美股": {"positions": [], "total_pnl": 0, "total_market_value": 0},
    }
    
    for pos in portfolio:
        market = pos.get("market", "A股")
        stock_code = pos.get("stock_code")
        shares = pos.get("shares", 0)
        cost_price = pos.get("cost_price", 0)
        
        if shares <= 0:
            continue
        
        # 获取实时价格
        price_info = get_price(stock_code, market)
        current_price = price_info["price"] if price_info else cost_price
        change_pct = price_info.get("change_pct", 0) if price_info else 0
        
        # 计算盈亏
        market_value = shares * current_price
        cost_value = shares * cost_price
        pnl = market_value - cost_value
        pnl_pct = (pnl / cost_value * 100) if cost_value > 0 else 0
        
        result[market]["positions"].append({
            "stock_code": stock_code,
            "shares": shares,
            "cost_price": cost_price,
            "current_price": current_price,
            "market_value": round(market_value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "change_pct": round(change_pct, 2),
        })
        result[market]["total_pnl"] += pnl
        result[market]["total_market_value"] += market_value
    
    # 汇总
    result["A股"]["total_pnl"] = round(result["A股"]["total_pnl"], 2)
    result["A股"]["total_market_value"] = round(result["A股"]["total_market_value"], 2)
    result["港股"]["total_pnl"] = round(result["港股"]["total_pnl"], 2)
    result["港股"]["total_market_value"] = round(result["港股"]["total_market_value"], 2)
    result["美股"]["total_pnl"] = round(result["美股"]["total_pnl"], 2)
    result["美股"]["total_market_value"] = round(result["美股"]["total_market_value"], 2)
    
    return result