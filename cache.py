# -*- coding: utf-8 -*-
"""IPO数据 PG 缓存层

自动建表、缓存读写，爬虫数据可复用，页面秒开。
PG 不可用时自动降级为实时抓取，不抛异常。
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("ipo-cache")

# PG 连接参数（环境变量可覆盖）
PG_CONFIG = {
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": int(os.environ.get("PG_PORT", "5432")),
    "user": os.environ.get("PG_USER", "postgres"),
    "password": os.environ.get("PG_PASSWORD", "linhu50115"),
    "dbname": os.environ.get("PG_DATABASE", "postgres"),
}

_conn = None


def _get_conn():
    """惰性获取 PG 连接"""
    global _conn
    if _conn is not None:
        try:
            # 轻量探活
            cur = _conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return _conn
        except Exception:
            _conn = None

    try:
        import psycopg2
        _conn = psycopg2.connect(**PG_CONFIG)
        _conn.autocommit = True
        return _conn
    except Exception as e:
        logger.warning(f"PG 连接失败，将降级为实时抓取: {e}")
        return None


def get_conn():
    """公开接口：获取 PG 连接（供 user.py 等模块复用）"""
    return _get_conn()


def init_cache():
    """初始化缓存表（幂等，多次调用安全）"""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ipo_cache (
                cache_key VARCHAR(100) PRIMARY KEY,
                data JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.close()
        logger.info("缓存表 ipo_cache 就绪")
        return True
    except Exception as e:
        logger.warning(f"建表失败: {e}")
        return False


def get_cached(key: str, ttl_minutes: int = 30):
    """读取缓存，过期返回 None"""
    conn = _get_conn()
    if conn is None:
        return None
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT data, updated_at FROM ipo_cache WHERE cache_key = %s",
            (key,)
        )
        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        data_raw, updated_at = row
        # 判断过期
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - updated_at > timedelta(minutes=ttl_minutes):
            return None
        # JSONB 返回的是 dict/list，直接返回
        return data_raw
    except Exception as e:
        logger.warning(f"读缓存失败: {e}")
        return None


def set_cache(key: str, data) -> bool:
    """写入缓存（UPSERT）"""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        # 确保 data 是 JSON 可序列化结构
        data_json = json.dumps(data, ensure_ascii=False, default=str)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ipo_cache (cache_key, data, updated_at) VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP) "
            "ON CONFLICT (cache_key) DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP",
            (key, data_json, data_json)
        )
        cur.close()
        return True
    except Exception as e:
        logger.warning(f"写缓存失败: {e}")
        return False


def with_cache(key_prefix: str, ttl_minutes: int, func, *args):
    """通用缓存包装器

    1. 尝试读缓存（有效期内）→ 命中则直接返回
    2. 未命中 → 调用 func(*args) 获取数据
    3. 写入缓存（失败不阻塞）
    4. 返回数据
    """
    # 构造缓存 key
    cache_key = f"{key_prefix}_{'_'.join(str(a) for a in args)}"

    # 1. 读缓存
    cached = get_cached(cache_key, ttl_minutes)
    if cached is not None:
        logger.info(f"缓存命中: {cache_key}")
        return cached

    # 2. 调用原始函数
    logger.info(f"缓存未命中，实时抓取: {cache_key}")
    data = func(*args)

    # 3. 异步写入缓存（非阻塞）
    if data is not None:
        set_cache(cache_key, data)

    return data
