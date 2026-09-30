"""防汛排涝应急调度接口：发布预警、启动/调整/解除响应，泵车物资台账与汇总卡片。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    ActionResult,
    FloodAdjustPayload,
    FloodLiftPayload,
    FloodResponsePayload,
    FloodWarningPayload,
    PageResult,
)
from app.services.flood import RESPONSE_LEVELS, STATUSES, WARNING_LEVELS, flood_service

router = APIRouter(prefix="/api/flood", tags=["防汛排涝调度"])


@router.get("/summary")
def summary() -> dict[str, Any]:
    """值班入口与台账页共用的汇总卡片，取自汛情与物资台账同一份数据。"""
    return flood_service.summary()


@router.get("/pumps")
def list_pumps(available_only: bool = Query(default=False, description="只返回尚有可用数量的泵车")) -> dict[str, Any]:
    """排涝泵车台账：返回结存、占用与可用数量。"""
    return {"items": flood_service.list_pumps(available_only=available_only)}


@router.get("/materials")
def list_materials(available_only: bool = Query(default=False, description="只返回尚有可用数量的应急物资")) -> dict[str, Any]:
    """可供调度的应急物资：可用数量由物资台账实时算出。"""
    return {"items": flood_service.list_materials(available_only=available_only)}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按汛情编号或名称检索"),
    status: str | None = Query(default=None, description=f"{'、'.join(STATUSES)}"),
    level: str | None = Query(default=None, description="按响应/预警等级过滤"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """汛情台账列表，按登记时间倒序；每条含完整变更记录与调度明细。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = flood_service.list_entries(keyword=keyword, status=status, level=level, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/meta/options")
def options() -> dict[str, Any]:
    """前端表单的等级、状态候选项。"""
    return {"statuses": STATUSES, "warning_levels": WARNING_LEVELS, "response_levels": RESPONSE_LEVELS}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条汛情的完整台账与状态变更记录。"""
    entry = flood_service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"汛情 {entry_id} 不存在")
    return entry


@router.post("/warning", response_model=ActionResult)
def issue_warning(payload: FloodWarningPayload) -> ActionResult:
    """发布汛情预警，汛情进入「预警中」并留下第一条变更记录。"""
    entry, message = flood_service.issue_warning(payload.model_dump())
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/response", response_model=ActionResult)
def start_response(entry_id: int, payload: FloodResponsePayload) -> ActionResult:
    """启动应急响应：登记响应等级、影响范围与调度的泵车、物资数量。"""
    values = payload.model_dump()
    values["泵车调度"] = [item.model_dump() for item in payload.泵车调度]
    values["物资调度"] = [item.model_dump() for item in payload.物资调度]
    entry, message = flood_service.start_response(entry_id, values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/adjust", response_model=ActionResult)
def adjust_level(entry_id: int, payload: FloodAdjustPayload) -> ActionResult:
    """调整响应等级并追加留痕；同级调整会被拒绝，可追加调度资源。"""
    values = payload.model_dump()
    values["泵车调度"] = [item.model_dump() for item in payload.泵车调度]
    values["物资调度"] = [item.model_dump() for item in payload.物资调度]
    entry, message = flood_service.adjust_level(entry_id, values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/lift", response_model=ActionResult)
def lift(entry_id: int, payload: FloodLiftPayload) -> ActionResult:
    """解除汛情：归还全部泵车物资，物资可用数量写回物资台账。"""
    entry, message = flood_service.lift(entry_id, payload.model_dump())
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
