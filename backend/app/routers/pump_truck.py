"""排涝泵车接口：维护可调度的移动排涝泵车台账。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.pump_truck import PumpTruckService

router = APIRouter(prefix="/api/pump-truck", tags=["排涝泵车"])

service = PumpTruckService()

LIST_FIELDS = ["泵车编号", "泵车型号", "排涝流量", "停放场地", "责任人", "状态", "占用汛情"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    status: str | None = Query(default=None, description="待命、调度中"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按状态过滤排涝泵车；调度中的泵车会标注占用汛情编号。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一台排涝泵车，初始状态为待命。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="排涝泵车已登记", entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出排涝泵车清单。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "pump_truck", "total": total, "items": items}
