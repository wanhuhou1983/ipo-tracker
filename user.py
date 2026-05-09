# -*- coding: utf-8 -*-
"""用户管理模块

- 微信登录（jscode2session 换 openid）
- 关注/取消关注新股新债
"""

import logging
import os
from datetime import datetime

import httpx
import cache

logger = logging.getLogger("ipo-user")

WX_APP_ID = "wx89f7ecb44368d09a"
WX_APP_SECRET = os.environ.get("WX_APP_SECRET", "")

# ==================== 数据库初始化 ====================

def init_user_tables():
    """建用户表和关注表（幂等）"""
    conn = cache.get_conn()
    if conn is None:
        logger.warning("PG 不可用，用户模块降级")
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                openid VARCHAR(100) UNIQUE NOT NULL,
                nickname VARCHAR(100),
                avatar VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_follows (
                id SERIAL PRIMARY KEY,
                openid VARCHAR(100) NOT NULL REFERENCES users(openid),
                follow_type VARCHAR(10) NOT NULL,
                stock_code VARCHAR(20) NOT NULL,
                stock_name VARCHAR(100) NOT NULL,
                listing_date DATE,
                apply_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(openid, follow_type, stock_code)
            )
        """)
        cur.close()
        logger.info("用户表/关注表就绪")
        return True
    except Exception as e:
        logger.warning(f"建表失败: {e}")
        return False


# ==================== 微信登录 ====================

def wx_login(code: str):
    """用 wx.login() 返回的 code 换 openid

    Returns:
        dict: {"code": 0, "openid": "xxx"} 或
              {"code": 1, "message": "xxx"}
    """
    if not WX_APP_SECRET:
        return {"code": 1, "message": "未配置 WX_APP_SECRET 环境变量"}

    try:
        r = httpx.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={
                "appid": WX_APP_ID,
                "secret": WX_APP_SECRET,
                "js_code": code,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        d = r.json()
        if "openid" not in d:
            return {"code": 1, "message": f"登录失败: {d.get('errmsg', '未知错误')}"}

        openid = d["openid"]

        # upsert 用户
        conn = cache.get_conn()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO users (openid, last_login_at) VALUES (%s, CURRENT_TIMESTAMP) "
                    "ON CONFLICT (openid) DO UPDATE SET last_login_at = CURRENT_TIMESTAMP",
                    (openid,)
                )
                cur.close()
            except Exception as e:
                logger.warning(f"写入用户失败: {e}")

        return {"code": 0, "openid": openid}

    except Exception as e:
        logger.warning(f"微信登录请求失败: {e}")
        return {"code": 1, "message": f"网络错误: {e}"}


# ==================== 关注管理 ====================

def get_follows(openid: str):
    """获取用户关注列表"""
    conn = cache.get_conn()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, follow_type, stock_code, stock_name, "
            "to_char(listing_date, 'YYYY-MM-DD'), to_char(apply_date, 'YYYY-MM-DD'), "
            "created_at "
            "FROM user_follows WHERE openid = %s ORDER BY created_at DESC",
            (openid,)
        )
        rows = cur.fetchall()
        cur.close()
        return [
            {
                "id": r[0],
                "follow_type": r[1],
                "stock_code": r[2],
                "stock_name": r[3],
                "listing_date": r[4] or "",
                "apply_date": r[5] or "",
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"查关注列表失败: {e}")
        return []


def add_follow(openid: str, follow_type: str, stock_code: str,
               stock_name: str, listing_date="", apply_date=""):
    """添加关注（重复添加幂等返回成功）"""
    conn = cache.get_conn()
    if conn is None:
        return {"code": 1, "message": "数据库不可用"}
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO user_follows (openid, follow_type, stock_code, stock_name, listing_date, apply_date) "
            "VALUES (%s, %s, %s, %s, %s::date, %s::date) "
            "ON CONFLICT (openid, follow_type, stock_code) DO NOTHING",
            (openid, follow_type, stock_code, stock_name,
             listing_date or None, apply_date or None)
        )
        cur.close()
        return {"code": 0, "message": "关注成功"}
    except Exception as e:
        logger.warning(f"添加关注失败: {e}")
        return {"code": 1, "message": f"添加失败: {e}"}


def remove_follow(openid: str, follow_id: int):
    """取消关注"""
    conn = cache.get_conn()
    if conn is None:
        return {"code": 1, "message": "数据库不可用"}
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM user_follows WHERE id = %s AND openid = %s",
            (follow_id, openid)
        )
        deleted = cur.rowcount
        cur.close()
        if deleted:
            return {"code": 0, "message": "已取消关注"}
        return {"code": 1, "message": "关注记录不存在"}
    except Exception as e:
        logger.warning(f"取消关注失败: {e}")
        return {"code": 1, "message": f"操作失败: {e}"}


def is_followed(openid: str, follow_type: str, stock_code: str) -> bool:
    """检查是否已关注（供前端卡片渲染用）"""
    conn = cache.get_conn()
    if conn is None:
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM user_follows WHERE openid = %s AND follow_type = %s AND stock_code = %s",
            (openid, follow_type, stock_code)
        )
        row = cur.fetchone()
        cur.close()
        return row is not None
    except Exception as e:
        logger.warning(f"查关注状态失败: {e}")
        return False
