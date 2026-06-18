from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.services.auth_service import require_feature
from app.entitlements import Feature

router = APIRouter(prefix="/api/v1/multi-site", tags=["multi-site"])

# Static mock data representing different facilities
SITES_DATA = [
  {
    "id": 'site-casablanca',
    "name": 'Casablanca Headquarters',
    "meterId": 'CM-HQ-01',
    "status": 'Active',
    "load": 184.5,
    "dailyConsumption": 2420,
    "peakPower": 210,
    "monthlyCost": 64800,
    "circuits": [
      { "name": 'Server Room A', "status": 'Active', "current": 120, "power": 26.4, "cosPhi": 0.98 },
      { "name": 'HVAC Main', "status": 'Active', "current": 280, "power": 61.6, "cosPhi": 0.88 },
      { "name": 'Production Line B', "status": 'Active', "current": 310, "power": 68.2, "cosPhi": 0.90 },
      { "name": 'Office Lighting', "status": 'Active', "current": 130, "power": 28.3, "cosPhi": 0.95 },
    ]
  },
  {
    "id": 'site-tangier',
    "name": 'Tangier Logistics Hub',
    "meterId": 'CM-TL-02',
    "status": 'Active',
    "load": 120.2,
    "dailyConsumption": 1650,
    "peakPower": 145,
    "monthlyCost": 44200,
    "circuits": [
      { "name": 'EV Charging Stations', "status": 'Active', "current": 180, "power": 39.6, "cosPhi": 0.99 },
      { "name": 'Conveyor Belts', "status": 'Active', "current": 220, "power": 48.4, "cosPhi": 0.85 },
      { "name": 'Warehouse Lights', "status": 'Active', "current": 100, "power": 22.0, "cosPhi": 0.92 },
      { "name": 'Office Pods', "status": 'Active', "current": 46, "power": 10.2, "cosPhi": 0.96 },
    ]
  },
  {
    "id": 'site-marrakech',
    "name": 'Marrakech Showroom',
    "meterId": 'CM-MS-03',
    "status": 'Active',
    "load": 65.8,
    "dailyConsumption": 920,
    "peakPower": 80,
    "monthlyCost": 24800,
    "circuits": [
      { "name": 'Display Lighting', "status": 'Active', "current": 110, "power": 24.2, "cosPhi": 0.97 },
      { "name": 'HVAC Aircon', "status": 'Active', "current": 150, "power": 33.0, "cosPhi": 0.89 },
      { "name": 'IT Infrastructure', "status": 'Active', "current": 30, "power": 6.6, "cosPhi": 0.95 },
      { "name": 'Security & Access', "status": 'Active', "current": 9, "power": 2.0, "cosPhi": 0.90 },
    ]
  },
  {
    "id": 'site-agadir',
    "name": 'Agadir Production Plant',
    "meterId": 'CM-AP-04',
    "status": 'Maintenance',
    "load": 0.0,
    "dailyConsumption": 0,
    "peakPower": 0,
    "monthlyCost": 0,
    "circuits": [
      { "name": 'Assembly Line 1', "status": 'Idle', "current": 0, "power": 0.0, "cosPhi": 0.0 },
      { "name": 'Main Compressor', "status": 'Idle', "current": 0, "power": 0.0, "cosPhi": 0.0 },
      { "name": 'Plant Cooling', "status": 'Idle', "current": 0, "power": 0.0, "cosPhi": 0.0 },
      { "name": 'Auxiliary System', "status": 'Idle', "current": 0, "power": 0.0, "cosPhi": 0.0 },
    ]
  }
]

@router.get("")
def get_multi_site_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_feature(Feature.MULTI_SITE)),
):
    """
    Returns the multi-site telemetry data.

    Enterprise-only: enforced server-side via `require_feature`, which returns a
    consistent 403 (instead of the previous 200-with-error body). See audit C2.
    """
    return {"data": SITES_DATA}
