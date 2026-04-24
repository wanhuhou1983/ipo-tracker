"""

IPO Tracker - 新股/可转债 一站式查询
轻量级FastAPI服务，数据从东方财富/NASDAQ实时抓取

"""
import spider
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI(title="IPO Tracker", version="2.0.0")
# CORS: 限制为本机访问（配合nginx反代时使用127.0.0.1）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
static_dir = os.path.join(os.path.dirname(__file__), "web")
if os.path.isdir(static_dir):
    app.mount("/web", StaticFiles(directory=static_dir), name="web")


# ==================== API 接口 ====================
@app.get("/")
async def root():
    """前端页面"""
    index = os.path.join(static_dir, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "IPO Tracker API", "version": "2.0.0"}


@app.get("/api/cb/new")
async def api_cb(days: int = Query(90, ge=1, le=365)):
    """可转债"""
    data = spider.get_cb_new(days)
    return {"code": 0, "data": data, "total": len(data)}


@app.get("/api/ipo/china")
async def api_china(days: int = Query(90, ge=1, le=365)):
    """A股新股（含北交所）"""
    data = spider.get_ipo_china(days)
    return {"code": 0, "data": data, "total": len(data)}


@app.get("/api/ipo/hk")
async def api_hk(days: int = Query(90, ge=1, le=365)):
    """港股新股"""
    data = spider.get_ipo_hk(days)
    return {"code": 0, "data": data, "total": len(data)}


@app.get("/api/ipo/us")
async def api_us(days: int = Query(90, ge=1, le=365)):
    """美股新股"""
    data = spider.get_ipo_us(days)
    return {"code": 0, "data": data, "total": len(data)}





@app.get("/api/calendar")
async def api_calendar(days: int = Query(90, ge=1, le=365)):
    """综合日历"""
    data = spider.get_calendar(days)
    return {"code": 0, "data": data}


@app.get("/app")
async def app_page():
    """前端页面入口（兼容旧链接）"""
    index = os.path.join(static_dir, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "前端页面未找到", "hint": "请检查 web/index.html 是否存在"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
