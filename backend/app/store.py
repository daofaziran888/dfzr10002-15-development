"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.seed import SEED_ROWS

# 消费方授权相关的运行时表：种子数据只给初始状态，运行过程中由授权领域服务维护。
AUTH_TABLES = (
    "consumer_app",        # 消费应用台账
    "consumer_grant",      # 消费方授权（显式授权 / 默认继承 / 紧急撤权）
    "service_version",     # 数据服务发布版本（同一服务仅一个当前版本）
    "cache_entry",         # 按应用隔离的运行时缓存条目
    "service_call_log",    # 服务调用记录（保留调用时的授权快照）
)


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }

    def reset(self) -> None:
        """恢复到种子初始状态；主要供自动化测试隔离用例使用。"""
        self._tables = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }

    def snapshot(self, module: str) -> list[dict[str, Any]]:
        """深拷贝一份表数据，避免调用方直接改到仓库内部状态。"""
        return [deepcopy(row) for row in self.rows(module)]

    def next_id(self, module: str) -> int:
        """生成模块内自增主键。"""
        return max((int(row.get("id", 0)) for row in self.rows(module)), default=0) + 1

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
