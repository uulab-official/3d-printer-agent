from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

TEMPLATE_SPECIFIC_FIELDS = {
    'tray': {'dividers'},
    'cable_comb': {'slots','cable_diameter','fit_clearance'},
    'magnet_frame': {'inset_diameter','inset_depth','fit_clearance'},
}

class GeometryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    template: Literal["tray", "cable_comb", "magnet_frame"] = "tray"
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

    @model_validator(mode='after')
    def applicable_fields(self):
        # model_dump includes neutral defaults; only meaningful inapplicable
        # overrides are rejected so saved, complete specs remain round-trippable.
        all_specific = set().union(*TEMPLATE_SPECIFIC_FIELDS.values())
        for name in all_specific - TEMPLATE_SPECIFIC_FIELDS[self.template]:
            if getattr(self,name) != type(self).model_fields[name].default:
                raise ValueError(f'{name}은 {self.template} 템플릿에 적용되지 않습니다.')
        return self
