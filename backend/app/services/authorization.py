"""消费方授权领域服务。

集中实现数据服务的消费方授权规则：

1. 发布服务时绑定「应用 + 响应字段 + 缓存键范围」，未授权应用调用一律拒绝；
2. 同一输出数据集按应用隔离缓存键，不同消费方互不读取对方缓存；
3. 授权优先级：紧急撤权 > 显式授权 > 默认继承授权；
4. 权限变更进入待发布暂存，重新发布后才生效；紧急撤权为例外，立即生效；
5. 同一服务始终只有一个当前版本，重复发布只替换、不并列；
6. 历史调用记录保存调用当时的授权快照，事后变更不改写；
7. 授权变更同步更新缓存管理模块的规则清单，命中范围与服务权限一致。
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from app.store import store

# 授权类型
GRANT_EXPLICIT = "显式授权"
GRANT_INHERITED = "默认继承"
GRANT_REVOKED = "紧急撤权"
GRANT_NONE = "未授权"

# 授权状态
GRANT_STATUS_ACTIVE = "生效中"
GRANT_STATUS_PENDING = "待发布"
GRANT_STATUS_REVOKED = "已撤权"

# 优先级：数字越大越优先
GRANT_PRIORITY = {
    GRANT_REVOKED: 3,
    GRANT_EXPLICIT: 2,
    GRANT_INHERITED: 1,
}

CACHE_VALID = "有效"
CACHE_INVALID = "已失效"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _split_fields(raw: str | None) -> list[str]:
    """把逗号/中文逗号分隔的字段串拆成去重后的有序列表。"""
    if not raw:
        return []
    text = str(raw).replace("，", ",")
    seen: list[str] = []
    for part in text.split(","):
        name = part.strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def _join_fields(fields: list[str]) -> str:
    return ",".join(fields)


class AuthorizationService:
    # ------------------------------------------------------------------
    # 基础查询
    # ------------------------------------------------------------------
    def list_apps(self) -> list[dict[str, Any]]:
        return store.rows("consumer_app")

    def list_grants(self, service_code: str | None = None) -> list[dict[str, Any]]:
        rows = store.rows("consumer_grant")
        if service_code:
            rows = [row for row in rows if row.get("服务编号") == service_code]
        return rows

    def list_versions(self, service_code: str | None = None) -> list[dict[str, Any]]:
        rows = store.rows("service_version")
        if service_code:
            rows = [row for row in rows if row.get("服务编号") == service_code]
        return rows

    def list_cache_entries(self, service_code: str | None = None,
                           app_code: str | None = None) -> list[dict[str, Any]]:
        rows = store.rows("cache_entry")
        if service_code:
            rows = [row for row in rows if row.get("服务编号") == service_code]
        if app_code:
            rows = [row for row in rows if row.get("应用编号") == app_code]
        return rows

    def list_call_logs(self, service_code: str | None = None,
                       app_code: str | None = None) -> list[dict[str, Any]]:
        rows = store.rows("service_call_log")
        if service_code:
            rows = [row for row in rows if row.get("服务编号") == service_code]
        if app_code:
            rows = [row for row in rows if row.get("应用编号") == app_code]
        return rows

    def find_service(self, service_code: str) -> dict[str, Any] | None:
        for row in store.rows("service"):
            if row.get("服务编号") == service_code:
                return row
        return None

    def find_app(self, app_code: str) -> dict[str, Any] | None:
        for row in store.rows("consumer_app"):
            if row.get("应用编号") == app_code:
                return row
        return None

    def _find_grant(self, service_code: str, app_code: str) -> dict[str, Any] | None:
        for row in store.rows("consumer_grant"):
            if row.get("服务编号") == service_code and row.get("应用编号") == app_code:
                return row
        return None

    def current_version(self, service_code: str) -> dict[str, Any] | None:
        for row in store.rows("service_version"):
            if row.get("服务编号") == service_code and row.get("是否当前版本"):
                return row
        return None

    # ------------------------------------------------------------------
    # 授权解析：紧急撤权 > 显式授权 > 默认继承
    # ------------------------------------------------------------------
    def resolve_grant(self, service_code: str, app_code: str) -> dict[str, Any]:
        """返回某应用对某服务当前实际生效的授权。

        返回字段：authorized、grant_type、fields、cache_scope、reason。
        紧急撤权即使存在显式/继承授权也一律拒绝，体现撤权优先。
        """
        grant = self._find_grant(service_code, app_code)
        if grant is None:
            return {
                "authorized": False,
                "grant_type": GRANT_NONE,
                "fields": [],
                "cache_scope": "",
                "reason": "应用未授权",
            }

        grant_type = grant["授权类型"]
        if grant_type == GRANT_REVOKED:
            return {
                "authorized": False,
                "grant_type": GRANT_REVOKED,
                "fields": [],
                "cache_scope": "",
                "reason": f"授权已被紧急撤权（{grant.get('撤权时间') or ''}）",
            }

        # 待发布暂存不影响线上鉴权：
        # - 全新登记（生效字段为空）：发布前按未授权拒绝；
        # - 生效授权的调整（生效字段仍在）：继续按旧字段放行，发布后才切换。
        if grant.get("状态") == GRANT_STATUS_PENDING and not grant.get("响应字段"):
            return {
                "authorized": False,
                "grant_type": GRANT_NONE,
                "fields": [],
                "cache_scope": "",
                "reason": "授权待重新发布后生效",
            }

        return {
            "authorized": True,
            "grant_type": grant_type,
            "fields": _split_fields(grant["响应字段"]),
            "cache_scope": grant["缓存范围"],
            "reason": "授权生效中",
        }

    @staticmethod
    def _default_cache_scope(service: dict[str, Any], app_code: str) -> str:
        return f"{service.get('输出数据集', '')}:{app_code}"

    # ------------------------------------------------------------------
    # 显式授权 / 默认继承登记（先暂存，重新发布后生效）
    # ------------------------------------------------------------------
    def upsert_grant(self, service_code: str, app_code: str, fields_raw: str,
                     cache_scope: str | None, grant_type: str) -> tuple[dict[str, Any] | None, str]:
        service = self.find_service(service_code)
        if service is None:
            return None, f"数据服务 {service_code} 不存在"
        if self.find_app(app_code) is None:
            return None, f"消费应用 {app_code} 未登记"
        fields = _split_fields(fields_raw)
        if not fields:
            return None, "响应字段不能为空"
        if grant_type not in (GRANT_EXPLICIT, GRANT_INHERITED):
            return None, f"授权类型「{grant_type}」不支持，仅支持显式授权/默认继承"

        # 字段不能超出服务本身声明的响应字段范围。
        service_fields = set(_split_fields(service.get("响应字段")))
        overflow = [name for name in fields if service_fields and name not in service_fields]
        if overflow:
            return None, f"字段 {'、'.join(overflow)} 不在服务 {service_code} 的响应字段范围内"

        scope = (cache_scope or "").strip() or self._default_cache_scope(service, app_code)
        rows = store.rows("consumer_grant")
        existing = self._find_grant(service_code, app_code)
        joined_fields = _join_fields(fields)

        if existing is None:
            # 全新授权：生效列留空，发布前调用按未授权处理。
            entry = {
                "id": store.next_id("consumer_grant"),
                "服务编号": service_code,
                "应用编号": app_code,
                "授权类型": grant_type,
                "响应字段": "",
                "缓存范围": "",
                "状态": GRANT_STATUS_PENDING,
                "版本号": 0,
                "来源版本号": self.current_version(service_code)["版本号"] if self.current_version(service_code) else 0,
                "待发布授权类型": grant_type,
                "待发布字段": joined_fields,
                "待发布缓存范围": scope,
                "撤权时间": None,
                "更新时间": _now(),
            }
            rows.append(entry)
            return entry, "授权已登记，待重新发布服务后生效"

        # 已存在记录只写暂存列，生效列（授权类型/响应字段/缓存范围）保持不动：
        # - 生效中的授权调整：线上仍按旧权限放行，发布后才切换；
        # - 撤权后重新登记：授权类型仍为紧急撤权，发布前一律拒绝，体现撤权优先。
        existing["待发布授权类型"] = grant_type
        existing["待发布字段"] = joined_fields
        existing["待发布缓存范围"] = scope
        existing["更新时间"] = _now()
        if existing["授权类型"] == GRANT_REVOKED:
            return existing, "撤权后的恢复授权已暂存，待重新发布服务后生效；发布前撤权仍然有效"
        return existing, "授权变更已暂存，待重新发布服务后生效；发布前仍按当前权限鉴权"

    # ------------------------------------------------------------------
    # 紧急撤权：立即生效，压过默认继承；只失效该应用自己的缓存
    # ------------------------------------------------------------------
    def emergency_revoke(self, service_code: str, app_code: str,
                         reason: str | None = None) -> tuple[dict[str, Any] | None, str]:
        grant = self._find_grant(service_code, app_code)
        if grant is None:
            return None, f"应用 {app_code} 对服务 {service_code} 不存在授权关系，无法撤权"
        if grant["授权类型"] == GRANT_REVOKED:
            return grant, "该授权已是紧急撤权状态，无需重复撤权"

        grant["授权类型"] = GRANT_REVOKED
        grant["状态"] = GRANT_STATUS_REVOKED
        grant["撤权时间"] = _now()
        grant["更新时间"] = _now()
        # 暂存调整一并作废，避免恢复时携带未发布内容。
        grant["待发布授权类型"] = None
        grant["待发布字段"] = None
        grant["待发布缓存范围"] = None

        invalidated = self._invalidate_cache(service_code=service_code, app_code=app_code)
        self._sync_cache_rules_for_service(service_code)
        self._append_log(
            service_code, app_code, query_params={},
            result=f"紧急撤权：{reason or '管理员手工撤权'}", cache_hit=False, row_count=0,
            grant_type=GRANT_REVOKED, fields="", cache_scope="",
        )
        return grant, f"已紧急撤权并失效 {invalidated} 条该应用缓存，其他应用不受影响"

    # ------------------------------------------------------------------
    # 发布 / 重新发布：唯一当前版本 + 授权快照 + 缓存规则同步
    # ------------------------------------------------------------------
    def publish_service(self, service_code: str, remark: str | None = None) -> tuple[dict[str, Any] | None, str]:
        service = self.find_service(service_code)
        if service is None:
            return None, f"数据服务 {service_code} 不存在"

        grants = [g for g in store.rows("consumer_grant") if g.get("服务编号") == service_code]
        effective = [g for g in grants if g["授权类型"] in (GRANT_EXPLICIT, GRANT_INHERITED)]
        if not effective:
            return None, "服务没有任何生效授权，拒绝发布；请先导入或登记消费方授权"

        versions = store.rows("service_version")
        previous = self.current_version(service_code)
        next_version_no = (int(previous["版本号"]) + 1) if previous else 1

        # 把待发布暂存落到生效列；仍处撤权且无恢复暂存的记录不进授权快照。
        snapshot: list[dict[str, Any]] = []
        for grant in grants:
            if grant.get("待发布字段"):
                # 撤权后重新登记的恢复授权也在发布这一刻才解除撤权。
                grant["授权类型"] = grant.get("待发布授权类型") or grant["授权类型"]
                grant["响应字段"] = grant["待发布字段"]
                grant["缓存范围"] = grant["待发布缓存范围"] or grant["缓存范围"]
                grant["待发布授权类型"] = None
                grant["待发布字段"] = None
                grant["待发布缓存范围"] = None
                grant["撤权时间"] = None
            if grant["授权类型"] == GRANT_REVOKED:
                grant["状态"] = GRANT_STATUS_REVOKED
                continue
            grant["状态"] = GRANT_STATUS_ACTIVE
            grant["版本号"] = next_version_no
            grant["来源版本号"] = next_version_no
            grant["更新时间"] = _now()
            snapshot.append({
                "应用编号": grant["应用编号"],
                "授权类型": grant["授权类型"],
                "响应字段": grant["响应字段"],
                "缓存范围": grant["缓存范围"],
            })

        # 唯一当前版本：旧版本全部转为历史版本，不产生并列有效版本。
        for version in versions:
            if version.get("服务编号") == service_code:
                version["是否当前版本"] = False

        new_version = {
            "id": store.next_id("service_version"),
            "服务编号": service_code,
            "版本号": next_version_no,
            "是否当前版本": True,
            "状态": "已发布",
            "授权快照": snapshot,
            "发布时间": _now(),
            "备注": remark or ("初始发布" if previous is None else "权限变更后重新发布"),
        }
        versions.append(new_version)

        # 服务主表状态同步为已发布。
        service["status"] = "已发布"
        service["pending"] = False
        service["abnormal"] = False

        # 重新发布使旧版本缓存整体过期；按应用隔离的条目会在下次调用时重建。
        self._invalidate_cache(service_code=service_code)
        self._sync_cache_rules_for_service(service_code)

        return new_version, (
            f"服务 {service_code} 已发布版本 v{next_version_no}，"
            f"绑定 {len(snapshot)} 个消费应用；历史版本已归档，当前仅一个有效版本"
        )

    # ------------------------------------------------------------------
    # 服务调用：鉴权 + 字段过滤 + 按应用隔离的缓存键
    # ------------------------------------------------------------------
    def call_service(self, service_code: str, app_code: str,
                     query_params: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """执行一次消费方调用。返回 (响应体, HTTP 状态码)。"""
        service = self.find_service(service_code)
        if service is None:
            return {"ok": False, "message": f"数据服务 {service_code} 不存在"}, 404

        resolved = self.resolve_grant(service_code, app_code)
        param_text = self._param_text(query_params)

        if not resolved["authorized"]:
            # 拒绝调用同样留痕，记录调用时的授权关系。
            self._append_log(
                service_code, app_code, query_params=query_params,
                result=f"拒绝：{resolved['reason']}", cache_hit=False, row_count=0,
                grant_type=resolved["grant_type"], fields="",
                cache_scope=resolved["cache_scope"],
            )
            return {
                "ok": False,
                "message": f"应用 {app_code} 无权调用服务 {service_code}：{resolved['reason']}",
                "grant_type": resolved["grant_type"],
            }, 403

        version = self.current_version(service_code)
        version_no = int(version["版本号"]) if version else 0
        fields = resolved["fields"]
        cache_scope = resolved["cache_scope"]
        cache_key = self.build_cache_key(service, app_code, fields, param_text, version_no)

        # 只在本应用自己的缓存键范围内命中，天然读不到其他应用的缓存。
        cached = self._find_valid_cache(cache_key)
        if cached is not None:
            cached["命中次数"] = int(cached.get("命中次数", 0)) + 1
            self._append_log(
                service_code, app_code, query_params=query_params,
                result="成功", cache_hit=True, row_count=len(cached.get("数据", [])),
                grant_type=resolved["grant_type"], fields=_join_fields(fields),
                cache_scope=cache_scope, version_no=version_no,
            )
            return {
                "ok": True,
                "message": "缓存命中",
                "cache_hit": True,
                "cache_key": cache_key,
                "grant_type": resolved["grant_type"],
                "服务版本号": version_no,
                "data": cached.get("数据", []),
            }, 200

        # 未命中：模拟取数并只返回授权字段。
        payload = self._mock_dataset(service, fields, query_params)
        entry = {
            "id": store.next_id("cache_entry"),
            "缓存键": cache_key,
            "服务编号": service_code,
            "服务版本号": version_no,
            "应用编号": app_code,
            "输出数据集": service.get("输出数据集"),
            "缓存范围": cache_scope,
            "字段范围": _join_fields(fields),
            "查询参数": param_text,
            "状态": CACHE_VALID,
            "命中次数": 0,
            "数据": payload,
            "写入时间": _now(),
            "失效时间": None,
        }
        store.rows("cache_entry").append(entry)
        self._append_log(
            service_code, app_code, query_params=query_params,
            result="成功", cache_hit=False, row_count=len(payload),
            grant_type=resolved["grant_type"], fields=_join_fields(fields),
            cache_scope=cache_scope, version_no=version_no,
        )
        return {
            "ok": True,
            "message": "已执行查询并写入应用专属缓存",
            "cache_hit": False,
            "cache_key": cache_key,
            "grant_type": resolved["grant_type"],
            "服务版本号": version_no,
            "data": payload,
        }, 200

    def build_cache_key(self, service: dict[str, Any], app_code: str,
                        fields: list[str], param_text: str, version_no: int) -> str:
        """缓存键包含服务、应用、数据集、授权字段范围、版本与参数。

        应用编号与字段范围都参与键计算：同一数据集的不同应用、不同字段权限
        必然得到不同的键，从结构上杜绝跨消费方读缓存。
        """
        dataset = service.get("输出数据集", "")
        raw = "|".join([
            str(service.get("服务编号", "")),
            app_code,
            str(dataset),
            _join_fields(fields),
            str(version_no),
            param_text,
        ])
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
        return f"{service.get('服务编号')}|{app_code}|{dataset}|{_join_fields(fields)}|v{version_no}|{param_text}|{digest}"

    # ------------------------------------------------------------------
    # 授权清单导入 + 差异文件
    # ------------------------------------------------------------------
    def import_grants(self, service_code: str,
                      rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str]:
        """导入消费方授权清单，返回汇总与差异文件内容。

        差异分三类：新增（库中没有）、变更（字段/缓存范围/类型不同）、一致。
        导入只写待发布暂存，发布后字段权限才与新版本一致。
        """
        service = self.find_service(service_code)
        if service is None:
            return None, [], f"数据服务 {service_code} 不存在"
        if not rows:
            return None, [], "授权清单为空，未导入任何记录"

        diff_rows: list[dict[str, Any]] = []
        added = changed = unchanged = invalid = 0
        for raw in rows:
            app_code = str(raw.get("应用编号") or "").strip()
            fields_raw = str(raw.get("响应字段") or "").strip()
            scope = raw.get("缓存范围")
            grant_type = str(raw.get("授权类型") or GRANT_EXPLICIT).strip()

            if not app_code or not fields_raw:
                invalid += 1
                diff_rows.append({
                    "应用编号": app_code, "响应字段": fields_raw,
                    "缓存范围": scope or "", "授权类型": grant_type,
                    "差异类型": "无效行", "库中原值": "", "导入后值": "",
                })
                continue

            existing = self._find_grant(service_code, app_code)
            target_scope = (scope or "").strip() or self._default_cache_scope(service, app_code)
            imported_value = f"{grant_type}|{_join_fields(_split_fields(fields_raw))}|{target_scope}"

            if existing is None:
                diff_type = "新增"
                old_value = ""
                added += 1
            else:
                old_value = "|".join([
                    existing["授权类型"], existing["响应字段"], existing["缓存范围"],
                ])
                diff_type = "变更" if old_value != imported_value else "一致"
                if diff_type == "变更":
                    changed += 1
                else:
                    unchanged += 1

            entry, message = self.upsert_grant(
                service_code, app_code, fields_raw, target_scope, grant_type,
            )
            diff_rows.append({
                "应用编号": app_code,
                "响应字段": _join_fields(_split_fields(fields_raw)),
                "缓存范围": target_scope,
                "授权类型": grant_type,
                "差异类型": diff_type if entry else f"导入失败：{message}",
                "库中原值": old_value,
                "导入后值": imported_value,
            })

        summary = {
            "服务编号": service_code,
            "服务版本号": self.current_version(service_code)["版本号"]
            if self.current_version(service_code) else 0,
            "导入总数": len(rows),
            "新增": added,
            "变更": changed,
            "一致": unchanged,
            "无效行": invalid,
            "差异文件": diff_rows,
            "提示": "导入内容已进入待发布暂存；重新发布后差异文件中的字段权限与服务新版本保持一致",
        }
        return summary, diff_rows, "导入完成，差异文件已生成"

    # ------------------------------------------------------------------
    # 缓存管理模块同步：命中范围与服务权限一致
    # ------------------------------------------------------------------
    def _sync_cache_rules_for_service(self, service_code: str) -> int:
        """按当前授权关系同步缓存管理（cache 模块）规则清单。

        每个「服务 + 应用」对应一条规则，缓存目标即授权缓存范围；
        撤权应用的规则停用，生效授权的规则启用，保证命中范围不越权。
        """
        service = self.find_service(service_code)
        cache_rows = store.rows("cache")
        grants = [g for g in store.rows("consumer_grant") if g.get("服务编号") == service_code]
        ttl = str(service.get("缓存秒数") or "300") if service else "300"

        def rule_code(app_code: str) -> str:
            return f"CACH-AUTH-{service_code}-{app_code}"

        existing = {row.get("规则编号"): row for row in cache_rows}
        for grant in grants:
            code = rule_code(grant["应用编号"])
            revoked = grant["授权类型"] == GRANT_REVOKED
            payload = {
                "规则编号": code,
                "缓存目标": grant["缓存范围"],
                "缓存时间": ttl,
                "失效条件": "紧急撤权或重新发布时立即失效" if revoked else "服务重新发布或授权撤权时失效",
                "预加载设置": "关闭",
                "内存上限": "256MB",
                "淘汰策略": "LRU",
                "是否启用": "否" if revoked else "是",
            }
            if code in existing:
                existing[code].update(payload)
                existing[code]["status"] = "已停用" if revoked else "已启用"
                existing[code]["abnormal"] = revoked
            else:
                cache_rows.append({
                    "id": store.next_id("cache"),
                    "status": "已停用" if revoked else "已启用",
                    "pending": False,
                    "abnormal": revoked,
                    **payload,
                })
        return len(grants)

    def sync_all_cache_rules(self) -> int:
        """全量同步：供缓存管理页面或初始化时调用。"""
        count = 0
        for service_code in {row.get("服务编号") for row in store.rows("consumer_grant")}:
            count += self._sync_cache_rules_for_service(service_code)
        return count

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _invalidate_cache(self, *, service_code: str, app_code: str | None = None) -> int:
        count = 0
        for entry in store.rows("cache_entry"):
            if entry.get("服务编号") != service_code:
                continue
            if app_code and entry.get("应用编号") != app_code:
                continue
            if entry.get("状态") == CACHE_VALID:
                entry["状态"] = CACHE_INVALID
                entry["失效时间"] = _now()
                count += 1
        return count

    def _find_valid_cache(self, cache_key: str) -> dict[str, Any] | None:
        for entry in store.rows("cache_entry"):
            if entry.get("缓存键") == cache_key and entry.get("状态") == CACHE_VALID:
                return entry
        return None

    @staticmethod
    def _param_text(query_params: dict[str, Any]) -> str:
        if not query_params:
            return ""
        return "&".join(f"{key}={query_params[key]}" for key in sorted(query_params))

    def _mock_dataset(self, service: dict[str, Any], fields: list[str],
                      query_params: dict[str, Any]) -> list[dict[str, Any]]:
        """模拟数据集取数：构造两行样例，再按授权字段裁剪。"""
        dataset = service.get("输出数据集", "DATASET")
        full_row = {
            "region": query_params.get("region", "east"),
            "amount": 128000,
            "orders": 320,
            "customers": 210,
            "channel": "online",
            "customer_id": "C-1001",
            "level": "VIP",
            "tags": "高价值,活跃",
        }
        rows = []
        for idx in range(2):
            row = {"row_id": f"{dataset}-{idx + 1}"}
            for name in fields:
                row[name] = full_row.get(name)
            rows.append(row)
        return rows

    def _append_log(self, service_code: str, app_code: str, *,
                    query_params: dict[str, Any], result: str, cache_hit: bool,
                    row_count: int, grant_type: str, fields: str, cache_scope: str,
                    version_no: int | None = None) -> None:
        logs = store.rows("service_call_log")
        if version_no is None:
            version = self.current_version(service_code)
            version_no = int(version["版本号"]) if version else 0
        next_seq = store.next_id("service_call_log")
        logs.append({
            "id": next_seq,
            "记录编号": f"CALL-{next_seq:04d}",
            "服务编号": service_code,
            "服务版本号": version_no,
            "应用编号": app_code,
            # 授权快照：保存调用当时的应用授权关系，事后撤权/重发布不改写。
            "授权类型": grant_type,
            "授权字段": fields,
            "缓存范围": cache_scope,
            "查询参数": self._param_text(query_params),
            "调用结果": result,
            "缓存命中": cache_hit,
            "返回行数": row_count,
            "调用时间": _now(),
        })


# 单例：路由层共享同一份运行时状态。
authorization_service = AuthorizationService()
