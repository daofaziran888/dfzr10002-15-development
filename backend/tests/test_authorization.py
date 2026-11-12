"""消费方授权领域规则测试：只依赖标准库，直接验证服务层与内存仓库。

运行：cd backend && .venv/bin/python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest

from app.services.authorization import (
    GRANT_INHERITED,
    GRANT_REVOKED,
    AuthorizationService,
)
from app.store import store


class AuthorizationRuleTest(unittest.TestCase):
    def setUp(self) -> None:
        store.reset()
        self.svc = AuthorizationService()
        self.service = "SVC-0001"

    # 1. 未授权应用调用被拒绝
    def test_unauthorized_app_rejected(self) -> None:
        body, status = self.svc.call_service(self.service, "APP-0003", {"region": "east"})
        self.assertEqual(403, status)
        self.assertFalse(body["ok"])

    # 2. 字段级权限 + 不同应用缓存键隔离
    def test_field_scope_and_cache_isolation(self) -> None:
        body_a, status_a = self.svc.call_service(self.service, "APP-0001", {"region": "east"})
        body_b, status_b = self.svc.call_service(self.service, "APP-0002", {"region": "east"})
        self.assertEqual(200, status_a)
        self.assertEqual(200, status_b)
        self.assertEqual(set(body_a["data"][0]), {"row_id", "region", "amount"})
        self.assertEqual(
            set(body_b["data"][0]),
            {"row_id", "region", "amount", "orders", "customers", "channel"},
        )
        self.assertNotEqual(body_a["cache_key"], body_b["cache_key"])
        # 各自只命中自己的缓存
        again_a, _ = self.svc.call_service(self.service, "APP-0001", {"region": "east"})
        self.assertTrue(again_a["cache_hit"])

    # 3. 紧急撤权：只失效本应用缓存，其他应用不受影响，且压过默认继承
    def test_emergency_revoke_scopes_to_app(self) -> None:
        self.svc.call_service(self.service, "APP-0001", {})
        self.svc.call_service(self.service, "APP-0002", {})
        _, message = self.svc.emergency_revoke(self.service, "APP-0001", "演练")
        self.assertIn("该应用缓存", message)

        a_entries = self.svc.list_cache_entries(self.service, "APP-0001")
        b_entries = self.svc.list_cache_entries(self.service, "APP-0002")
        self.assertTrue(all(e["状态"] == "已失效" for e in a_entries))
        self.assertTrue(all(e["状态"] == "有效" for e in b_entries))

        _, status = self.svc.call_service(self.service, "APP-0001", {})
        self.assertEqual(403, status)
        body_b, status_b = self.svc.call_service(self.service, "APP-0002", {})
        self.assertEqual(200, status_b)
        self.assertTrue(body_b["ok"])

        # 撤权后登记默认继承，发布前撤权仍然优先
        self.svc.upsert_grant(self.service, "APP-0001", "region,amount", None, GRANT_INHERITED)
        resolved = self.svc.resolve_grant(self.service, "APP-0001")
        self.assertEqual(GRANT_REVOKED, resolved["grant_type"])
        self.assertFalse(resolved["authorized"])

    # 4. 重新发布只保留一个当前版本，历史版本归档
    def test_republish_keeps_single_current_version(self) -> None:
        version, _ = self.svc.publish_service(self.service, "再次发布")
        self.assertEqual(2, version["版本号"])
        versions = self.svc.list_versions(self.service)
        current = [v for v in versions if v["是否当前版本"]]
        self.assertEqual(1, len(current))
        self.assertEqual(2, current[0]["版本号"])
        # 连续第三次发布仍只有一个当前版本
        self.svc.publish_service(self.service)
        current = [v for v in self.svc.list_versions(self.service) if v["是否当前版本"]]
        self.assertEqual(1, len(current))
        self.assertEqual(3, current[0]["版本号"])

    # 5. 权限变更发布前不影响线上；发布后生效
    def test_pending_changes_not_effective_until_publish(self) -> None:
        # 五列收敛为三列，未发布前仍按五列
        self.svc.upsert_grant(self.service, "APP-0002", "region,amount,orders", None, "显式授权")
        body, status = self.svc.call_service(self.service, "APP-0002", {})
        self.assertEqual(200, status)
        self.assertIn("channel", body["data"][0])
        # 全新授权发布前无权
        self.svc.upsert_grant(self.service, "APP-0003", "region,channel", None, "显式授权")
        _, status = self.svc.call_service(self.service, "APP-0003", {})
        self.assertEqual(403, status)

        self.svc.publish_service(self.service)
        body, status = self.svc.call_service(self.service, "APP-0002", {})
        self.assertEqual(200, status)
        self.assertEqual(set(body["data"][0]), {"row_id", "region", "amount", "orders"})
        body, status = self.svc.call_service(self.service, "APP-0003", {})
        self.assertEqual(200, status)
        self.assertTrue(body["ok"])

    # 6. 历史调用记录保留调用当时的授权快照
    def test_call_logs_keep_authorization_snapshot(self) -> None:
        self.svc.call_service(self.service, "APP-0001", {"region": "east"})
        self.svc.emergency_revoke(self.service, "APP-0001")
        logs = self.svc.list_call_logs(self.service, "APP-0001")
        success = [r for r in logs if r["调用结果"] == "成功"]
        self.assertTrue(any(
            r["授权类型"] == "显式授权" and r["授权字段"] == "region,amount"
            and r["服务版本号"] == 1
            for r in success
        ))
        self.assertTrue(any("撤权" in r["调用结果"] for r in logs))

    # 7. 导入差异分类正确，差异文件行与待发布权限一致
    def test_import_diff_classification(self) -> None:
        summary, diff_rows, _ = self.svc.import_grants(self.service, [
            {"应用编号": "APP-0001", "响应字段": "region,amount", "缓存范围": "DS-SALES:APP-0001", "授权类型": "显式授权"},
            {"应用编号": "APP-0002", "响应字段": "region,amount,orders", "缓存范围": "DS-SALES:APP-0002", "授权类型": "显式授权"},
            {"应用编号": "APP-0003", "响应字段": "region,channel", "缓存范围": "DS-SALES:APP-0003", "授权类型": "显式授权"},
            {"应用编号": "", "响应字段": "", "缓存范围": "", "授权类型": "显式授权"},
        ])
        self.assertEqual(1, summary["新增"])
        self.assertEqual(1, summary["变更"])
        self.assertEqual(1, summary["一致"])
        self.assertEqual(1, summary["无效行"])
        diff_map = {row["应用编号"]: row["差异类型"] for row in diff_rows}
        self.assertEqual("新增", diff_map["APP-0003"])
        self.assertEqual("变更", diff_map["APP-0002"])

    # 8. 缓存管理模块规则随授权同步，撤权应用规则停用
    def test_cache_rules_synced_with_grants(self) -> None:
        self.svc.emergency_revoke(self.service, "APP-0001")
        rules = [r for r in store.rows("cache") if r.get("规则编号", "").startswith("CACH-AUTH-SVC-0001")]
        rule_map = {r["规则编号"]: r for r in rules}
        self.assertEqual("已停用", rule_map["CACH-AUTH-SVC-0001-APP-0001"]["status"])
        self.assertEqual("已启用", rule_map["CACH-AUTH-SVC-0001-APP-0002"]["status"])
        # 缓存目标与授权缓存范围一一对应
        self.assertEqual("DS-SALES:APP-0002", rule_map["CACH-AUTH-SVC-0001-APP-0002"]["缓存目标"])

    # 9. 无授权的服务禁止发布
    def test_publish_without_grant_rejected(self) -> None:
        # SERV-0001 是骨架演示服务，存在但没有任何消费方授权
        entry, message = self.svc.publish_service("SERV-0001")
        self.assertIsNone(entry)
        self.assertIn("没有任何生效授权", message)


if __name__ == "__main__":
    unittest.main()
