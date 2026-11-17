"""
後端伺服器。
本機啟動：uvicorn main:app --reload
打開網頁：http://127.0.0.1:8000
"""
import base64
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from google.genai import errors
from pydantic import BaseModel

from inspector import analyze_photos
from pricing import estimate_price
from rules import decide

app = FastAPI(title="智鑑家具 SmartInspect")

# 允許其他網址的前端呼叫（例如用 Live Server 開的 5500 port）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EXPECTED_COUNT = 5
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 每張照片最多 10 MB

# 用程式所在的資料夾當基準，不管從哪裡啟動 uvicorn 都找得到檔案
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_FILE = BASE_DIR / "index.html"


# ========== 共用工具 ==========

def decode_data_url(data_url, index: int) -> tuple[bytes, str]:
    """把前端傳來的 data:image/jpeg;base64,... 轉回 (bytes, 格式)"""
    if not isinstance(data_url, str) or not data_url.startswith("data:") or ";base64," not in data_url:
        raise HTTPException(status_code=400, detail=f"第 {index} 張照片格式錯誤")
    header, b64 = data_url.split(",", 1)
    mime_type = header[5:].split(";")[0]
    if mime_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"第 {index} 張不是支援的圖片格式（{mime_type}）")
    try:
        data = base64.b64decode(b64, validate=True)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"第 {index} 張照片內容損壞")
    check_size(data, index)
    return data, mime_type


def check_size(data: bytes, index: int):
    """避免太大的檔案拖慢 Gemini 或塞爆記憶體"""
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"第 {index} 張照片太大（上限 {MAX_IMAGE_BYTES // 1024 // 1024} MB）",
        )


def run_inspection(images: list[tuple[bytes, str]]) -> dict:
    """
    所有入口共用：送給 Gemini → Python 規則判定 → 估價 → 回傳前端要的格式。
    回傳格式：Gemini 的檢查表欄位 + final_decision + price
    """
    try:
        result = analyze_photos(images)
    except errors.ServerError:
        raise HTTPException(status_code=503, detail="AI 服務忙碌中，請稍後再試")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI 回應太慢，請再試一次")
    except errors.ClientError as e:
        raise HTTPException(status_code=502, detail=f"AI 服務請求失敗：{e.message}")
    except ValueError:
        raise HTTPException(status_code=502, detail="AI 回傳格式錯誤，請再試一次")
    except Exception as e:
        print(f"未預期的錯誤：{type(e).__name__}：{e}")
        raise HTTPException(status_code=500, detail="伺服器發生錯誤，請稍後再試")

    final = decide(result)
    body = {
        **result.model_dump(),
        "final_decision": final,
        "price": estimate_price(result, final),
    }
    return body


# ========== 網頁 ==========

@app.get("/")
def home():
    if FRONTEND_FILE.exists():
        return FileResponse(FRONTEND_FILE)
    return {"message": "家具檢測後端運作中（找不到 index.html）"}


@app.get("/health")
def health():
    return {"message": "家具檢測後端運作中"}


# ========== 前端用的 API ==========

class AnalyzeRequest(BaseModel):
    images: list[str | None]


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    """前端送 5 張照片（data URL，順序：桌面、左前、左後、右後、右前）"""
    if len(request.images) != EXPECTED_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"需要 {EXPECTED_COUNT} 張照片，收到 {len(request.images)} 張",
        )
    images = [decode_data_url(url, i) for i, url in enumerate(request.images, start=1)]
    return run_inspection(images)
