"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

from typing import Any

from app.seed import SEED_ROWS

# 运营概览里模块名默认显示表名，这里给出业务中文名，缺失时回落到表名。
MODULE_LABELS = {
    "pipe": "管段档案",
    "manhole": "检查井",
    "valve": "阀门井室",
    "pumpstation": "泵站设施",
    "patrol": "巡查任务",
    "defect": "缺陷登记",
    "cctv": "内窥检测",
    "repair": "修复施工",
    "pressure": "压力监测",
    "flow": "流量监测",
    "leak": "泄漏排查",
    "dredge": "清淤疏浚",
    "material": "养护材料",
    "equip": "养护机械",
    "traffic": "占道许可",
    "complaint": "公众诉求",
    "fund": "养护资金",
    "archive": "管网档案",
    "flood": "防汛调度",
    "pump_truck": "排涝泵车",
}


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "label": MODULE_LABELS.get(name, name),
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
