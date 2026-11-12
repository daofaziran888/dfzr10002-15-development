"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import indicator as router_indicator
from app.routers import datasource as router_datasource
from app.routers import query as router_query
from app.routers import experiment as router_experiment
from app.routers import dataset as router_dataset
from app.routers import chart as router_chart
from app.routers import report as router_report
from app.routers import service as router_service
from app.routers import dashboard as router_dashboard
from app.routers import dimension as router_dimension
from app.routers import filter as router_filter
from app.routers import schedule as router_schedule
from app.routers import export as router_export
from app.routers import cache as router_cache
from app.routers import model as router_model
from app.routers import log as router_log
from app.routers import authorization as router_authorization

ROUTERS = [router_indicator, router_datasource, router_query, router_experiment, router_dataset, router_chart, router_report, router_service, router_dashboard, router_dimension, router_filter, router_schedule, router_export, router_cache, router_model, router_log, router_authorization]
