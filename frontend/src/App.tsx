import { useState } from 'react'
import { Link, Route, Routes } from 'react-router-dom'

import Overview from './views/Overview'
import IndicatorView from './views/indicator'
import DatasourceView from './views/datasource'
import QueryView from './views/query'
import ExperimentView from './views/experiment'
import DatasetView from './views/dataset'
import ChartView from './views/chart'
import ReportView from './views/report'
import ServiceView from './views/service'
import ConsumerAuthView from './views/consumer-auth'
import DashboardView from './views/dashboard'
import DimensionView from './views/dimension'
import FilterView from './views/filter'
import ScheduleView from './views/schedule'
import ExportView from './views/export'
import CacheView from './views/cache'
import ModelView from './views/model'
import LogView from './views/log'

const navItems = [{ label: "运营概览", path: "/" }, { label: "指标口径管理", path: "/indicator" }, { label: "分析数据源", path: "/datasource" }, { label: "聚合查询配置", path: "/query" }, { label: "分析实验管理", path: "/experiment" }, { label: "分析数据集", path: "/dataset" }, { label: "可视化图表配置", path: "/chart" }, { label: "分析报告管理", path: "/report" }, { label: "数据服务发布", path: "/service" }, { label: "消费方授权", path: "/consumer-auth" }, { label: "数据看板", path: "/dashboard" }, { label: "分析维度管理", path: "/dimension" }, { label: "全局筛选器", path: "/filter" }, { label: "定时分析任务", path: "/schedule" }, { label: "数据导出配置", path: "/export" }, { label: "查询缓存管理", path: "/cache" }, { label: "分析模型管理", path: "/model" }, { label: "分析操作日志", path: "/log" }]

export default function App() {
  const [operator] = useState('值班管理员')

  return (
    <div className="app-shell">
      <aside className="app-side">
        <h1 className="app-title">数据分析工作台</h1>
        <nav className="nav-list">
          {navItems.map((item) => (
            <Link key={item.path} to={item.path} className="nav-item">
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="app-main">
        <header className="app-head">
          <span className="head-desc">面向企业数据分析师与数据产品经理的一站式数据分析工作台。提供指标口径管理、聚合查询、分析实验设计、数据服务发布与应用集成的完整链路。</span>
          <span className="head-user">当前值班：{operator}</span>
        </header>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/indicator" element={<IndicatorView />} />
          <Route path="/datasource" element={<DatasourceView />} />
          <Route path="/query" element={<QueryView />} />
          <Route path="/experiment" element={<ExperimentView />} />
          <Route path="/dataset" element={<DatasetView />} />
          <Route path="/chart" element={<ChartView />} />
          <Route path="/report" element={<ReportView />} />
          <Route path="/service" element={<ServiceView />} />
          <Route path="/consumer-auth" element={<ConsumerAuthView />} />
          <Route path="/dashboard" element={<DashboardView />} />
          <Route path="/dimension" element={<DimensionView />} />
          <Route path="/filter" element={<FilterView />} />
          <Route path="/schedule" element={<ScheduleView />} />
          <Route path="/export" element={<ExportView />} />
          <Route path="/cache" element={<CacheView />} />
          <Route path="/model" element={<ModelView />} />
          <Route path="/log" element={<LogView />} />
        </Routes>
      </main>
    </div>
  )
}
