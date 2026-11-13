from pydantic import BaseModel,Field,ValidationError,field_validator,model_validator

# 每張照片應該拍到的內容，順序跟前端一致
EXPECTED_VIEWS = ["桌面整體", "左前桌角", "左後桌角", "右後桌角", "右前桌角"]
RETAKE_NOTE = "照片需要重拍，重拍後再評分"

class PhotoCheck(BaseModel):
    view:int = Field(le=5,ge=1)
    seen:str      # 這張照片實際拍到什麼
    matches:bool  # 是否符合這張應該拍的內容（照片 1 要完整桌面，照片 2～5 要桌角與桌腳）

class SinglePhotoCheck(BaseModel):
    """拍照當下的單張檢查（/check-photo）"""
    seen:str      # 照片實際拍到什麼
    matches:bool  # 是否符合這張該拍的內容
    clear:bool    # 是否清楚可用
    hint:str      # 不通過時的重拍建議

class Dimension(BaseModel):
    score:int|None = Field(le=4,ge=0)
    note:str

class Defect(BaseModel):
    type:str
    location:str
    view:int = Field(le=5,ge=1)

class Dimensions(BaseModel):
    structure:Dimension
    surface_wear:Dimension
    water_damage:Dimension

class InspectResult(BaseModel):
    # 放在第一個欄位：讓 Gemini 先逐張確認拍到什麼，再做其他判斷
    photo_checks:list[PhotoCheck]
    need_retake:bool
    retake_views: list[int]
    retake_hint:str
    dimensions:Dimensions
    defects:list[Defect] #宣告defects這個屬性接收的資料一定要是串列並且此串列裡面每個值都要符合 Defect 這個類別的規定
    confidence:float=Field(le=1,ge=0)
    reason:str

    @field_validator("retake_views")
    @classmethod
    def keep_valid_views(cls, views):
        # 只留 1～5 的照片編號，去掉重複並排序；Gemini 偶爾回傳 0 或 6 時前端才不會當掉
        return sorted({v for v in views if 1 <= v <= 5})

    @model_validator(mode="after")
    def retake_wrong_views(self):
        # Gemini 有時候發現照片拍錯了，卻忘了把 need_retake 設成 true
        # 這裡由程式強制：任何一張 matches 是 false，就一定要重拍那一張
        wrong = [c for c in self.photo_checks if not c.matches]
        if wrong:
            self.need_retake = True
            self.retake_views = sorted(set(self.retake_views) | {c.view for c in wrong})
            if not self.retake_hint:
                self.retake_hint = "；".join(
                    f"第 {c.view} 張應該拍{EXPECTED_VIEWS[c.view - 1]}，但照片是{c.seen}" for c in wrong
                ) + "，請重拍"

        # 照片要重拍時，分數不可信：三項一律改成 null（前端顯示「無法判斷」）
        if self.need_retake:
            for dim in (self.dimensions.structure, self.dimensions.surface_wear, self.dimensions.water_damage):
                dim.score = None
                dim.note = RETAKE_NOTE
        return self

# ========== 測試function ==========

def try_parse(blueprint,json_text):
    try:
        d = blueprint.model_validate_json(json_text)
        # print("succeed",d.model_dump())#這邊出來是dict
        print("succeed",d.model_dump_json(indent=2))#這邊出來直接是json
    except ValidationError as e:
        print(f"error:{e}")


if __name__ == "__main__":
  pass
 

