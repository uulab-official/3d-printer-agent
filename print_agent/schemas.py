import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

TEMPLATE_SPECIFIC_FIELDS = {
    'tray': {'dividers'},
    'cable_comb': {'slots','cable_diameter','fit_clearance'},
    'magnet_frame': {'inset_diameter','inset_depth','fit_clearance'},
    'phone_stand': {'lean_angle','device_thickness','lip_height','fit_clearance'},
    'name_tag': {'text','text_size','text_depth','hole_diameter'},
    'wall_hook': {'hole_diameter','lip_height'},
    'keycap': {'text','text_size','text_depth','fit_clearance','key_units'},
}
# Filament colours a person can name. Keys are stored; hex values are display
# approximations only, not a measured filament colour.
PALETTE = {
    'white': ('흰색', '#F4F4F1'), 'black': ('검정', '#232323'), 'gray': ('회색', '#8E9096'),
    'red': ('빨강', '#D2302C'), 'orange': ('주황', '#F07F1F'), 'yellow': ('노랑', '#F4C430'),
    'green': ('초록', '#2E9E4F'), 'blue': ('파랑', '#2563C9'), 'purple': ('보라', '#7B4BB8'),
    'pink': ('분홍', '#EE7FB2'), 'brown': ('갈색', '#8B5A2B'),
}
# Colour of the whole model, and of the raised letters on a name tag.
COLOR_FIELDS = {'color', 'accent_color'}
# Non-numeric fields. Every other parameter is a finite number.
TEXT_FIELDS = {'text'}
# Printable letters, digits, Hangul, spaces and a few marks; no control characters.
NAME_TEXT = re.compile(r"[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ .,'&!?♥★\-]{1,20}")
# A keycap legend is short and may be empty (a blank key).
KEYCAP_TEXT = re.compile(r"[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ .,'&!?♥★\-]{0,6}")
# Key sizes (units of 19.05 mm) the keycap template builds; 2u and wider get stabilizer stems.
KEY_UNITS = (1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.75, 6.25, 7.0)
# Fields added after v0.10. They appear in canonical parameters only for the
# templates that use them, so earlier jobs, recipes and review hashes keep the
# exact same eleven-field shape.
LATER_FIELDS = {'lean_angle','device_thickness','lip_height','text','text_size','text_depth','hole_diameter','key_units'}
# Colours are optional for every template; an unchosen colour ('') is omitted from
# canonical parameters, so models without colours keep their earlier shape and hashes.

class GeometryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    template: Literal["tray", "cable_comb", "magnet_frame", "phone_stand", "name_tag", "wall_hook", "keycap"] = "tray"
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
    text_size: float = Field(default=12, ge=3, le=40)
    text_depth: float = Field(default=2, ge=0.6, le=6)
    hole_diameter: float = Field(default=4, ge=2, le=10)
    key_units: float = Field(default=1, ge=1, le=7)
    color: str = Field(default="", max_length=16)
    accent_color: str = Field(default="", max_length=16)

    @model_validator(mode='after')
    def applicable_fields(self):
        # model_dump includes neutral defaults; only meaningful inapplicable
        # overrides are rejected so saved, complete specs remain round-trippable.
        all_specific = set().union(*TEMPLATE_SPECIFIC_FIELDS.values())
        for name in all_specific - TEMPLATE_SPECIFIC_FIELDS[self.template]:
            if getattr(self,name) != type(self).model_fields[name].default:
                raise ValueError(f'{name}은 {self.template} 템플릿에 적용되지 않습니다.')
        for name in COLOR_FIELDS:
            if getattr(self, name) and getattr(self, name) not in PALETTE:
                raise ValueError(f'지원하는 색은 {", ".join(label for label, _ in PALETTE.values())}입니다.')
        if self.accent_color and self.template == 'keycap':
            raise ValueError('키캡 글자는 윗면에 새기므로 글자만 다른 색으로 만들 수 없습니다. 모델 색만 고르세요.')
        if self.accent_color and self.template != 'name_tag':
            raise ValueError('글자 색은 이름 키링에만 지정할 수 있습니다.')
        if self.template == 'name_tag' and not NAME_TEXT.fullmatch(self.text.strip() if self.text else ''):
            raise ValueError('키링 글자는 한글·영문·숫자·공백과 일부 기호로 1~20자여야 합니다.')
        if self.template == 'name_tag' and self.text_size < 6:
            raise ValueError('키링 글자 크기는 6 mm 이상이어야 합니다.')
        if self.template == 'keycap' and not KEYCAP_TEXT.fullmatch(self.text.strip() if self.text else ''):
            raise ValueError('키캡 글자는 한글·영문·숫자·공백과 일부 기호로 6자 이하여야 합니다(비워 두면 무지 키캡).')
        if self.template == 'keycap' and self.key_units not in KEY_UNITS:
            raise ValueError('키 크기는 ' + ', '.join(f'{units:g}u' for units in KEY_UNITS) + ' 중에서 고르세요.')
        return self

    @model_serializer(mode='wrap')
    def canonical(self, handler):
        data = handler(self)
        for name in LATER_FIELDS - TEMPLATE_SPECIFIC_FIELDS[self.template]:
            data.pop(name, None)
        for name in COLOR_FIELDS:
            if not data.get(name):
                data.pop(name, None)
        return data
