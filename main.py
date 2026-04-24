"""

IPO Tracker - 新股/可转债 一站式查询
轻量级FastAPI服务，数据从东方财富/NASDAQ实时抓取

"""
import spider
import portfolio
import price
import recognize
from fastapi import FastAPI, Query, Body, UploadFile, File
from pydantic import BaseModel
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


# ==================== 持仓管理接口 ====================

class PositionInput(BaseModel):
    user_id: str = "default"
    stock_code: str
    market: str  # A股/港股/美股
    shares: float
    cost_price: float
    source: str = "manual"


@app.get("/api/portfolio")
async def get_portfolio(user_id: str = "default"):
    """获取用户持仓（合并后）"""
    merged = portfolio.merge_portfolio(user_id)
    # 计算盈亏
    pnl_data = price.calculate_pnl(merged.get("data", []))
    return {"code": 0, "data": pnl_data}


@app.post("/api/portfolio")
async def add_position(pos: PositionInput):
    """添加持仓"""
    return portfolio.add_position(
        pos.user_id, pos.stock_code, pos.market, 
        pos.shares, pos.cost_price, pos.source
    )


@app.put("/api/portfolio/{position_id}")
async def update_position(position_id: int, user_id: str = "default", shares: float = None, cost_price: float = None):
    """更新持仓"""
    return portfolio.update_position(user_id, position_id, shares, cost_price)


@app.delete("/api/portfolio/{position_id}")
async def delete_position(position_id: int, user_id: str = "default"):
    """删除持仓"""
    return portfolio.delete_position(user_id, position_id)


@app.get("/api/price/{market}/{stock_code}")
async def get_stock_price(market: str, stock_code: str):
    """获取实时股价"""
    p = price.get_price(stock_code, market)
    if p:
        return {"code": 0, "data": p}
    return {"code": 1, "message": "获取价格失败"}


# ==================== 照片识别接口 ====================

@app.post("/api/recognize")
async def recognize_image(
    file: UploadFile = File(...),
    user_id: str = "default"
):
    """上传图片识别持仓"""
    import base64
    image_bytes = await file.read()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    
    result = recognize.recognize_holdings(image_b64, user_id)
    return result


@app.get("/api/recognize/status")
async def check_recognize_status():
    """检查识别服务状态"""
    import os
    api_key = os.environ.get("SILICONFLOW_API_KEY", "")
    if api_key:
        return {"code": 0, "status": "ready", "message": "API已配置"}
    return {"code": 1, "status": "not_configured", "message": "请配置SILICONFLOW_API_KEY"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
