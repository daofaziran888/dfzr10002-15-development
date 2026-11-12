"""接口出入参模型：列表分页、动作结果与各模块的明细结构。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    """登记或修改一条业务记录时提交的字段集合。"""

    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None



class IndicatorEntry(BaseModel):
    """业务指标明细结构。"""

    field_0: str | None = None  # 指标编号
    field_1: str | None = None  # 指标名称
    field_2: str | None = None  # 计算公式
    field_3: str | None = None  # 统计粒度
    field_4: str | None = None  # 时间范围
    field_5: str | None = None  # 筛选条件
    field_6: str | None = None  # 数据来源
    field_7: str | None = None  # 口径版本

class DatasourceEntry(BaseModel):
    """数据源连接明细结构。"""

    field_0: str | None = None  # 连接编号
    field_1: str | None = None  # 连接名称
    field_2: str | None = None  # 数据库类型
    field_3: str | None = None  # 连接地址
    field_4: str | None = None  # 认证凭据
    field_5: str | None = None  # 默认库名
    field_6: str | None = None  # 连接池大小
    field_7: str | None = None  # 是否启用

class QueryEntry(BaseModel):
    """查询模板明细结构。"""

    field_0: str | None = None  # 模板编号
    field_1: str | None = None  # 模板名称
    field_2: str | None = None  # 查询语句
    field_3: str | None = None  # 参数定义
    field_4: str | None = None  # 缓存时间
    field_5: str | None = None  # 结果上限
    field_6: str | None = None  # 执行超时
    field_7: str | None = None  # 模板版本

class ExperimentEntry(BaseModel):
    """分析实验明细结构。"""

    field_0: str | None = None  # 实验编号
    field_1: str | None = None  # 实验名称
    field_2: str | None = None  # 分析数据集
    field_3: str | None = None  # 分组字段
    field_4: str | None = None  # 目标度量
    field_5: str | None = None  # 基准区间
    field_6: str | None = None  # 显著阈值
    field_7: str | None = None  # 实验状态

class DatasetEntry(BaseModel):
    """数据集明细结构。"""

    field_0: str | None = None  # 数据集编号
    field_1: str | None = None  # 数据集名称
    field_2: str | None = None  # 来源表名
    field_3: str | None = None  # 字段列表
    field_4: str | None = None  # 行数上限
    field_5: str | None = None  # 刷新频率
    field_6: str | None = None  # 最近刷新
    field_7: str | None = None  # 是否启用

class ChartEntry(BaseModel):
    """图表配置明细结构。"""

    field_0: str | None = None  # 图表编号
    field_1: str | None = None  # 图表名称
    field_2: str | None = None  # 图表类型
    field_3: str | None = None  # 数据源绑定
    field_4: str | None = None  # 横轴字段
    field_5: str | None = None  # 纵轴字段
    field_6: str | None = None  # 筛选条件
    field_7: str | None = None  # 刷新间隔

class ReportEntry(BaseModel):
    """分析报告明细结构。"""

    field_0: str | None = None  # 报告编号
    field_1: str | None = None  # 报告标题
    field_2: str | None = None  # 关联数据集
    field_3: str | None = None  # 分析周期
    field_4: str | None = None  # 报告模板
    field_5: str | None = None  # 生成时间
    field_6: str | None = None  # 生成人
    field_7: str | None = None  # 报告状态

class ServiceEntry(BaseModel):
    """数据服务明细结构。"""

    field_0: str | None = None  # 服务编号
    field_1: str | None = None  # 服务名称
    field_2: str | None = None  # 输出数据集
    field_3: str | None = None  # 查询参数
    field_4: str | None = None  # 响应字段
    field_5: str | None = None  # 缓存秒数
    field_6: str | None = None  # 分页上限
    field_7: str | None = None  # 消费应用

class DashboardEntry(BaseModel):
    """看板面板明细结构。"""

    field_0: str | None = None  # 面板编号
    field_1: str | None = None  # 面板名称
    field_2: str | None = None  # 布局配置
    field_3: str | None = None  # 图表集合
    field_4: str | None = None  # 刷新频率
    field_5: str | None = None  # 可见范围
    field_6: str | None = None  # 创建人
    field_7: str | None = None  # 是否展示

class DimensionEntry(BaseModel):
    """分析维度明细结构。"""

    field_0: str | None = None  # 维度编号
    field_1: str | None = None  # 维度名称
    field_2: str | None = None  # 维度表名
    field_3: str | None = None  # 维度字段
    field_4: str | None = None  # 层级关系
    field_5: str | None = None  # 筛选条件
    field_6: str | None = None  # 排序规则
    field_7: str | None = None  # 维度版本

class FilterEntry(BaseModel):
    """筛选器明细结构。"""

    field_0: str | None = None  # 筛选器编号
    field_1: str | None = None  # 筛选器名称
    field_2: str | None = None  # 关联字段
    field_3: str | None = None  # 筛选类型
    field_4: str | None = None  # 默认值
    field_5: str | None = None  # 可选值来源
    field_6: str | None = None  # 联动维度
    field_7: str | None = None  # 是否启用

class ScheduleEntry(BaseModel):
    """定时任务明细结构。"""

    field_0: str | None = None  # 任务编号
    field_1: str | None = None  # 任务名称
    field_2: str | None = None  # 分析类型
    field_3: str | None = None  # 调度表达式
    field_4: str | None = None  # 输入参数
    field_5: str | None = None  # 输出目标
    field_6: str | None = None  # 通知渠道
    field_7: str | None = None  # 是否启用

class ExportEntry(BaseModel):
    """导出模板明细结构。"""

    field_0: str | None = None  # 模板编号
    field_1: str | None = None  # 模板名称
    field_2: str | None = None  # 数据源绑定
    field_3: str | None = None  # 导出格式
    field_4: str | None = None  # 字段选择
    field_5: str | None = None  # 筛选参数
    field_6: str | None = None  # 导出上限
    field_7: str | None = None  # 是否启用

class CacheEntry(BaseModel):
    """缓存规则明细结构。"""

    field_0: str | None = None  # 规则编号
    field_1: str | None = None  # 缓存目标
    field_2: str | None = None  # 缓存时间
    field_3: str | None = None  # 失效条件
    field_4: str | None = None  # 预加载设置
    field_5: str | None = None  # 内存上限
    field_6: str | None = None  # 淘汰策略
    field_7: str | None = None  # 是否启用

class ModelEntry(BaseModel):
    """分析模型明细结构。"""

    field_0: str | None = None  # 模型编号
    field_1: str | None = None  # 模型名称
    field_2: str | None = None  # 模型类型
    field_3: str | None = None  # 输入字段
    field_4: str | None = None  # 参数配置
    field_5: str | None = None  # 训练数据集
    field_6: str | None = None  # 模型版本
    field_7: str | None = None  # 部署状态

class LogEntry(BaseModel):
    """操作日志明细结构。"""

    field_0: str | None = None  # 日志编号
    field_1: str | None = None  # 操作类型
    field_2: str | None = None  # 操作对象
    field_3: str | None = None  # 操作人
    field_4: str | None = None  # 操作时间
    field_5: str | None = None  # 查询耗时
    field_6: str | None = None  # 返回行数
    field_7: str | None = None  # 日志备注


class GrantUpsertPayload(BaseModel):
    """登记/调整单条消费方授权（显式授权或默认继承）。"""

    服务编号: str
    应用编号: str
    响应字段: str
    缓存范围: str | None = None
    授权类型: str = "显式授权"  # 显式授权 / 默认继承


class EmergencyRevokePayload(BaseModel):
    """紧急撤权：立即生效，优先级高于默认继承授权。"""

    服务编号: str
    应用编号: str
    撤权原因: str | None = None


class ServiceCallPayload(BaseModel):
    """消费应用调用数据服务。"""

    服务编号: str
    应用编号: str
    查询参数: dict[str, Any] = Field(default_factory=dict)


class GrantImportRow(BaseModel):
    """授权清单导入的单行：应用编号、响应字段、缓存范围。"""

    应用编号: str
    响应字段: str
    缓存范围: str | None = None
    授权类型: str = "显式授权"


class GrantImportPayload(BaseModel):
    """数据服务发布前上传的消费方授权清单。"""

    服务编号: str
    清单: list[GrantImportRow]
