# -*- coding: utf-8 -*-
"""照片识别模块
使用硅基流动(DeepSeek-VL2)识别券商截图中的持仓信息
"""
import base64
import httpx
import json
import os

# 硅基流动API Key（需要用户配置）
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")

# API地址
SF_API_URL = "https://api.siliconflow.cn/v1/chat/completions"


def encode_image(image_path_or_bytes):
    """图片转base64"""
    if isinstance(image_path_or_bytes, bytes):
        return base64.b64encode(image_path_or_bytes).decode("utf-8")
    with open(image_path_or_bytes, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def recognize_holdings(image_data, user_id="default"):
    """识别券商截图中的持仓信息
    
    Args:
        image_data: 图片base64字符串或文件路径
        user_id: 用户ID
    
    Returns:
        dict: 识别结果，包含股票列表
    """
    if not SILICONFLOW_API_KEY:
        return {"code": 1, "message": "请配置硅基流动API Key (SILICONFLOW_API_KEY)"}
    
    # 如果是文件路径，先转base64
    if os.path.isfile(image_data):
        image_data = encode_image(image_data)
    
    # 构建prompt
    prompt = """请识别这张券商APP持仓截图中的股票信息。

请按以下JSON格式返回（只返回JSON，不要其他内容）：
{
    "positions": [
        {
            "stock_code": "股票代码",
            "stock_name": "股票名称",
            "shares": 持仓数量（数字）,
            "cost_price": 成本价（数字）,
            "market": "市场（A股/港股/美股）"
        }
    ]
}

注意事项：
1. 股票代码：A股如000001、600000；港股如00700、09988；美股如AAPL、TSLA
2. 如果截图模糊或信息不完整，请返回空数组
3. 不需要识别期权、牛熊证等衍生品
4. 如果有多页，请识别当前页内容
"""

    # 调用API
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "deepseek-ai/DeepSeek-VL2",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ]
            }
        ],
        "max_tokens": 1024,
        "temperature": 0.1,
    }
    
    try:
        r = httpx.post(SF_API_URL, json=payload, headers=headers, timeout=60)
        result = r.json()
        
        # 解析返回的JSON
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # 提取JSON部分
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = content[start:end]
            data = json.loads(json_str)
            return {"code": 0, "data": data.get("positions", [])}
        else:
            return {"code": 1, "message": "无法解析识别结果", "raw": content}
            
    except Exception as e:
        return {"code": 1, "message": f"识别失败: {str(e)}"}


def recognize_from_url(image_url, user_id="default"):
    """从URL识别图片"""
    if not SILICONFLOW_API_KEY:
        return {"code": 1, "message": "请配置硅基流动API Key"}
    
    prompt = """请识别这张券商APP持仓截图中的股票信息。

请按以下JSON格式返回（只返回JSON，不要其他内容）：
{
    "positions": [
        {
            "stock_code": "股票代码",
            "stock_name": "股票名称", 
            "shares": 持仓数量,
            "cost_price": 成本价,
            "market": "市场（A股/港股/美股）"
        }
    ]
}"""

    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "deepseek-ai/DeepSeek-VL2",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ],
        "max_tokens": 1024,
        "temperature": 0.1,
    }
    
    try:
        r = httpx.post(SF_API_URL, json=payload, headers=headers, timeout=60)
        result = r.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = content[start:end]
            data = json.loads(json_str)
            return {"code": 0, "data": data.get("positions", [])}
        return {"code": 1, "message": "无法解析识别结果"}
    except Exception as e:
        return {"code": 1, "message": f"识别失败: {str(e)}"}