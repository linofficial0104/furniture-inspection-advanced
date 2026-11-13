"""
估價規則：參考 IKEA 英國 Buy Back 方案推出時的三個等級
  如新（無刮痕）50%、非常好（輕微刮痕）40%、使用痕跡（多處刮痕）30%
只有 pass 自動估價，等級由「有幾項是 1 分（輕微）」決定。
review 不自動估價，只給上限；reject 為 0；retake 要重拍後才能估價。
"""
from schema import InspectResult

NEW_PRICE = 2000        # 新品價格
SELF_DROP_BONUS = 50    # 自己送到門市的低碳獎勵

PRICE_TIERS = [
    {"name": "如新", "rate": 0.5, "desc": "三項皆完好"},             # 0 個 1 分
    {"name": "非常好", "rate": 0.4, "desc": "一項有輕微痕跡"},        # 1 個 1 分
    {"name": "使用痕跡", "rate": 0.3, "desc": "兩項以上有輕微痕跡"},  # 2 個以上 1 分
]


def estimate_price(result: InspectResult, final: str) -> dict:
    """
    回傳一個 dict，四個欄位：
      amount：收購價（整數），沒有價格時是 None
      self_drop_amount：自己送到門市的價格（amount + 獎勵），只有 pass 有，其他是 None
      text：畫面上顯示的大字
      formula：畫面上顯示的算法說明
    """
    # 1. retake：照片看不清楚，沒辦法估價
    if final == "retake":
        return {
            "amount": None,
            "self_drop_amount": None,
            "text": "重拍後估價",
            "formula": "部分照片無法判斷",
        }

    # 2. reject：不收購
    if final == "reject":
        return {
            "amount": 0,
            "self_drop_amount": None,
            "text": "NT$ 0",
            "formula": "受損程度不符收購標準",
        }

    scores = [
        result.dimensions.structure.score,
        result.dimensions.surface_wear.score,
        result.dimensions.water_damage.score,
    ]
    minor_count = scores.count(1)

    # 3. review：不自動估價，只給上限
    #    有 2 分以上的項目：狀況比最低等級差，上限是最低等級的價格
    #    分數都是 0 或 1、只是 AI 把握度不夠：上限是分數對應的等級價格
    if final == "review":
        if any(s is not None and s >= 2 for s in scores):
            cap_tier = PRICE_TIERS[2]
        else:
            cap_tier = PRICE_TIERS[min(minor_count, 2)]
        max_price = round(NEW_PRICE * cap_tier["rate"])
        return {
            "amount": None,
            "self_drop_amount": None,
            "text": "轉交人工核價",
            "formula": f"最高不超過 NT$ {max_price}，由專員確認",
        }

    # 4. pass：數有幾項是 1 分，決定等級（pass 的分數只會是 0 或 1）
    tier = PRICE_TIERS[min(minor_count, 2)]   # 3 個 1 分也算第三級
    amount = round(NEW_PRICE * tier["rate"])
    percent = round(tier["rate"] * 100)

    return {
        "amount": amount,
        "self_drop_amount": amount + SELF_DROP_BONUS,
        "text": f"NT$ {amount}",
        "formula": f"{tier['name']}：新品 ${NEW_PRICE} × {percent}%（{tier['desc']}）",
    }
