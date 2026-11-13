from schema import InspectResult

CONFIDENCE_THRESHOLD = 0.7


def decide(result: InspectResult) -> str:
    scores = [
        result.dimensions.structure.score,
        result.dimensions.surface_wear.score,
        result.dimensions.water_damage.score,
    ]

    # 規則 1：照片拍錯或不能用 → retake
    # 放在最前面：照片不對時分數也不可信，不能拿來 reject
    if result.need_retake:
        return "retake"
    # 規則 2：任一項 4 分（報廢），或兩項以上 3 分（嚴重）→ reject
    elif 4 in scores:
        return "reject"
    elif scores.count(3) > 1:
        return "reject"
    # 規則 3：有項目無法判斷（null）→ retake
    elif None in scores:
        return "retake"
    # 規則 4：一項 3 分、任一項 2 分，或 AI 把握度不夠 → review
    elif scores.count(3) == 1:
        return "review"
    elif 2 in scores:
        return "review"
    elif result.confidence < CONFIDENCE_THRESHOLD:
        return "review"
    # 規則 5：全部 0 或 1 分且把握度足夠 → pass
    else:
        return "pass"
