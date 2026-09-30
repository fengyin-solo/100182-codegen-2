"""排涝泵车业务规则：泵车台账维护与待命/调度状态展示。

占用与回退由防汛调度服务（flood）在启动、调整、解除响应时统一维护，
本模块只负责台账查询与登记，避免两个模块互相写状态。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "pump_truck"
REQUIRED_FIELDS = ["泵车编号", "泵车型号", "排涝流量"]


class PumpTruckService:
    def list_entries(
        self,
        *,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["停放场地"] = str(values.get("停放场地") or "").strip()
        entry["责任人"] = str(values.get("责任人") or "").strip()
        entry["status"] = "待命"
        entry["状态"] = "待命"
        entry["占用汛情"] = None
        entry["pending"] = False
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []
