# 智鑑家具 SmartInspect

二手家具遠端智慧質檢系統。使用者用手機依照畫面引導拍 5 張桌子照片，由 Gemini 檢查結構、表面磨損與受潮狀況，再用固定規則決定能不能收購、預估收購價多少。

> 本專案為「2026 永續智慧創新黑客松」競賽原型，**非 IKEA 官方服務**。網站中的 IKEA 名稱、門市與客服資訊僅作情境示意，收購價為原型試算。

- **線上網站：** https://furniture-inspection-advanced.onrender.com
- **示範網站：** https://furniture-demo-v1.onrender.com （給手邊沒有桌子的人看）

## 為什麼做這個

二手家具回購難以普及，最大的困難是人工審核與派車收件成本太高。民眾隨手拍的照片光線、角度不一，客服很難估價；派車到府或搬去門市才發現板材受潮膨脹而退貨，不只浪費車趟碳排，也容易引起消費爭議。

智鑑家具把品質控制移到**拍照當下**：用光線提示和對齊框引導拍出規格一致的照片，在家具出門前就先判斷能不能收。

## 功能

**拍照引導**
- 依序拍 5 張：1 張桌面整體 + 4 個桌角（左前、左後、右後、右前）
- 桌面用微梯形虛線框對齊；桌角用 Y 字對齊（黃點對準桌角、兩條斜線對齊桌邊、直線對齊桌腳）
- 即時偵測光線，太暗時不能拍照
- 也可以從相簿選取照片

**AI 分析與判定**
- Gemini 先逐張確認照片拍到的是不是該拍的部位，再為三個項目評分（0 完好 ～ 4 報廢）
- 照片拍錯或看不清楚時，指出要重拍哪幾張
- 由 Python 規則決定最後結果，不讓 AI 自己下結論

**四種結果**

| 結果 | 條件 | 收購價 |
|---|---|---|
| 符合收購標準（pass） | 三項都是 0 或 1 分，把握度 ≥ 70% | 新品價 × 50% / 40% / 30%，親送門市再加 NT$ 50 |
| 需人工複核（review） | 任一項 2 分、只有一項 3 分，或把握度 < 70% | 不自動估價，只給上限，可補拍近照 |
| 無法收購（reject） | 任一項 4 分，或兩項以上 3 分 | NT$ 0，引導零件維修或環保局清運 |
| 照片需要重拍（retake） | 照片拍錯、看不清楚，或某項無法判斷 | 重拍後再估價 |

## 系統架構

```
手機瀏覽器（index.html）
   │  5 張照片（壓縮成 800 px 的 JPEG，data URL）
   ▼
FastAPI 後端（main.py）── POST /analyze
   │
   ├─ inspector.py ── Gemini：逐張確認 + 三項評分 + 缺陷清單（照 prompt.txt 的標準）
   ├─ schema.py ──── 檢查 Gemini 回傳的格式；照片拍錯就強制改成重拍
   ├─ rules.py ───── 依分數和把握度決定 pass / review / reject / retake
   └─ pricing.py ─── 依結果估算收購價
   │
   ▼
結果頁：判定、收購價、三項分數、缺陷清單、下一步建議
```

## 檔案說明

| 檔案 | 用途 |
|---|---|
| `index.html` | 整個前端：首頁、拍照畫面、結果頁、專案理念，全部在這一個檔案裡 |
| `main.py` | 後端伺服器：提供網頁和 `/analyze` API，處理錯誤訊息 |
| `inspector.py` | 呼叫 Gemini，忙碌或逾時會自動重試一次 |
| `prompt.txt` | 給 Gemini 的檢查指示和評分標準 |
| `schema.py` | Gemini 回傳資料的格式定義與檢查 |
| `rules.py` | 判定規則 |
| `pricing.py` | 估價規則（新品價、等級折數、親送獎勵） |
| `requirements.txt` | Python 套件 |
| `DEMO_CHECKLIST.md` | 部署設定、手機實測和上台前的檢查清單 |
| `docs/` | 專案規劃與程式學習講義（PDF） |

## 在自己電腦上執行

