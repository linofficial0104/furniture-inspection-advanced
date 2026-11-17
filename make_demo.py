"""
產生 demo 備案資料：用真實照片跑一次分析，把結果和照片縮圖存到 demo/<結果>.json。
前端結果頁右上角的 pass / review / reject / retake 按鈕會讀這些檔案。

用法（照片順序：桌面、左前、左後、右後、右前）：
    python make_demo.py pass  資料夾路徑                 資料夾裡要有 desktop.jpg、corner_1～4.jpg
    python make_demo.py retake 照片1 照片2 照片3 照片4 照片5   直接指定 5 張照片

如果分析結果跟指定的不一樣（例如想做 pass 卻跑出 review），不會存檔，
要強制存成別的名字可以加 --force。
"""
import argparse
import base64
import json
from datetime import datetime
from pathlib import Path

from inspector import PHOTO_FILES
from main import DEMO_DIR, FINALS, run_inspection, shrink


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=sorted(FINALS))
    parser.add_argument("photos", nargs="+", help="一個資料夾，或 5 張照片")
    parser.add_argument("--force", action="store_true", help="結果不符也照樣存檔")
    args = parser.parse_args()

    if len(args.photos) == 1:
        folder = Path(args.photos[0])
        paths = [folder / name for name in PHOTO_FILES]
    elif len(args.photos) == 5:
        paths = [Path(p) for p in args.photos]
    else:
        raise SystemExit("請給一個資料夾，或剛好 5 張照片")
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise SystemExit("找不到照片：" + "、".join(missing))

    raw = [p.read_bytes() for p in paths]
    body = run_inspection([(shrink(data, 1280), "image/jpeg") for data in raw])
    final = body["final_decision"]
    scores = [d["score"] for d in body["dimensions"].values()]
    print(f"分析結果：{final}，分數 {scores}，把握度 {body['confidence']}")

    if final != args.case and not args.force:
        raise SystemExit(f"結果是 {final}，不是 {args.case}，沒有存檔（要強制存檔請加 --force）")

    body["demo"] = True
    body["saved_at"] = datetime.now().isoformat(timespec="seconds")
    body["preview_images"] = [
        "data:image/jpeg;base64," + base64.b64encode(shrink(data, 400)).decode() for data in raw
    ]
    out = DEMO_DIR / f"{args.case}.json"
    out.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已存到 {out}")


if __name__ == "__main__":
    main()
