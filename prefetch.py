#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定时预取脚本：将爬虫数据写入 PG 缓存，供 API 读取。

用法：
    python prefetch.py                     # 爬取全部数据
    python prefetch.py --china             # 只爬A股
    python prefetch.py --cb                # 只爬可转债
    python prefetch.py --hk                # 只爬港股
    python prefetch.py --us                # 只爬美股

建议 cron 配置（每日8:00和14:00各跑一次）：
    0 8,14 * * * cd /opt/ipo-tracker && ./venv/bin/python prefetch.py >> /var/log/ipo-prefetch.log 2>&1
"""

import sys
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("prefetch")

sys.path.insert(0, ".")
import spider
import cache


def prefetch_one(name: str, func, days: int = 120, ttl: int = 480):
    """爬取单个数据源并写入缓存"""
    cache_key = f"{name}_{days}"
    logger.info(f"开始爬取: {name} (days={days})")
    start = time.time()

    try:
        data = func(days)
        elapsed = time.time() - start
        count = len(data) if data else 0
        logger.info(f"爬取完成: {name} → {count}条, 耗时{elapsed:.1f}s")

        # 写入 PG 缓存
        ok = cache.set_cache(cache_key, data)
        if ok:
            logger.info(f"缓存写入成功: {cache_key}")
        else:
            logger.warning(f"缓存写入失败: {cache_key}（PG不可用？）")

        return data
    except Exception as e:
        logger.error(f"爬取失败 {name}: {e}")
        return None


def main():
    # 初始化缓存表
    cache.init_cache()

    tasks = []

    # 解析命令行参数
    args = set(sys.argv[1:]) if len(sys.argv) > 1 else {"--all"}
    do_all = "--all" in args or len(args) == 0

    if do_all or "--china" in args:
        tasks.append(("china", spider.get_ipo_china, 120, 480))
    if do_all or "--cb" in args:
        tasks.append(("cb", spider.get_cb_new, 120, 480))
    if do_all or "--hk" in args:
        tasks.append(("hk", spider.get_ipo_hk, 120, 480))
    if do_all or "--us" in args:
        tasks.append(("us", spider.get_ipo_us, 120, 480))

    if not tasks:
        logger.warning("没有指定爬取任务，使用 --all / --china / --cb / --hk / --us")
        return

    total_start = time.time()
    results = []
    for name, func, days, ttl in tasks:
        data = prefetch_one(name, func, days, ttl)
        results.append((name, len(data) if data else 0))

    total_elapsed = time.time() - total_start
    summary = " | ".join(f"{n}:{c}条" for n, c in results)
    logger.info(f"全部完成 [{summary}] 总耗时{total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
