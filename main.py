"""
後端伺服器。
本機啟動：uvicorn main:app --reload
打開網頁：http://127.0.0.1:8000
"""
import base64
import io
import json
import time
from pathlib import Path

import httpx

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from google.genai import errors
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

from inspector import PHOTO_FILES, analyze_photos, check_single_photo
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
FINALS = {"pass", "review", "reject", "retake"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 每張照片最多 10 MB

# 用程式所在的資料夾當基準，不管從哪裡啟動 uvicorn 都找得到檔案
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_FILE = BASE_DIR / "index.html"
TEST_IMAGE_DIR = BASE_DIR / "test" / "images"
DEMO_DIR = BASE_DIR / "demo"
DEMO_DIR.mkdir(exist_ok=True)


# ========== 共用工具 ==========

def shrink(data: bytes, max_side: int) -> bytes:
    """縮小照片並轉成 JPEG，也會依手機的方向資訊轉正"""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


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
    回傳格式：Gemini 的檢查表欄位 + final_decision + price + demo
    示範資料改用 make_demo.py 產生，伺服器不會自動存檔
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
        "demo": False,
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


class CheckPhotoRequest(BaseModel):
    view: int = Field(ge=1, le=EXPECTED_COUNT)   # 照片編號 1～5
    image: str                                   # data URL


@app.post("/check-photo")
def check_photo(request: CheckPhotoRequest):
    """
    拍照當下檢查單張照片：拍的部位對不對、清不清楚。
    回傳 {ok, hint, seen, skipped}。
    AI 出錯或逾時時一律放行（ok=true、skipped=true），不讓使用者卡在拍照畫面；
    5 張送出後的完整分析還會再檢查一次。
    """
    data, mime_type = decode_data_url(request.image, request.view)
    started = time.time()
    try:
        result = check_single_photo(request.view, data, mime_type)
    except Exception as e:
        print(f"單張檢查失敗，直接放行：{type(e).__name__}：{e}")
        return {"ok": True, "hint": "", "seen": "", "skipped": True}
    ok = result.matches and result.clear
    print(f"單張檢查 第 {request.view} 張：{'通過' if ok else '不通過'}（{time.time() - started:.1f} 秒）{result.seen}")
    hint = result.hint or "這張照片不符合要求，請依照畫面提示重拍"
    return {"ok": ok, "hint": "" if ok else hint, "seen": result.seen, "skipped": False}


@app.get("/analyze-test-images")
def analyze_test_images():
    """首頁「測試」按鈕：用伺服器上 test/images 的 5 張照片跑一次真實分析"""
    images, previews = [], []
    for name in PHOTO_FILES:
        path = TEST_IMAGE_DIR / name
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"找不到測試照片 {path}")
        raw = path.read_bytes()
        images.append((shrink(raw, 1280), "image/jpeg"))
        previews.append("data:image/jpeg;base64," + base64.b64encode(shrink(raw, 400)).decode())
    body = run_inspection(images)
    return {**body, "preview_images": previews}


@app.get("/demo/{case}")
def demo(case: str):
    """Demo 備案：之前真實跑出來、存起來的結果，demo 欄位是 true"""
    path = DEMO_DIR / f"{case}.json"
    if case not in FINALS or not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"沒有 {case} 的示範資料，請先用真實照片跑出一次 {case} 的結果",
        )
    return json.loads(path.read_text(encoding="utf-8"))


# ========== 測試用（用 /docs 頁面或 curl 上傳檔案） ==========

@app.post("/inspect")
def inspect_furniture(photos: list[UploadFile] = File(...)):
    """用檔案上傳的方式送 5 張照片，方便在 /docs 頁面測試"""
    if len(photos) != EXPECTED_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"需要 {EXPECTED_COUNT} 張照片，收到 {len(photos)} 張",
        )
    images = []
    for i, photo in enumerate(photos, start=1):
        if photo.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"第 {i} 張不是支援的圖片格式（{photo.content_type}）",
            )
        data = photo.file.read(MAX_IMAGE_BYTES + 1)
        check_size(data, i)
        images.append((data, photo.content_type))
    return run_inspection(images)
