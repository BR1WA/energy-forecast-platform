"""
Alerts router — alert management and configuration.
"""
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User, Alert, AlertConfig
from app.schemas import AlertResponse, AlertConfigCreate, AlertConfigResponse, AlertAcknowledge
from app.services.auth_service import get_current_user
from app.services.websocket_manager import manager

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


@router.get("/", response_model=List[AlertResponse])
def list_alerts(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List alerts for the current user."""
    alerts = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id)
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )
    return [AlertResponse.model_validate(a) for a in alerts]


@router.get("/unacknowledged", response_model=List[AlertResponse])
def list_unacknowledged(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List unacknowledged alerts."""
    alerts = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id, Alert.is_acknowledged == False)
        .order_by(Alert.created_at.desc())
        .all()
    )
    return [AlertResponse.model_validate(a) for a in alerts]


@router.post("/acknowledge")
def acknowledge_alert(
    data: AlertAcknowledge,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Acknowledge an alert."""
    alert = db.query(Alert).filter(
        Alert.id == data.alert_id,
        Alert.user_id == current_user.id
    ).first()

    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.is_acknowledged = True
    db.commit()
    return {"message": "Alert acknowledged", "alert_id": data.alert_id}


@router.get("/config", response_model=AlertConfigResponse)
def get_alert_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the user's alert configuration."""
    config = db.query(AlertConfig).filter(AlertConfig.user_id == current_user.id).first()
    if not config:
        # Create default config
        config = AlertConfig(user_id=current_user.id, threshold_kw=3.0, email_enabled=True)
        db.add(config)
        db.commit()
        db.refresh(config)
    return AlertConfigResponse.model_validate(config)


@router.post("/config", response_model=AlertConfigResponse)
def update_alert_config(
    data: AlertConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update alert threshold configuration."""
    config = db.query(AlertConfig).filter(AlertConfig.user_id == current_user.id).first()
    if config:
        config.threshold_kw = data.threshold_kw
        config.email_enabled = data.email_enabled
    else:
        config = AlertConfig(
            user_id=current_user.id,
            threshold_kw=data.threshold_kw,
            email_enabled=data.email_enabled,
        )
        db.add(config)

    db.commit()
    db.refresh(config)
    return AlertConfigResponse.model_validate(config)


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, token: str = None, db: Session = Depends(get_db)):
    from app.services.auth_service import decode_token

    if not token:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token is missing")
        return
        
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.accept()
            await websocket.close(code=1008, reason="Invalid token type")
            return
            
        user_id = payload.get("sub")
        if not user_id:
            await websocket.accept()
            await websocket.close(code=1008, reason="Invalid token payload")
            return
            
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user or not user.is_active:
            await websocket.accept()
            await websocket.close(code=1008, reason="User unauthorized or inactive")
            return
            
        if client_id != str(user.id):
            await websocket.accept()
            await websocket.close(code=1008, reason="Client ID does not match user ID")
            return
    except Exception as e:
        await websocket.accept()
        await websocket.close(code=1008, reason=f"Authentication failed: {str(e)}")
        return

    await manager.connect(client_id, websocket)
    try:
        while True:
            # Keep connection open, ignore any incoming client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(client_id, websocket)
    except Exception as e:
        print(f"[WS] Exception for client {client_id}: {e}")
        manager.disconnect(client_id, websocket)
