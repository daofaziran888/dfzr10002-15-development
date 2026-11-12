"""消费方授权接口。

覆盖授权清单维护、紧急撤权、服务发布（版本管理）、消费调用鉴权、
授权清单导入与差异文件下载，以及缓存条目/调用记录/版本的查询。
"""
from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.schemas import (
    ActionResult,
    EmergencyRevokePayload,
    GrantImportPayload,
    GrantUpsertPayload,
    ServiceCallPayload,
)
from app.services.authorization import authorization_service

router = APIRouter(prefix="/api/consumer-auth", tags=["消费方授权"])

# 最近一次导入生成的差异文件，供「导入结束后下载差异文件」使用。
_last_diff: dict[str, list[dict[str, Any]]] = {}


@router.get("/apps")
def list_apps() -> dict[str, Any]:
    """消费应用台账。"""
    return {"items": authorization_service.list_apps(), "total": len(authorization_service.list_apps())}


@router.get("/grants")
def list_grants(
    service_code: str | None = Query(default=None, description="按服务编号过滤"),
    app_code: str | None = Query(default=None, description="按应用编号过滤"),
) -> dict[str, Any]:
    """消费方授权列表（含生效字段与待发布暂存）。"""
    items = authorization_service.list_grants(service_code)
    if app_code:
        items = [row for row in items if row.get("应用编号") == app_code]
    return {"items": items, "total": len(items)}


@router.post("/grants", response_model=ActionResult)
def upsert_grant(payload: GrantUpsertPayload) -> ActionResult:
    """登记或调整显式授权/默认继承授权；变更进入待发布，重新发布后生效。"""
    entry, message = authorization_service.upsert_grant(
        payload.服务编号, payload.应用编号, payload.响应字段,
        payload.缓存范围, payload.授权类型,
    )
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/emergency-revoke", response_model=ActionResult)
def emergency_revoke(payload: EmergencyRevokePayload) -> ActionResult:
    """紧急撤权：立即拒绝该应用调用并失效其缓存，优先级高于默认继承。"""
    entry, message = authorization_service.emergency_revoke(
        payload.服务编号, payload.应用编号, payload.撤权原因,
    )
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/publish/{service_code}", response_model=ActionResult)
def publish_service(service_code: str, payload: dict[str, Any] | None = None) -> ActionResult:
    """发布/重新发布服务：固化授权快照、归档旧版本、同步缓存规则。"""
    remark = (payload or {}).get("remark")
    entry, message = authorization_service.publish_service(service_code, remark)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/versions")
def list_versions(service_code: str | None = Query(default=None)) -> dict[str, Any]:
    """服务版本列表，可验证同一服务始终只有一个当前版本。"""
    items = authorization_service.list_versions(service_code)
    current = [row for row in items if row.get("是否当前版本")]
    return {
        "items": items,
        "total": len(items),
        "当前版本数": len(current),
    }


@router.post("/call")
def call_service(payload: ServiceCallPayload) -> dict[str, Any]:
    """消费应用调用数据服务：未授权/已撤权返回 403，授权通过则按字段权限返回并隔离缓存。"""
    body, status = authorization_service.call_service(
        payload.服务编号, payload.应用编号, payload.查询参数,
    )
    if status != 200:
        raise HTTPException(status_code=status, detail=body)
    return body


@router.get("/cache-entries")
def list_cache_entries(
    service_code: str | None = Query(default=None),
    app_code: str | None = Query(default=None),
) -> dict[str, Any]:
    """运行时缓存条目：可观察不同应用的缓存键彼此隔离、撤权后条目失效。"""
    items = authorization_service.list_cache_entries(service_code, app_code)
    return {"items": items, "total": len(items)}


@router.get("/call-logs")
def list_call_logs(
    service_code: str | None = Query(default=None),
    app_code: str | None = Query(default=None),
) -> dict[str, Any]:
    """服务调用记录：保留调用当时的应用授权快照。"""
    items = authorization_service.list_call_logs(service_code, app_code)
    return {"items": items, "total": len(items)}


@router.post("/import")
def import_grants(payload: GrantImportPayload) -> dict[str, Any]:
    """发布前上传消费方授权清单（应用编号、响应字段、缓存范围），返回差异结果。"""
    rows = [row.model_dump() for row in payload.清单]
    summary, diff_rows, message = authorization_service.import_grants(payload.服务编号, rows)
    if summary is None:
        raise HTTPException(status_code=400, detail=message)
    _last_diff.clear()
    _last_diff[payload.服务编号] = diff_rows
    return {"ok": True, "message": message, **summary}


@router.get("/import/diff-download")
def download_diff(service_code: str = Query(..., description="按服务编号下载最近一次导入差异")) -> StreamingResponse:
    """导入结束后下载差异文件（CSV），字段权限与待发布的服务版本一致。"""
    diff_rows = _last_diff.get(service_code)
    if not diff_rows:
        raise HTTPException(status_code=404, detail=f"服务 {service_code} 暂无导入差异，请先上传授权清单")

    buffer = io.StringIO()
    headers = ["应用编号", "授权类型", "响应字段", "缓存范围", "差异类型", "库中原值", "导入后值"]
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    for row in diff_rows:
        writer.writerow({key: row.get(key, "") for key in headers})
    buffer.seek(0)
    data = buffer.getvalue().encode("utf-8-sig")
    filename = f"grant-diff-{service_code}.csv"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/sync-cache-rules", response_model=ActionResult)
def sync_cache_rules() -> ActionResult:
    """手动触发缓存管理模块规则同步（发布与撤权时已自动同步）。"""
    count = authorization_service.sync_all_cache_rules()
    return ActionResult(ok=True, message=f"已同步 {count} 条授权对应的缓存规则")
