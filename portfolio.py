# -*- coding: utf-8 -*-
"""持仓管理模块
支持功能：
- 持仓CRUD（股票代码、市场、股数、成本价）
- 多账户合并，摊薄成本价
- 浮动盈亏计算
"""
import json
import os
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "portfolio.json")

# 确保目录存在
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)


def _load():
    """加载持仓数据"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}


def _save(data):
    """保存持仓数据"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_portfolio(user_id="default"):
    """获取用户持仓"""
    data = _load()
    return data.get(user_id, [])


def add_position(user_id, stock_code, market, shares, cost_price, source="manual"):
    """添加持仓"""
    data = _load()
    if user_id not in data:
        data[user_id] = []
    
    # 检查是否已存在相同股票
    for p in data[user_id]:
        if p["stock_code"] == stock_code and p["market"] == market:
            # 合并：计算新的加权成本价
            total_shares = p["shares"] + shares
            if total_shares > 0:
                new_cost = (p["shares"] * p["cost_price"] + shares * cost_price) / total_shares
                p["shares"] = total_shares
                p["cost_price"] = round(new_cost, 4)
            else:
                p["shares"] = total_shares
            p["updated_at"] = datetime.now().isoformat()
            _save(data)
            return {"code": 0, "message": "已合并到现有持仓", "position": p}
    
    # 新增
    new_pos = {
        "id": len(data[user_id]) + 1,
        "stock_code": stock_code,
        "market": market,  # A股/港股/美股
        "shares": shares,
        "cost_price": cost_price,
        "source": source,  # manual/photo
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    data[user_id].append(new_pos)
    _save(data)
    return {"code": 0, "message": "添加成功", "position": new_pos}


def update_position(user_id, position_id, shares=None, cost_price=None):
    """更新持仓"""
    data = _load()
    if user_id not in data:
        return {"code": 1, "message": "用户不存在"}
    
    for p in data[user_id]:
        if p["id"] == position_id:
            if shares is not None:
                p["shares"] = shares
            if cost_price is not None:
                p["cost_price"] = cost_price
            p["updated_at"] = datetime.now().isoformat()
            _save(data)
            return {"code": 0, "message": "更新成功", "position": p}
    
    return {"code": 1, "message": "持仓不存在"}


def delete_position(user_id, position_id):
    """删除持仓"""
    data = _load()
    if user_id not in data:
        return {"code": 1, "message": "用户不存在"}
    
    data[user_id] = [p for p in data[user_id] if p["id"] != position_id]
    _save(data)
    return {"code": 0, "message": "删除成功"}


def merge_portfolio(user_id):
    """合并同一股票的多笔持仓，摊薄成本价"""
    data = _load()
    if user_id not in data:
        return {"code": 0, "data": []}
    
    # 按股票代码+市场分组合并
    merged = {}
    for p in data[user_id]:
        key = f"{p['market']}_{p['stock_code']}"
        if key not in merged:
            merged[key] = {
                "stock_code": p["stock_code"],
                "market": p["market"],
                "shares": 0,
                "cost_price": 0,
            }
        total_shares = merged[key]["shares"] + p["shares"]
        if total_shares > 0:
            merged[key]["cost_price"] = (merged[key]["shares"] * merged[key]["cost_price"] + p["shares"] * p["cost_price"]) / total_shares
        merged[key]["shares"] = total_shares
    
    result = list(merged.values())
    return {"code": 0, "data": result}