需要 Python 3.10 以上，以及 Gemini API 金鑰（可在 [Google AI Studio](https://aistudio.google.com/) 申請）。

1. 建立虛擬環境並安裝套件（Windows PowerShell）：

   ```bash
   python -m venv venv
   ```
   ```bash
   .\venv\Scripts\Activate.ps1
   ```
   ```bash
   pip install -r requirements.txt
   ```

2. 在專案資料夾建立 `.env`：

   ```
   GEMINI_API_KEY=你的金鑰
   GEMINI_MODEL=gemini-3.5-flash-lite
   ```

   `.env` 已經寫在 `.gitignore` 裡，不會被上傳。

3. 啟動伺服器：

   ```bash
   uvicorn main:app --reload
   ```

4. 打開 http://127.0.0.1:8000

電腦瀏覽器只要是 `localhost` 就能開相機；手機要用 **https** 網址才能開相機，所以手機測試請用部署後的網址。

## 部署到 Render

| 設定 | 值 |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Environment | `GEMINI_API_KEY`、`GEMINI_MODEL`，建議再設 `PYTHON_VERSION` |

Render 免費方案閒置一段時間會休眠，第一次打開網站可能要等約一分鐘。完整的部署與實測項目見 [DEMO_CHECKLIST.md](DEMO_CHECKLIST.md)。

## API

### `POST /analyze`

送出 5 張照片，順序固定為：桌面、左前、左後、右後、右前。

```json
{ "images": ["data:image/jpeg;base64,...", "...", "...", "...", "..."] }
```

- 支援 JPEG、PNG、WebP，每張最多 10 MB
- 一般 2～10 秒回應；Gemini 忙碌或逾時會自動重試一次

回傳（節錄）：

```json
{
  "final_decision": "pass",
  "confidence": 0.9,
  "dimensions": {
    "structure":    { "score": 0, "note": "四支桌腳與接合處看起來完整緊密" },
    "surface_wear": { "score": 1, "note": "桌面有細小刮痕" },
    "water_damage": { "score": 0, "note": "沒有觀察到水漬" }
  },
  "defects": [{ "type": "scratch", "location": "桌面中央偏下方", "view": 1 }],
  "need_retake": false,
  "retake_views": [],
  "reason": "結構與防潮狀況良好，僅有輕微使用痕跡",
  "price": { "amount": 800, "self_drop_amount": 850, "text": "NT$ 800", "formula": "非常好：新品 $2000 × 40%（一項有輕微痕跡）" }
}
```

錯誤時回傳 `{ "detail": "錯誤說明" }`，例如照片數量不對（400）、照片太大（413）、AI 服務忙碌（503）、AI 回應太慢（504）。

### `GET /health`

確認伺服器是否在運作，給部署平台檢查用。

## 調整設定

| 想改的東西 | 位置 |
|---|---|
| 新品價格、等級折數、親送獎勵 | `pricing.py` 的 `NEW_PRICE`、`PRICE_TIERS`、`SELF_DROP_BONUS` |
| 把握度門檻（低於就轉人工） | `rules.py` 的 `CONFIDENCE_THRESHOLD` |
| 評分標準、AI 檢查方式 | `prompt.txt` |
| 首頁顯示的「最高收購價」 | `index.html`（改 `NEW_PRICE` 時要一起改，目前是新品價 × 50%） |
| Gemini 逾時與重試次數 | `inspector.py` 的 `TIMEOUT_MS`、`MAX_ATTEMPTS` |

## 已知限制

- 「送出人工審核」和補傳近照只是畫面示意，尚未串接後台。
- 目前只針對桌子（IKEA LACK 方桌 / 邊桌）設計，其他家具需要另外的拍攝引導和評分標準。
- AI 分析每次可能略有不同，邊界情況（例如很輕微的刮痕）可能被判在相鄰的等級。

## 開發團隊

**猴子樂園 (Monkeys World)**
國立臺灣科技大學｜資通科技國際學士學位學程 / 電資學士班

林承翰、蕭宇臻、張瑋家、陳均碩、葉宇森、陳宥廷、陳宥羲
