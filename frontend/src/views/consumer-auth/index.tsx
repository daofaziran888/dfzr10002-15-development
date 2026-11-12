import { useCallback, useEffect, useRef, useState } from 'react'

import { request } from '@/api/client'

const ENDPOINT = '/api/consumer-auth'

type Row = Record<string, string | number | null | boolean | string[] | Record<string, unknown>[]>
type TabKey = 'grants' | 'versions' | 'cache' | 'logs'

const tabs: { key: TabKey; label: string }[] = [
  { key: 'grants', label: '消费方授权' },
  { key: 'versions', label: '服务版本' },
  { key: 'cache', label: '应用缓存条目' },
  { key: 'logs', label: '调用记录' },
]

const grantColumns = [
  '服务编号', '应用编号', '授权类型', '响应字段', '缓存范围', '状态', '版本号',
  '待发布授权类型', '待发布字段', '更新时间',
]
const versionColumns = ['服务编号', '版本号', '是否当前版本', '状态', '发布时间', '备注']
const cacheColumns = ['缓存键', '应用编号', '输出数据集', '缓存范围', '字段范围', '状态', '命中次数', '写入时间']
const logColumns = ['记录编号', '服务编号', '服务版本号', '应用编号', '授权类型', '授权字段', '缓存范围', '调用结果', '缓存命中', '调用时间']

