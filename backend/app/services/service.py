"""数据服务发布业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "service"
REQUIRED_FIELDS = ["服务编号", "服务名称", "输出数据集"]
STATUS_ORDER = ["草稿", "待审批", "已发布", "已停用"]
ACTION_RULES = {"提交审批": "待审批", "发布服务": "已发布", "停用服务": "已停用"}
NEGATIVE_ACTIONS = ["停用服务"]


class ServiceService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("服务编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"数据服务 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于数据服务发布可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"

        # 发布动作走消费方授权领域：绑定应用授权、固化唯一当前版本并同步缓存规则。
        # 没有授权关系的演示数据（SERV-* 骨架记录）保持原有状态流转，不阻断页面操作。
        if action == "发布服务":
            from app.services.authorization import authorization_service

            service_code = str(entry.get("服务编号") or "")
            if authorization_service.list_grants(service_code):
                _, message = authorization_service.publish_service(service_code)
                if message is None:
                    return None, "服务发布失败，请检查消费方授权配置"
                refreshed = authorization_service.find_service(service_code)
                return refreshed or entry, message

        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"数据服务已{action}"
