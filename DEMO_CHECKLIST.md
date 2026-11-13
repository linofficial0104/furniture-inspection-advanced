# Demo 前檢查清單

## 部署（Render）

- [ ] Environment 設好 `GEMINI_API_KEY`、`GEMINI_MODEL`
- [ ] （選填）`GEMINI_CHECK_MODEL`：拍照當下單張檢查用的模型，沒設就跟 `GEMINI_MODEL` 一樣
- [ ] Environment 設 `PYTHON_VERSION`（本機開發用 3.14，兩邊一致比較保險）
- [ ] Build Command：`pip install -r requirements.txt`
- [ ] Start Command：`uvicorn main:app --host 0.0.0.0 --port $PORT`
- [ ] `demo/` 資料夾的 4 個 json 有一起上傳（示範按鈕要用）

## 手機實測（iPhone、Android 各一台）

用 Render 的 https 網址開，不要用 http 或區網 IP：手機瀏覽器只有 https 才能開相機。

- [ ] 首頁下方顯示「✓ 伺服器已就緒」
- [ ] 按「開始拍攝」會跳出相機權限，允許後看得到畫面
- [ ] 光線提示會變（遮住鏡頭會顯示「光線偏暗」）
- [ ] 5 張照片拍完會自動送出，10 秒內拿到結果
- [ ] 「從相簿選取 5 張照片」可以用（iPhone 的照片是 HEIC，要確認能正常上傳）
- [ ] 每拍一張，下方會出現「AI 正在檢查…」，約 2 秒後顯示「✓ 沒問題」才跳下一張
- [ ] 照片 1 故意拍桌角 → 拍完馬上顯示「需要重拍」和重拍建議，縮圖有紅框；按「重拍這張」可以重拍，按「仍然使用」可以保留
- [ ] 從相簿選 5 張、其中一張放錯 → 停在拍攝畫面並標出放錯的那張
- [ ] 結果頁右上角 pass / review / reject / retake 四個示範按鈕都有照片和結果
- [ ] 「加入主畫面」後從主畫面打開，相機一樣能用
- [ ] 開飛航模式按送出 → 會顯示「連不到伺服器」，不會一直轉圈

## 上台前 10 分鐘

- [ ] 用手機打開網址，等首頁顯示「✓ 伺服器已就緒」（Render 免費方案閒置會休眠，叫醒要約一分鐘）
- [ ] 按一次「測試」確認 Gemini 正常
- [ ] 萬一 Gemini 掛掉：改用結果頁右上角的示範按鈕，資料是之前真實跑出來的

## 重新產生示範資料

```bash
python make_demo.py pass   照片資料夾
python make_demo.py review 照片資料夾
python make_demo.py reject 照片資料夾
python make_demo.py retake 照片1 照片2 照片3 照片4 照片5
```

資料夾裡要有 `desktop.jpg`、`corner_1.jpg`～`corner_4.jpg`。分析結果跟指定的不同時不會存檔。

目前的示範資料來源（`Desktop/pic_generator/output_ai`）：

| 結果 | 照片 |
|---|---|
| pass | surface_wear/level_1_light |
| review | surface_wear/level_2_medium |
| reject | water_damage/level_3_heavy |
| retake | surface_wear/level_1_light，但照片 1 換成 corner_1.jpg |

## 已知問題

- `test/images` 和 `pic_generator` 的照片裡，corner_1 和 corner_3 是同一張、corner_2 和 corner_4 是同一張。要拍到另外兩個桌角的真實照片才能解決。
