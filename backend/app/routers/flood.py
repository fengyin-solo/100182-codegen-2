"""防汛排涝应急调度接口：汛情登记、响应启动/调整/解除，以及调度资源查询。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.flood import LEVELS, FloodService

router = APIRouter(prefix="/api/flood", tags=["防汛排涝调度"])

service = FloodService()

LIST_FIELDS = [
    "汛情编号", "预警等级", "current_level", "影响范围", "降雨情况",
    "登记人员", "status", "预警时间", "响应时间", "解除时间",
    "dispatched_truck_count", "dispatched_material_count",
]


@router.get("", response_model=PageResult[dict])
def list_entries(
    status: str | None = Query(default=None, description="预警、应急响应、已解除"),
    level: str | None = Query(default=None, description="Ⅳ级、Ⅲ级、Ⅱ级、Ⅰ级"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按状态与当前等级过滤汛情台账；汇总卡片与列表共用同一份数据。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(status=status, level=level, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/active")
def list_active() -> dict[str, Any]:
    """值班入口：返回所有未解除汛情（含预警与应急响应）。"""
    return {"items": service.active_entries()}


@router.get("/summary")
def get_summary() -> dict[str, Any]:
    """汇总卡片：与台账列表、值班入口取自同一份汛情数据。"""
    return service.summary()


@router.get("/resources")
def list_resources() -> dict[str, Any]:
    """登记响应前拉取可调度的排涝泵车与应急物资余量。"""
    return service.list_resources()


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单场汛情明细，含泵车/物资调度明细与完整状态变更记录。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"汛情 {entry_id} 不存在或已归档")
    return entry


@router.post("/warnings", response_model=ActionResult)
def create_warning(payload: EntryPayload) -> ActionResult:
    """发布汛情预警：登记预警等级、降雨情况与初始影响范围。"""
    level = str(payload.values.get("预警等级") or "").strip()
    if level not in LEVELS:
        return ActionResult(ok=False, message="预警等级必须是 Ⅳ级、Ⅲ级、Ⅱ级、Ⅰ级 之一")
    entry, missing = service.create_warning(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message=f"{level}汛情预警已发布", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """执行启动应急响应、调整响应等级、解除预警、解除应急响应。

    同级未解除响应会被拦下；解除时泵车恢复待命、物资可用数量写回物资台账。
    """
    action = str(payload.values.get("action") or "").strip()
    values = {k: v for k, v in payload.values.items() if k != "action"}
    entry, message = service.run_action(entry_id, action, values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export/all")
def export_entries() -> dict[str, Any]:
    """导出汛情调度台账全量数据，含状态变更记录。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "flood", "total": total, "items": items}
