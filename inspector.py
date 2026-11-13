"""
把 5 張照片和 prompt 送給 Gemini，拿回檢查表（InspectResult）。
main.py 呼叫這裡的 analyze_photos()（5 張一起分析）和 check_single_photo()（拍照當下單張檢查）。
"""
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from schema import InspectResult, SinglePhotoCheck

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL")
if not API_KEY or not MODEL:
    raise RuntimeError("找不到 GEMINI_API_KEY 或 GEMINI_MODEL，請檢查 .env")

PROMPT = (BASE_DIR / "prompt.txt").read_text(encoding="utf-8")
CHECK_PROMPT = (BASE_DIR / "check_prompt.txt").read_text(encoding="utf-8")

# 拍照當下單張檢查用的模型：要快、要便宜；沒設定就跟分析用同一個
CHECK_MODEL = os.getenv("GEMINI_CHECK_MODEL") or MODEL
CHECK_TIMEOUT_MS = 10_000   # 單張檢查最多等 10 秒，超過就放行，不卡使用者

# 照片順序跟前端一致：1 桌面整體，2～5 四個桌角（左前、左後、右後、右前）
PHOTO_LABELS = ["桌面整體", "左前桌角", "左後桌角", "右後桌角", "右前桌角"]
PHOTO_FILES = ["desktop.jpg", "corner_1.jpg", "corner_2.jpg", "corner_3.jpg", "corner_4.jpg"]

MAX_ATTEMPTS = 2        # 最多試幾次（第一次 + 重試一次）
RETRY_WAIT_SECONDS = 2  # 重試前等幾秒
TIMEOUT_MS = 30_000     # 一次呼叫最多等 30 秒（實測正常 2～5 秒）；重試一次最久約 62 秒

client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(timeout=TIMEOUT_MS),
)
check_client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(timeout=CHECK_TIMEOUT_MS),
)

# 每張照片的拍攝要求，給單張檢查用
PHOTO_REQUIREMENTS = [
    "必須看得到整個桌面，桌面的四個邊和四個角大致都在畫面內。只拍到一個桌角、桌邊或局部特寫就不符合。",
] + [
    "必須是單一桌角的特寫，看得到桌角、桌腳和兩者的接合處。整個桌面俯視、沒有桌腳、或不是桌子就不符合。"
] * 4


def check_single_photo(view: int, data: bytes, mime_type: str) -> SinglePhotoCheck:
    """
    拍照當下檢查單張照片：拍的部位對不對、清不清楚。
    view：照片編號 1～5。只呼叫一次、不重試，失敗就 raise，由呼叫端決定要不要放行。
    """
    prompt = CHECK_PROMPT.format(
        view=view, label=PHOTO_LABELS[view - 1], requirement=PHOTO_REQUIREMENTS[view - 1]
    )
    response = check_client.models.generate_content(
        model=CHECK_MODEL,
        contents=[prompt, types.Part.from_bytes(data=data, mime_type=mime_type)],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SinglePhotoCheck,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    if not response.text:
        raise ValueError("Gemini 沒有回傳內容")
    return SinglePhotoCheck.model_validate_json(response.text)


def _build_contents(photos):
    contents = [PROMPT]
    for i, (data, mime_type) in enumerate(photos, start=1):
        contents.append(f"照片 {i}：{PHOTO_LABELS[i - 1]}")
        contents.append(types.Part.from_bytes(data=data, mime_type=mime_type))
    return contents


def analyze_photos(photos: list[tuple[bytes, str]]) -> InspectResult:
    """
    photos：5 組 (照片的 bytes, 格式)
    回傳：Gemini 填好的檢查表
    Gemini 忙碌或回傳格式錯誤時，自動重試；重試完還是失敗就 raise
    """
    contents = _build_contents(photos)
    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=InspectResult,
                    # 沒有用到工具呼叫，關掉可以去除每次呼叫都印出的 AFC 警告
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
            if not response.text:
                raise ValueError("Gemini 沒有回傳內容")
            # ValidationError 是 ValueError 的子類別，格式錯誤也會被下面接住
            return InspectResult.model_validate_json(response.text)

        except (errors.ServerError, ValueError) as e:
            # 5xx 和格式錯誤：可能是暫時的，值得再試
            last_error = e
            if attempt < MAX_ATTEMPTS:
                print(f"第 {attempt} 次失敗（{type(e).__name__}），{RETRY_WAIT_SECONDS} 秒後重試")
                time.sleep(RETRY_WAIT_SECONDS)

        # errors.ClientError（4xx，例如金鑰或模型名稱錯）不重試，直接往外丟

    raise last_error
