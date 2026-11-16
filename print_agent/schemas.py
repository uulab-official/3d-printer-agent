import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

TEMPLATE_SPECIFIC_FIELDS = {
    'tray': {'dividers'},
    'cable_comb': {'slots','cable_diameter','fit_clearance'},
    'magnet_frame': {'inset_diameter','inset_depth','fit_clearance'},
    'phone_stand': {'lean_angle','device_thickness','lip_height','fit_clearance'},
    'name_tag': {'text','text_size','text_depth','hole_diameter'},
}
# Non-numeric fields. Every other parameter is a finite number.
TEXT_FIELDS = {'text'}
# Printable letters, digits, Hangul, spaces and a few marks; no control characters.
NAME_TEXT = re.compile(r"[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ .,'&!?♥★\-]{1,20}")
# Fields added after v0.10. They appear in canonical parameters only for the
# templates that use them, so earlier jobs, recipes and review hashes keep the
# exact same eleven-field shape.
LATER_FIELDS = {'lean_angle','device_thickness','lip_height','text','text_size','text_depth','hole_diameter'}

class GeometryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    template: Literal["tray", "cable_comb", "magnet_frame", "phone_stand", "name_tag"] = "tray"
    width: float = Field(default=120, ge=10, le=500)
    depth: float = Field(default=80, ge=10, le=500)
    height: float = Field(default=35, ge=2, le=300)
    wall: float = Field(default=2, ge=0.8, le=20)
    bottom: float = Field(default=2, ge=0.8, le=20)
    dividers: int = Field(default=0, ge=0, le=12, strict=True)
    slots: int = Field(default=5, ge=1, le=20, strict=True)
    cable_diameter: float = Field(default=6, ge=1, le=30)
    inset_diameter: float = Field(default=52, ge=5, le=450)
    inset_depth: float = Field(default=2, ge=0.5, le=30)
    fit_clearance: float = Field(default=0.3, ge=0, le=3)
    lean_angle: float = Field(default=65, ge=50, le=80)
    device_thickness: float = Field(default=12, ge=4, le=30)
    lip_height: float = Field(default=12, ge=3, le=60)
    text: str = Field(default="", max_length=20)
    text_size: float = Field(default=12, ge=6, le=40)
    text_depth: float = Field(default=2, ge=0.6, le=6)
    hole_diameter: float = Field(default=4, ge=2, le=10)

    @model_validator(mode='after')
    def applicable_fields(self):
        # model_dump includes neutral defaults; only meaningful inapplicable
        # overrides are rejected so saved, complete specs remain round-trippable.
        all_specific = set().union(*TEMPLATE_SPECIFIC_FIELDS.values())
        for name in all_specific - TEMPLATE_SPECIFIC_FIELDS[self.template]:
            if getattr(self,name) != type(self).model_fields[name].default:
                raise ValueError(f'{name}은 {self.template} 템플릿에 적용되지 않습니다.')
        if self.template == 'name_tag' and not NAME_TEXT.fullmatch(self.text.strip() if self.text else ''):
            raise ValueError('키링 글자는 한글·영문·숫자·공백과 일부 기호로 1~20자여야 합니다.')
        return self

    @model_serializer(mode='wrap')
    def canonical(self, handler):
        data = handler(self)
        for name in LATER_FIELDS - TEMPLATE_SPECIFIC_FIELDS[self.template]:
            data.pop(name, None)
        return data
