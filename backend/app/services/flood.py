"""防汛排涝应急调度业务规则：汛情状态流转、调度资源占用与回退都收在这里。

一条汛情（flood）的状态序列：预警 -> 应急响应 -> 已解除。
- 预警阶段登记汛情与影响范围；
- 响应阶段登记响应等级、影响范围，调度排涝泵车与应急物资（占用资源）；
- 等级调整只改等级、影响范围，可追加调度泵车与物资，原调度继续占用；
- 解除后泵车回到待命、物资可用数量写回物资台账，并逐条留下状态变更记录。

为防止同一等级的多场响应互相抢占资源，未解除的记录不能被同级响应覆盖：
启动响应或调整到某一等级时，只要存在其它处于该等级的未解除响应，一律拦下。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "flood"
TRUCK_MODULE = "pump_truck"
MATERIAL_MODULE = "material"

REQUIRED_WARNING_FIELDS = ["汛情编号", "预警等级", "降雨情况"]
REQUIRED_RESPONSE_FIELDS = ["响应等级", "影响范围"]
LEVELS = ["Ⅳ级", "Ⅲ级", "Ⅱ级", "Ⅰ级"]
STATUS_WARNING = "预警"
STATUS_RESPONSE = "应急响应"
STATUS_CLOSED = "已解除"
TERMINATED_RESOURCE_STATUS = "已解除回收"
TRUCK_READY_STATUS = "待命"
MATERIAL_READY_STATUS = "正常可用"
# 已冻结/已耗尽的物资即使账面有数量也不允许占用。
MATERIAL_BLOCKED_STATUSES = {"已冻结", "已耗尽"}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


class FloodService:
    # ------------------------------------------------------------------ 查询
    def list_entries(
        self,
        *,
        status: str | None = None,
        level: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if level:
            rows = [row for row in rows if row.get("current_level") == level]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def active_entries(self) -> list[dict[str, Any]]:
        """值班入口只关心未解除的汛情，按登记时间倒序返回。"""
        rows = [row for row in store.rows(MODULE) if row.get("status") != STATUS_CLOSED]
        return sorted(rows, key=lambda row: int(row.get("id", 0)), reverse=True)

    def summary(self) -> dict[str, Any]:
        """汇总卡片与台账取自同一份数据：统计口径只在这里算一遍。"""
        rows = store.rows(MODULE)
        active = [row for row in rows if row.get("status") != STATUS_CLOSED]
        responding = [row for row in active if row.get("status") == STATUS_RESPONSE]
        warning = [row for row in active if row.get("status") == STATUS_WARNING]
        trucks = sum(int(row.get("dispatched_truck_count", 0)) for row in responding)
        occupied_materials = sum(
            int(item.get("数量", 0))
            for row in responding
            for item in row.get("materials", [])
            if item.get("状态") != TERMINATED_RESOURCE_STATUS
        )
        level_distribution = {
            level: sum(1 for row in responding if row.get("current_level") == level)
            for level in LEVELS
        }
        return {
            "cards": [
                {"label": "未解除汛情", "value": len(active)},
                {"label": "预警中", "value": len(warning)},
                {"label": "应急响应中", "value": len(responding)},
                {"label": "调度泵车(台)", "value": trucks},
                {"label": "占用物资(件)", "value": occupied_materials},
            ],
            "level_distribution": level_distribution,
        }

    # ------------------------------------------------------------------ 登记
    def create_warning(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [f for f in REQUIRED_WARNING_FIELDS if not str(values.get(f) or "").strip()]
        if missing:
            return None, missing
        level = str(values.get("预警等级")).strip()
        if level not in LEVELS:
            return None, []
        rows = store.rows(MODULE)
        entry = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "汛情编号": str(values.get("汛情编号")).strip(),
            "预警等级": level,
            "current_level": level,
            "降雨情况": str(values.get("降雨情况")).strip(),
            "影响范围": str(values.get("影响范围") or "").strip(),
            "登记人员": str(values.get("登记人员") or "值班管理员").strip(),
            "status": STATUS_WARNING,
            "pending": True,
            "abnormal": True,
            "预警时间": _now(),
            "响应时间": None,
            "解除时间": None,
            "trucks": [],
            "materials": [],
            "dispatched_truck_count": 0,
            "dispatched_material_count": 0,
            "change_logs": [],
        }
        entry["change_logs"].append(self._log(
            entry, STATUS_WARNING, STATUS_WARNING,
            f"发布{level}预警，影响范围：{entry['影响范围'] or '待划定'}",
        ))
        rows.append(entry)
        return entry, []

    # ------------------------------------------------------------------ 动作
    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"汛情 {entry_id} 不存在或已归档"
        if action == "启动应急响应":
            return self._start_response(entry, values)
        if action == "调整响应等级":
            return self._adjust_level(entry, values)
        if action == "解除预警":
            if entry["status"] != STATUS_WARNING:
                return None, "仅预警阶段可以解除预警，已启动响应的汛情请先解除响应"
            return self._close(entry, "解除预警", values)
        if action == "解除应急响应":
            if entry["status"] != STATUS_RESPONSE:
                return None, "仅应急响应中的汛情可以解除响应"
            return self._close(entry, "解除应急响应", values)
        return None, f"动作「{action}」不属于防汛调度可执行范围"

    # ----------------------------------------------------------- 启动/调整响应
    def _start_response(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        if entry["status"] != STATUS_WARNING:
            return None, f"汛情当前为「{entry['status']}」，只有预警中的汛情才能启动应急响应"
        level = str(values.get("响应等级") or "").strip()
        if level not in LEVELS:
            return None, "响应等级必须是 Ⅳ级、Ⅲ级、Ⅱ级、Ⅰ级 之一"
        scope = str(values.get("影响范围") or "").strip()
        missing = [f for f in REQUIRED_RESPONSE_FIELDS if not str(values.get(f) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        blocked = self._blocked_by_same_level(level, exclude_id=int(entry["id"]))
        if blocked:
            return None, (
                f"存在未解除的{level}响应（汛情 {blocked['汛情编号']}，影响范围：{blocked['影响范围']}），"
                f"同级响应不能覆盖，请先解除或调整该场响应"
            )

        # 启动响应必须落实排涝力量：至少调度一台排涝泵车。
        if not (values.get("trucks") or []):
            return None, "启动应急响应至少需要调度 1 台排涝泵车"

        dispatch, message = self._dispatch(entry, values)
        if message:
            return None, message

        entry["status"] = STATUS_RESPONSE
        entry["current_level"] = level
        entry["影响范围"] = scope
        entry["响应时间"] = _now()
        entry["change_logs"].append(self._log(
            entry, STATUS_WARNING, STATUS_RESPONSE,
            f"启动{level}应急响应，影响范围：{scope}；"
            f"调度泵车 {dispatch['trucks']} 台、应急物资 {dispatch['materials']} 件，"
            f"物资可用数量已同步扣减",
        ))
        return entry, f"{level}应急响应已启动"

    def _adjust_level(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        if entry["status"] != STATUS_RESPONSE:
            return None, "仅应急响应中的汛情可以调整响应等级"
        new_level = str(values.get("响应等级") or "").strip()
        if new_level not in LEVELS:
            return None, "目标响应等级必须是 Ⅳ级、Ⅲ级、Ⅱ级、Ⅰ级 之一"
        old_level = str(entry.get("current_level"))
        if new_level == old_level:
            return None, f"当前已是{new_level}，同级调整会覆盖进行中的响应，已拦下；如需加派资源请追加调度"
        blocked = self._blocked_by_same_level(new_level, exclude_id=int(entry["id"]))
        if blocked:
            return None, (
                f"存在未解除的{new_level}响应（汛情 {blocked['汛情编号']}），"
                f"调整后会与同级响应冲突，已拦下"
            )

        # 等级调整允许加派资源；原调度记录保持占用。
        dispatch, message = self._dispatch(entry, values)
        if message:
            return None, message

        scope = str(values.get("影响范围") or entry.get("影响范围") or "").strip()
        entry["current_level"] = new_level
        if scope:
            entry["影响范围"] = scope
        extra = ""
        if dispatch["trucks"] or dispatch["materials"]:
            extra = (
                f"；本次加派泵车 {dispatch['trucks']} 台、物资 {dispatch['materials']} 件，"
                f"加派物资可用数量已同步扣减"
            )
        entry["change_logs"].append(self._log(
            entry, f"{old_level}响应", f"{new_level}响应",
            f"响应等级由{old_level}调整为{new_level}，影响范围：{entry['影响范围']}"
            f"{extra}；累计在调泵车 {entry['dispatched_truck_count']} 台、"
            f"占用物资 {entry['dispatched_material_count']} 件",
        ))
        return entry, f"响应等级已调整为{new_level}"

    # ------------------------------------------------------------- 解除与回退
    def _close(self, entry: dict[str, Any], action: str, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        before_status = entry["status"]
        released_trucks = 0
        released_materials = 0
        for item in entry["trucks"]:
            if item.get("状态") == TERMINATED_RESOURCE_STATUS:
                continue
            truck = store.find(TRUCK_MODULE, int(item["泵车id"]))
            if truck is not None:
                truck["状态"] = TRUCK_READY_STATUS
                truck["status"] = TRUCK_READY_STATUS
                truck["占用汛情"] = None
            item["状态"] = TERMINATED_RESOURCE_STATUS
            released_trucks += 1
        for item in entry["materials"]:
            if item.get("状态") == TERMINATED_RESOURCE_STATUS:
                continue
            material = store.find(MATERIAL_MODULE, int(item["物资id"]))
            if material is not None:
                # 可用数量写回物资台账：解除后物资回到可用状态。
                material["可用数量"] = int(material.get("可用数量", 0)) + int(item["数量"])
                if material.get("status") == "占用中":
                    material["status"] = MATERIAL_READY_STATUS
                    material["材料状态"] = MATERIAL_READY_STATUS
            item["状态"] = TERMINATED_RESOURCE_STATUS
            released_materials += int(item["数量"])

        entry["status"] = STATUS_CLOSED
        entry["current_level"] = "已解除"
        entry["pending"] = False
        entry["abnormal"] = False
        entry["解除时间"] = _now()
        entry["解除说明"] = str(values.get("解除说明") or "").strip()
        entry["change_logs"].append(self._log(
            entry, before_status, STATUS_CLOSED,
            f"{action}，回收泵车 {released_trucks} 台、回库物资 {released_materials} 件，"
            f"可用数量已写回物资台账"
            + (f"；说明：{entry['解除说明']}" if entry["解除说明"] else ""),
        ))
        return entry, f"汛情已解除，{released_trucks} 台泵车恢复待命、{released_materials} 件物资回库"

    # ------------------------------------------------------------- 资源调度
    def _dispatch(
        self, entry: dict[str, Any], values: dict[str, Any]
    ) -> tuple[dict[str, int], str]:
        """按提交的泵车/物资清单占用资源；返回 (本次调度汇总, 错误信息)。

        状态变更记录由调用方在状态真正切换后统一追加，保证日志顺序与状态一致。
        """
        trucks = values.get("trucks") or []
        materials = values.get("materials") or []
        if not isinstance(trucks, list) or not isinstance(materials, list):
            return {}, "调度清单格式不正确"

        occupied_truck_ids: set[int] = set()
        material_totals: dict[int, int] = {}
        for item in trucks:
            truck_id = self._to_int(item.get("truck_id") if isinstance(item, dict) else item)
            if truck_id is None:
                return {}, "调度清单中存在未选择的排涝泵车"
            occupied_truck_ids.add(truck_id)
        for item in materials:
            if not isinstance(item, dict):
                return {}, "物资调度清单格式不正确"
            material_id = self._to_int(item.get("material_id"))
            quantity = self._to_int(item.get("quantity"))
            if material_id is None:
                return {}, "物资调度清单中存在未选择的应急物资"
            if quantity is None or quantity <= 0:
                return {}, f"物资「{item.get('material_name') or material_id}」的调度数量须为正整数"
            material_totals[material_id] = material_totals.get(material_id, 0) + quantity

        # 校验全部通过后再落库，避免出现占用一半的半成品状态。
        for truck_id in occupied_truck_ids:
            truck = store.find(TRUCK_MODULE, truck_id)
            if truck is None:
                return {}, f"排涝泵车 {truck_id} 不存在"
            if truck.get("状态") != TRUCK_READY_STATUS:
                return {}, f"泵车「{truck.get('泵车编号')}」当前为{truck.get('状态')}，无法重复调度"
        for material_id, quantity in material_totals.items():
            material = store.find(MATERIAL_MODULE, material_id)
            if material is None:
                return {}, f"应急物资 {material_id} 不存在"
            if material.get("status") in MATERIAL_BLOCKED_STATUSES:
                return {}, f"物资「{material.get('材料名称')}」当前为{material.get('status')}状态，禁止调度占用"
            available = int(material.get("可用数量", 0))
            if quantity > available:
                return {}, (
                    f"物资「{material.get('材料名称')}」可用数量不足：申请 {quantity}，"
                    f"当前仅可用 {available}（可能已被其它未解除响应占用）"
                )

        operator = str(values.get("登记人员") or entry.get("登记人员") or "值班管理员").strip()
        for truck_id in occupied_truck_ids:
            truck = store.find(TRUCK_MODULE, truck_id)
            truck["状态"] = "调度中"
            truck["status"] = "调度中"
            truck["占用汛情"] = entry["汛情编号"]
            entry["trucks"].append({
                "泵车id": truck_id,
                "泵车编号": truck.get("泵车编号"),
                "泵车型号": truck.get("泵车型号"),
                "排涝流量": truck.get("排涝流量"),
                "调度时间": _now(),
                "调度人": operator,
                "状态": "占用中",
            })
        for material_id, quantity in material_totals.items():
            material = store.find(MATERIAL_MODULE, material_id)
            material["可用数量"] = int(material.get("可用数量", 0)) - quantity
            if material["可用数量"] == 0:
                material["status"] = "占用中"
                material["材料状态"] = "占用中"
            entry["materials"].append({
                "物资id": material_id,
                "材料编号": material.get("材料编号"),
                "材料名称": material.get("材料名称"),
                "数量": quantity,
                "计量单位": material.get("计量单位"),
                "调度时间": _now(),
                "调度人": operator,
                "状态": "占用中",
            })

        # 汇总字段供列表/卡片直接展示，明细始终以 trucks、materials 为准。
        entry["dispatched_truck_count"] = self._active_truck_quantity(entry)
        entry["dispatched_material_count"] = self._active_material_quantity(entry)
        return {"trucks": len(occupied_truck_ids), "materials": sum(material_totals.values())}, ""

    # ------------------------------------------------------------- 资源台账
    def list_resources(self) -> dict[str, Any]:
        """登记响应时选择泵车与物资：只返回可调度的泵车与仍有可用数量的物资。"""
        trucks = [
            {
                "id": row["id"],
                "泵车编号": row.get("泵车编号"),
                "泵车型号": row.get("泵车型号"),
                "排涝流量": row.get("排涝流量"),
                "停放场地": row.get("停放场地"),
                "状态": row.get("状态"),
                "占用汛情": row.get("占用汛情"),
            }
            for row in store.rows(TRUCK_MODULE)
        ]
        materials = [
            {
                "id": row["id"],
                "材料编号": row.get("材料编号"),
                "材料名称": row.get("材料名称"),
                "规格型号": row.get("规格型号"),
                "结存数量": row.get("结存数量"),
                "可用数量": row.get("可用数量"),
                "计量单位": row.get("计量单位"),
                "存放场地": row.get("存放场地"),
                "状态": row.get("status"),
            }
            for row in store.rows(MATERIAL_MODULE)
        ]
        return {"trucks": trucks, "materials": materials}

    # ------------------------------------------------------------------ 工具
    def _blocked_by_same_level(self, level: str, exclude_id: int) -> dict[str, Any] | None:
        """未解除的记录不能被同级响应覆盖：找一条处于该等级的在响汛情。"""
        for row in store.rows(MODULE):
            if int(row.get("id", 0)) == exclude_id:
                continue
            if row.get("status") == STATUS_RESPONSE and row.get("current_level") == level:
                return row
        return None

    def _log(self, entry: dict[str, Any], from_status: str, to_status: str, detail: str) -> dict[str, Any]:
        return {
            "时间": _now(),
            "操作人": entry.get("登记人员") or "值班管理员",
            "变更前": from_status,
            "变更后": to_status,
            "说明": detail,
        }

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            result = int(value)
        except (TypeError, ValueError):
            return None
        return result if result > 0 else None

    def _active_truck_quantity(self, entry: dict[str, Any]) -> int:
        return sum(1 for item in entry["trucks"] if item.get("状态") != TERMINATED_RESOURCE_STATUS)

    def _active_material_quantity(self, entry: dict[str, Any]) -> int:
        return sum(
            int(item.get("数量", 0))
            for item in entry["materials"]
            if item.get("状态") != TERMINATED_RESOURCE_STATUS
        )
