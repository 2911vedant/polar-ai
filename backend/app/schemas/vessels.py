from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class VesselStatus(BaseModel):
    id: str
    name: str
    current_lat: float
    current_lon: float
    current_speed_knots: float
    current_heading_deg: float
    current_status: str
    ice_class: str
    max_speed_knots: float
    data_mode: str
