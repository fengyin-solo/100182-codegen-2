"""防汛排涝应急调度业务规则。

一条汛情的状态流转固定为：预警中 → 响应中 → 已解除（预警也可直接解除）。
所有状态变化都会向「变更记录」追加一条不可改写的留痕；调度的排涝泵车与
应急物资在启动响应/等级调整时占用库存，在解除时按本汛情占用量原样释放，
并把可用数量写回物资台账，保证看板与台账取的是同一份数据。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

EVENT_MODULE = "flood_event"
PUMP_MODULE = "flood_pump"
MATERIAL_MODULE = "material"

STATUS_WARNING = "预警中"
STATUS_RESPONDING = "响应中"
STATUS_LIFTED = "已解除"
STATUSES = [STATUS_WARNING, STATUS_RESPONDING, STATUS_LIFTED]

WARNING_LEVELS = ["蓝色预警", "黄色预警", "橙色预警", "红色预警"]
RESPONSE_LEVELS = ["Ⅳ级响应", "Ⅲ级响应", "Ⅱ级响应", "Ⅰ级响应"]

REQUIRED_WARNING_FIELDS = ["汛情名称", "预警等级", "影响范围"]
REQUIRED_RESPONSE_FIELDS = ["响应等级", "影响范围"]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _log(entry: dict[str, Any], record: dict[str, Any]) -> None:
    """向汛情追加一条状态变更留痕（只追加，不改写历史记录）。"""
    entry.setdefault("变更记录", []).append(record)


def _stock_rows(module: str) -> list[dict[str, Any]]:
    rows = store.rows(module)
    for row in rows:
        row.setdefault("占用数量", 0)
    return rows


def _merge_allocations(
    current: list[dict[str, Any]], additions: list[dict[str, Any]], key: str
) -> list[dict[str, Any]]:
    """把本次新增调度合并进累计调度，按资源编号累加数量。"""
    merged = {int(item["材料ID"]): dict(item) for item in current}
    for item in additions:
        rid = int(item["材料ID"])
        if rid in merged:
            merged[rid]["数量"] = _as_int(merged[rid].get("数量")) + _as_int(item.get("数量"))
        else:
            merged[rid] = dict(item)
    return list(merged.values())


def _parse_allocations(raw: Any) -> list[dict[str, Any]]:
    return [item for item in (raw or []) if isinstance(item, dict) and _as_int(item.get("数量")) > 0]


class FloodService:
    # ------------------------------------------------------------------ 列表/汇总
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        level: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(EVENT_MODULE)
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("汛情编号", "")) or keyword in str(row.get("汛情名称", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if level:
            rows = [
                row for row in rows
                if row.get("响应等级") == level or row.get("预警等级") == level
            ]
        rows = sorted(rows, key=lambda row: int(row.get("id", 0)), reverse=True)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(EVENT_MODULE, entry_id)

    def summary(self) -> dict[str, Any]:
        """值班入口与台账页共用的汇总卡片，数据直接来自汛情/物资台账本身。"""
        events = store.rows(EVENT_MODULE)
        warning = [e for e in events if e.get("status") == STATUS_WARNING]
        responding = [e for e in events if e.get("status") == STATUS_RESPONDING]
        lifted = [e for e in events if e.get("status") == STATUS_LIFTED]
        pump_total = sum(
            _as_int(p.get("结存数量")) - _as_int(p.get("占用数量"))
            for p in _stock_rows(PUMP_MODULE)
        )
        material_kinds = sum(
            1 for m in _stock_rows(MATERIAL_MODULE)
            if _as_int(m.get("结存数量")) - _as_int(m.get("占用数量")) > 0
        )
        cards = [
            {"label": "在汛汛情", "value": len(warning) + len(responding)},
            {"label": "响应中", "value": len(responding)},
            {"label": "预警待响应", "value": len(warning)},
            {"label": "已解除", "value": len(lifted)},
            {"label": "泵车可用台数", "value": pump_total},
            {"label": "有库存应急物资", "value": material_kinds},
        ]
        return {"cards": cards}

    # ------------------------------------------------------------------ 资源台账
    def list_pumps(self, available_only: bool = False) -> list[dict[str, Any]]:
        rows = _stock_rows(PUMP_MODULE)
        for row in rows:
            row["可用数量"] = _as_int(row.get("结存数量")) - _as_int(row.get("占用数量"))
        if available_only:
            rows = [row for row in rows if _as_int(row.get("可用数量")) > 0]
        return rows

    def list_materials(self, available_only: bool = False) -> list[dict[str, Any]]:
        rows = _stock_rows(MATERIAL_MODULE)
        for row in rows:
            row["可用数量"] = _as_int(row.get("结存数量")) - _as_int(row.get("占用数量"))
        if available_only:
            # 冻结/耗尽的物资不参与应急调度
            rows = [
                row for row in rows
                if _as_int(row.get("可用数量")) > 0 and row.get("status") not in ("已冻结", "已耗尽")
            ]
        return rows

    def _build_pump_allocations(self, raw: Any) -> tuple[list[dict[str, Any]], str]:
        """校验泵车调度数量并生成调度明细；库存不足时返回错误说明。"""
        allocations: list[dict[str, Any]] = []
        pumps = {int(p["id"]): p for p in _stock_rows(PUMP_MODULE)}
        for item in _parse_allocations(raw):
            rid = _as_int(item.get("材料ID"))
            qty = _as_int(item.get("数量"))
            pump = pumps.get(rid)
            if pump is None:
                return [], f"排涝泵车 {rid} 不在应急车场内"
            available = _as_int(pump.get("结存数量")) - _as_int(pump.get("占用数量"))
            if qty > available:
                return [], f"排涝泵车「{pump.get('泵车名称')}」可用 {available} 台，不足以调度 {qty} 台"
            allocations.append({
                "材料ID": rid,
                "泵车编号": pump.get("泵车编号"),
                "泵车名称": pump.get("泵车名称"),
                "数量": qty,
            })
        return allocations, ""

    def _build_material_allocations(self, raw: Any) -> tuple[list[dict[str, Any]], str]:
        """校验应急物资数量并生成调度明细；可用数量不足时返回错误说明。"""
        allocations: list[dict[str, Any]] = []
        materials = {int(m["id"]): m for m in _stock_rows(MATERIAL_MODULE)}
        for item in _parse_allocations(raw):
            rid = _as_int(item.get("材料ID"))
            qty = _as_int(item.get("数量"))
            material = materials.get(rid)
            if material is None:
                return [], f"应急物资 {rid} 不在物资台账内"
            if material.get("status") in ("已冻结", "已耗尽"):
                return [], f"应急物资「{material.get('材料名称')}」当前为{material.get('status')}，不能参与调度"
            available = _as_int(material.get("结存数量")) - _as_int(material.get("占用数量"))
            if qty > available:
                return [], f"应急物资「{material.get('材料名称')}」可用 {available}，不足以调度 {qty}"
            allocations.append({
                "材料ID": rid,
                "材料编号": material.get("材料编号"),
                "材料名称": material.get("材料名称"),
                "数量": qty,
            })
        return allocations, ""

    def _occupy(self, pump_adds: list[dict[str, Any]], material_adds: list[dict[str, Any]]) -> None:
        """占用泵车/物资库存，并把应急物资标记为占用状态。"""
        pumps = {int(p["id"]): p for p in _stock_rows(PUMP_MODULE)}
        for item in pump_adds:
            pumps[int(item["材料ID"])]["占用数量"] = _as_int(pumps[int(item["材料ID"])].get("占用数量")) + _as_int(item["数量"])
        materials = {int(m["id"]): m for m in _stock_rows(MATERIAL_MODULE)}
        for item in material_adds:
            row = materials[int(item["材料ID"])]
            row["占用数量"] = _as_int(row.get("占用数量")) + _as_int(item["数量"])
            if _as_int(row.get("占用数量")) > 0:
                row["status"] = "应急占用"
                row["材料状态"] = "应急占用"
                row["pending"] = True

    def _release(self, entry: dict[str, Any]) -> None:
        """解除时把本汛情调度的泵车、物资全部归还台账并恢复可用状态。"""
        pumps = {int(p["id"]): p for p in _stock_rows(PUMP_MODULE)}
        for item in entry.get("泵车调度", []):
            row = pumps.get(int(item["材料ID"]))
            if row is None:
                continue
            row["占用数量"] = max(0, _as_int(row.get("占用数量")) - _as_int(item["数量"]))
        materials = {int(m["id"]): m for m in _stock_rows(MATERIAL_MODULE)}
        for item in entry.get("物资调度", []):
            row = materials.get(int(item["材料ID"]))
            if row is None:
                continue
            row["占用数量"] = max(0, _as_int(row.get("占用数量")) - _as_int(item["数量"]))
            if _as_int(row.get("占用数量")) == 0 and row.get("status") == "应急占用":
                row["status"] = "正常可用"
                row["材料状态"] = "正常可用"

    # ------------------------------------------------------------------ 状态流转
    def issue_warning(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """发布预警：汛情进入「预警中」，等待启动响应或直接解除。"""
        missing = [field for field in REQUIRED_WARNING_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        warning_level = str(values.get("预警等级")).strip()
        if warning_level not in WARNING_LEVELS:
            return None, f"预警等级「{warning_level}」不合法，应为：{'、'.join(WARNING_LEVELS)}"
        rows = store.rows(EVENT_MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({
            "汛情编号": f"FLD-{datetime.now().strftime('%Y')}-{entry['id']:04d}",
            "汛情名称": str(values.get("汛情名称")).strip(),
            "预警等级": warning_level,
            "响应等级": "",
            "影响范围": str(values.get("影响范围")).strip(),
            "值班人员": str(values.get("值班人员") or "值班管理员").strip(),
            "status": STATUS_WARNING,
            "pending": True,
            "abnormal": False,
            "发布时间": _now(),
            "响应时间": "",
            "调整时间": "",
            "解除时间": "",
            "泵车调度": [],
            "物资调度": [],
            "变更记录": [],
        })
        _log(entry, {
            "时间": entry["发布时间"],
            "动作": "发布预警",
            "由状态": "",
            "到状态": STATUS_WARNING,
            "响应等级": warning_level,
            "影响范围": entry["影响范围"],
            "值班人员": entry["值班人员"],
            "说明": str(values.get("说明") or "发布防汛预警，值班岗进入值守").strip(),
        })
        rows.append(entry)
        return entry, "汛情预警已发布"

    def start_response(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """启动响应：预警中 → 响应中，登记等级、影响范围并占用泵车物资。"""
        entry = store.find(EVENT_MODULE, entry_id)
        if entry is None:
            return None, f"汛情 {entry_id} 不存在"
        if entry.get("status") == STATUS_RESPONDING:
            # 未解除的响应不能被同级响应覆盖：需要先调整等级或解除。
            current = entry.get("响应等级")
            if str(values.get("响应等级") or "").strip() == current:
                return None, f"该汛情已有未解除的{current}，同级响应不能重复登记，请改走「等级调整」或先解除"
            return None, f"该汛情已有未解除的{current}，不能再次启动响应，请通过「等级调整」变更等级"
        if entry.get("status") == STATUS_LIFTED:
            return None, "该汛情已解除，不能再启动响应；如出现新汛情请重新发布预警"

        missing = [field for field in REQUIRED_RESPONSE_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        level = str(values.get("响应等级")).strip()
        if level not in RESPONSE_LEVELS:
            return None, f"响应等级「{level}」不合法，应为：{'、'.join(RESPONSE_LEVELS)}"
        scope = str(values.get("影响范围")).strip()
        operator = str(values.get("值班人员") or entry.get("值班人员") or "值班管理员").strip()

        pump_adds, message = self._build_pump_allocations(values.get("泵车调度"))
        if message:
            return None, message
        material_adds, message = self._build_material_allocations(values.get("物资调度"))
        if message:
            return None, message

        # 校验全部通过后再占用库存、改写状态
        self._occupy(pump_adds, material_adds)
        timestamp = _now()
        entry.update({
            "status": STATUS_RESPONDING,
            "pending": True,
            "abnormal": True,
            "响应等级": level,
            "影响范围": scope,
            "值班人员": operator,
            "响应时间": timestamp,
        })
        entry["泵车调度"] = _merge_allocations(entry.get("泵车调度", []), pump_adds, "泵车编号")
        entry["物资调度"] = _merge_allocations(entry.get("物资调度", []), material_adds, "材料编号")
        _log(entry, {
            "时间": timestamp,
            "动作": "启动响应",
            "由状态": STATUS_WARNING,
            "到状态": STATUS_RESPONDING,
            "响应等级": level,
            "影响范围": scope,
            "值班人员": operator,
            "说明": str(values.get("说明") or f"启动{level}，调度排涝力量赶赴现场").strip(),
            "泵车调度": pump_adds,
            "物资调度": material_adds,
        })
        return entry, f"{level}已启动，泵车与应急物资已占用调度"

    def adjust_level(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """等级调整：仅响应中可调整；同级调整不允许，追加的调度继续占用库存。"""
        entry = store.find(EVENT_MODULE, entry_id)
        if entry is None:
            return None, f"汛情 {entry_id} 不存在"
        if entry.get("status") != STATUS_RESPONDING:
            return None, f"汛情当前为「{entry.get('status')}」，只有响应中的汛情才能调整等级"
        previous = entry.get("响应等级")
        target = str(values.get("响应等级") or "").strip()
        if target not in RESPONSE_LEVELS:
            return None, f"响应等级「{target}」不合法，应为：{'、'.join(RESPONSE_LEVELS)}"
        if target == previous:
            return None, f"当前已是{previous}，同级调整不会被记录，请选择更高或更低的响应等级"

        pump_adds, message = self._build_pump_allocations(values.get("泵车调度"))
        if message:
            return None, message
        material_adds, message = self._build_material_allocations(values.get("物资调度"))
        if message:
            return None, message

        self._occupy(pump_adds, material_adds)
        timestamp = _now()
        scope = str(values.get("影响范围") or entry.get("影响范围") or "").strip()
        operator = str(values.get("值班人员") or entry.get("值班人员") or "值班管理员").strip()
        entry.update({"响应等级": target, "调整时间": timestamp})
        if scope:
            entry["影响范围"] = scope
        entry["泵车调度"] = _merge_allocations(entry.get("泵车调度", []), pump_adds, "泵车编号")
        entry["物资调度"] = _merge_allocations(entry.get("物资调度", []), material_adds, "材料编号")
        _log(entry, {
            "时间": timestamp,
            "动作": "等级调整",
            "由状态": STATUS_RESPONDING,
            "到状态": STATUS_RESPONDING,
            "响应等级": f"{previous} → {target}",
            "影响范围": entry.get("影响范围"),
            "值班人员": operator,
            "说明": str(values.get("说明") or f"响应等级由{previous}调整为{target}").strip(),
            "泵车调度": pump_adds,
            "物资调度": material_adds,
        })
        return entry, f"响应等级已由{previous}调整为{target}"

    def lift(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """解除：释放本汛情占用的全部泵车与物资，物资恢复可用并写回台账。"""
        entry = store.find(EVENT_MODULE, entry_id)
        if entry is None:
            return None, f"汛情 {entry_id} 不存在"
        if entry.get("status") == STATUS_LIFTED:
            return None, "该汛情已解除，不能重复解除"
        previous_status = entry.get("status")
        self._release(entry)
        timestamp = _now()
        operator = str(values.get("值班人员") or entry.get("值班人员") or "值班管理员").strip()
        entry.update({
            "status": STATUS_LIFTED,
            "pending": False,
            "abnormal": False,
            "解除时间": timestamp,
            "值班人员": operator,
        })
        _log(entry, {
            "时间": timestamp,
            "动作": "解除响应" if previous_status == STATUS_RESPONDING else "解除预警",
            "由状态": previous_status,
            "到状态": STATUS_LIFTED,
            "响应等级": entry.get("响应等级") or entry.get("预警等级"),
            "影响范围": entry.get("影响范围"),
            "值班人员": operator,
            "说明": str(values.get("说明") or "积水退尽、现场恢复，调度泵车归库、应急物资恢复可用").strip(),
        })
        return entry, "汛情已解除，调度泵车已归库，应急物资可用数量已写回物资台账"


flood_service = FloodService()