export default function ConsumerAuthView() {
  const [tab, setTab] = useState<TabKey>('grants')
  const [rows, setRows] = useState<Row[]>([])
  const [apps, setApps] = useState<Row[]>([])
  const [message, setMessage] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [serviceFilter, setServiceFilter] = useState('SVC-0001')
  const fileInput = useRef<HTMLInputElement>(null)

  // 授权登记表单
  const [form, setForm] = useState({
    服务编号: 'SVC-0001',
    应用编号: 'APP-0001',
    响应字段: 'region,amount',
    缓存范围: '',
    授权类型: '显式授权',
  })
  // 调用模拟器
  const [callForm, setCallForm] = useState({ 服务编号: 'SVC-0001', 应用编号: 'APP-0001' })
  const [callResult, setCallResult] = useState<Record<string, unknown> | null>(null)

  const reload = useCallback(async () => {
    setErrorMessage('')
    try {
      const path = {
        grants: `${ENDPOINT}/grants?service_code=${encodeURIComponent(serviceFilter)}`,
        versions: `${ENDPOINT}/versions?service_code=${encodeURIComponent(serviceFilter)}`,
        cache: `${ENDPOINT}/cache-entries?service_code=${encodeURIComponent(serviceFilter)}`,
        logs: `${ENDPOINT}/call-logs?service_code=${encodeURIComponent(serviceFilter)}`,
      }[tab]
      const response = await request(path)
      if (!response.ok) throw new Error('数据读取失败')
      const payload = await response.json()
      setRows(payload.items ?? [])
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '消费方授权数据读取失败')
    }
  }, [tab, serviceFilter])

  useEffect(() => {
    void reload()
  }, [reload])

  useEffect(() => {
    void (async () => {
      const response = await request(`${ENDPOINT}/apps`)
      if (response.ok) setApps((await response.json()).items ?? [])
    })()
  }, [])

  async function submitGrant() {
    setErrorMessage(''); setMessage('')
    const response = await request(`${ENDPOINT}/grants`, {
      method: 'POST',
      body: JSON.stringify(form),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      setErrorMessage(payload.message ?? '授权登记失败')
      return
    }
    setMessage(payload.message)
    setCallResult(null)
    await reload()
  }

  async function revoke(appCode: string) {
    setErrorMessage(''); setMessage('')
    const response = await request(`${ENDPOINT}/emergency-revoke`, {
      method: 'POST',
      body: JSON.stringify({ 服务编号: serviceFilter, 应用编号: appCode, 撤权原因: '页面紧急撤权' }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      setErrorMessage(payload.message ?? '紧急撤权失败')
      return
    }
    setMessage(payload.message)
    await reload()
  }

  async function publish() {
    setErrorMessage(''); setMessage('')
    const response = await request(`${ENDPOINT}/publish/${encodeURIComponent(serviceFilter)}`, {
      method: 'POST',
      body: JSON.stringify({ remark: '页面触发重新发布' }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      setErrorMessage(payload.message ?? '发布失败')
      return
    }
    setMessage(payload.message)
    await reload()
  }

  async function simulateCall() {
    setErrorMessage(''); setMessage('')
    const response = await request(`${ENDPOINT}/call`, {
      method: 'POST',
      body: JSON.stringify({ ...callForm, 查询参数: { region: 'east' } }),
    })
    const payload = await response.json()
    setCallResult({ httpStatus: response.status, ...payload })
    await reload()
  }

  async function handleImportFile(event: React.ChangeEvent<HTMLInputElement>) {
    setErrorMessage(''); setMessage('')
    const file = event.target.files?.[0]
    if (!file) return
    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      const payloadBody = {
        服务编号: serviceFilter,
        清单: Array.isArray(parsed) ? parsed : parsed.清单 ?? [],
      }
      const response = await request(`${ENDPOINT}/import`, {
        method: 'POST',
        body: JSON.stringify(payloadBody),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail ?? '导入失败')
      setMessage(`导入完成：新增 ${payload.新增} / 变更 ${payload.变更} / 一致 ${payload.一致} / 无效 ${payload.无效行}，可下载差异文件核对`)
      await reload()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '授权清单解析失败，请检查 JSON 格式')
    } finally {
      event.target.value = ''
    }
  }

  const columns = { grants: grantColumns, versions: versionColumns, cache: cacheColumns, logs: logColumns }[tab]

  return (
    <section className="page" data-module="consumer-auth">
      <header className="page-head">
        <div>
          <h2>消费方授权管理</h2>
          <p className="page-desc">
            发布服务时绑定消费应用、响应字段与缓存键范围；紧急撤权优先于默认继承，
            不同应用的缓存按键隔离，重新发布仅保留一个当前版本。
          </p>
        </div>
        <div className="page-actions">
          <button className="btn primary" type="button" onClick={() => fileInput.current?.click()}>
            上传授权清单
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="application/json,.json"
            style={{ display: 'none' }}
            onChange={(event) => void handleImportFile(event)}
          />
          <button
            className="btn"
            type="button"
            onClick={() => window.open(`${ENDPOINT}/import/diff-download?service_code=${encodeURIComponent(serviceFilter)}`, '_blank')}
          >
            下载差异文件
          </button>
          <button className="btn" type="button" onClick={() => void publish()}>重新发布服务</button>
        </div>
      </header>

      <form className="filter-bar" onSubmit={(event) => { event.preventDefault(); void reload() }}>
        <label className="filter-item">
          <span>服务编号</span>
          <input value={serviceFilter} onChange={(event) => setServiceFilter(event.target.value)} placeholder="如 SVC-0001" />
        </label>
        <button className="btn" type="submit">查询</button>
      </form>

      <div className="stat-row">
        <article className="stat-card">
          <span className="stat-label">授权记录数</span>
          <strong className="stat-value">{tab === 'grants' ? rows.length : '—'}</strong>
        </article>
        <article className="stat-card">
          <span className="stat-label">当前版本数（应恒为 1）</span>
          <strong className="stat-value">
            {tab === 'versions' ? rows.filter((r) => r['是否当前版本'] === true).length : '—'}
          </strong>
        </article>
        <article className="stat-card">
          <span className="stat-label">有效缓存条目</span>
          <strong className="stat-value">
            {tab === 'cache' ? rows.filter((r) => r['状态'] === '有效').length : '—'}
          </strong>
        </article>
      </div>

      <nav className="nav-list" style={{ display: 'flex', gap: 8, margin: '12px 0' }}>
        {tabs.map((item) => (
          <button
            key={item.key}
            className={`btn ${tab === item.key ? 'primary' : 'ghost'}`}
            type="button"
            onClick={() => setTab(item.key)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => <th key={column}>{column}</th>)}
            {tab === 'grants' && <th>操作</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row.id ?? Math.random())}>
              {columns.map((column) => {
                const value = row[column]
                return (
                  <td key={column}>
                    {typeof value === 'boolean' ? (value ? '是' : '否')
                      : Array.isArray(value) ? `${value.length} 项`
                      : (value === null || value === undefined || value === '' ? '—' : String(value))}
                  </td>
                )
              })}
              {tab === 'grants' && (
                <td className="row-actions">
                  <button
                    className="link"
                    type="button"
                    disabled={row['授权类型'] === '紧急撤权'}
                    onClick={() => void revoke(String(row['应用编号']))}
                  >
                    紧急撤权
                  </button>
                </td>
              )}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td className="empty-state" colSpan={columns.length + 1}>暂无数据</td>
            </tr>
          )}
        </tbody>
      </table>

      <div style={{ display: 'flex', gap: 16, marginTop: 20, flexWrap: 'wrap' }}>
        <article className="stat-card" style={{ flex: 1, minWidth: 320 }}>
          <span className="stat-label">登记 / 调整授权（发布后生效）</span>
          <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
            <input placeholder="服务编号" value={form.服务编号}
              onChange={(e) => setForm({ ...form, 服务编号: e.target.value })} />
            <select value={form.应用编号} onChange={(e) => setForm({ ...form, 应用编号: e.target.value })}>
              {apps.map((app) => <option key={String(app.id)} value={String(app['应用编号'])}>{String(app['应用编号'])} - {String(app['应用名称'])}</option>)}
            </select>
            <input placeholder="响应字段，逗号分隔" value={form.响应字段}
              onChange={(e) => setForm({ ...form, 响应字段: e.target.value })} />
            <input placeholder="缓存范围（留空默认 数据集:应用编号）" value={form.缓存范围}
              onChange={(e) => setForm({ ...form, 缓存范围: e.target.value })} />
            <select value={form.授权类型} onChange={(e) => setForm({ ...form, 授权类型: e.target.value })}>
              <option value="显式授权">显式授权</option>
              <option value="默认继承">默认继承</option>
            </select>
            <button className="btn primary" type="button" onClick={() => void submitGrant()}>提交授权变更</button>
          </div>
        </article>

        <article className="stat-card" style={{ flex: 1, minWidth: 320 }}>
          <span className="stat-label">消费调用模拟器（验证鉴权与缓存隔离）</span>
          <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
            <input placeholder="服务编号" value={callForm.服务编号}
              onChange={(e) => setCallForm({ ...callForm, 服务编号: e.target.value })} />
            <select value={callForm.应用编号} onChange={(e) => setCallForm({ ...callForm, 应用编号: e.target.value })}>
              {apps.map((app) => <option key={String(app.id)} value={String(app['应用编号'])}>{String(app['应用编号'])}</option>)}
            </select>
            <button className="btn primary" type="button" onClick={() => void simulateCall()}>发起调用</button>
            {callResult && (
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0 }}>
                {JSON.stringify(callResult, null, 2)}
              </pre>
            )}
          </div>
        </article>
      </div>

      <footer className="page-foot">
        <span>共 {rows.length} 条记录</span>
        {message && <span className="stat-label">{message}</span>}
        {errorMessage && <span className="error-text">{errorMessage}</span>}
      </footer>
    </section>
  )
}
