import { useEffect, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceArea, ReferenceLine
} from 'recharts'
import {
  GitCommit, Target, BrainCircuit, RefreshCw,
  ChevronRight, AlertTriangle, TrendingDown, Search,
  LayoutDashboard, Settings, Menu, X, Database
} from 'lucide-react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { auth } from '../firebase'
import '../index.css'

interface AnomalyWindow {
  start_time: string
  end_time: string
  severity: number
  direction: string
  metric_name: string
  aggregate_actual_mean: number
  aggregate_expected_mean: number
  aggregate_deviation_pct: number
  detection_method: string
}

interface LogDoc {
  id: string
  timestamp: string
  source: string
  text_content: string
  similarity_score: number
  matched_query: string
}

interface Hypothesis {
  rank: number
  cause_title: string
  evidence_strength: string
  status: string
  evidence_checks: { check_name: string; result: string; explanation: string; weight: number }[]
  reasoning: string
  supporting_evidence_ids: string[]
  recommended_action: string
}

interface AnomalyReport {
  anomaly_window: AnomalyWindow
  decomposition: {
    anomaly_window: AnomalyWindow
    primary_driver: {
      dimension: string
      segment_value: string
      baseline_mean: number
      anomaly_mean: number
      absolute_change: number
      segment_percent_change: number
      contribution_to_total: number
    }
    secondary_driver: any
    is_ambiguous: boolean
    drill_down_paths: string[][]
    all_segments: any[]
  }
  rag: {
    search_queries: string[]
    retrieved_logs: LogDoc[]
  }
  hypothesis: {
    hypotheses: Hypothesis[]
    served_from: string
    status: string
  }
  timeline?: any
  reconciliation?: any
  recovery_validation?: any
}

interface TraceData {
  timeseries: {
    data: { timestamp: string; actual: number; predicted_mean: number; upper_bound: number; lower_bound: number }[]
    anomalies: AnomalyWindow[]
  }
  reports: AnomalyReport[]
}

function getConfidenceClass(strength: string): string {
  if (strength === 'HIGH') return 'confidence-high'
  if (strength === 'MEDIUM') return 'confidence-med'
  return 'confidence-low'
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function formatDateTime(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export default function Dashboard() {
  const [trace, setTrace] = useState<TraceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [activeTab, setActiveTab] = useState('dashboard')
  const [costs, setCosts] = useState<any>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  
  // UI Features
  const [showEvents, setShowEvents] = useState(false)
  const systemEvents = [
    { date: '2025-05-15T00:00:00Z', label: 'Competitor Promo', color: 'var(--error)' },
    { date: '2025-06-12T09:00:00Z', label: 'iOS Deploy', color: 'var(--primary)' },
    { date: '2025-08-05T02:00:00Z', label: 'Stripe SDK Update', color: 'var(--warning)' },
  ]
  
  // Chat state
  const [chatOpen, setChatOpen] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState<{role: string, content: string}[]>([
    { role: 'assistant', content: 'Hi! I am the Trace.ai Data Assistant. Ask me anything about the recent anomalies.' }
  ])

  const [datasets, setDatasets] = useState<any[]>([]);
  const navigate = useNavigate();

  const fetchTrace = async () => {
    setLoading(true)
    setError(null)
    try {
      const token = await auth.currentUser?.getIdToken();
      
      // 1. Check if user has uploaded any datasets
      const dsRes = await fetch(`${API_BASE_URL}/api/v1/datasets/`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (dsRes.ok) {
        const ds = await dsRes.json();
        setDatasets(ds);
        if (ds.length === 0) {
          setLoading(false);
          return; // They have no datasets, UI will handle this
        }
      }

      // 2. Fetch the trace reports (In a real app, pass the dataset_id here)
      const res = await fetch(`${API_BASE_URL}/api/v1/trace_full`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Failed to fetch trace data')
      const data = await res.json()
      setTrace(data)
      setSelectedIdx(0)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const fetchCosts = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/costs`)
      const data = await res.json()
      setCosts(data)
    } catch (e) {
      console.error('Failed to fetch costs', e)
    }
  }

  const sendChatMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!chatInput.trim()) return
    
    const newMessages = [...chatMessages, { role: 'user', content: chatInput }]
    setChatMessages(newMessages)
    setChatInput('')

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: chatInput })
      })
      const data = await res.json()
      setChatMessages([...newMessages, { role: 'assistant', content: data.response }])
    } catch (err) {
      setChatMessages([...newMessages, { role: 'assistant', content: 'Failed to connect to AI server.' }])
    }
  }

  useEffect(() => { 
    fetchTrace()
    fetchCosts()
  }, [])

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner" />
        <h2 className="title-lg">Trace.ai Engine Running...</h2>
        <p className="text-muted body-md">Analyzing metrics and operational logs across 4 pipeline stages</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="app-layout" style={{ alignItems: 'center', justifyContent: 'center', width: '100%' }}>
        <div className="card" style={{ textAlign: 'center', padding: '48px', maxWidth: '400px' }}>
          <AlertTriangle size={48} color="var(--error)" style={{ margin: '0 auto' }} />
          <h2 className="title-lg mt-4">Connection Error</h2>
          <p className="text-muted body-md mt-4">{error}</p>
          <button className="btn mt-4" onClick={fetchTrace}>
            <RefreshCw size={16} /> Retry
          </button>
        </div>
      </div>
    )
  }

  if (datasets.length === 0) {
    return (
      <div className="app-layout" style={{ alignItems: 'center', justifyContent: 'center', width: '100%' }}>
        <div className="card" style={{ textAlign: 'center', padding: '48px', maxWidth: '400px' }}>
          <Database size={48} color="var(--primary)" style={{ margin: '0 auto' }} />
          <h2 className="title-lg mt-4">Welcome to Trace.ai</h2>
          <p className="text-muted body-md mt-4">You haven't uploaded any data yet. Upload your first CSV dataset to start monitoring for anomalies.</p>
          <button className="btn btn-primary mt-4" onClick={() => navigate('/upload')} style={{ margin: '16px auto 0' }}>
            Upload Dataset
          </button>
        </div>
      </div>
    )
  }

  if (!trace || !trace.reports || trace.reports.length === 0) {
    return (
      <div className="app-layout" style={{ alignItems: 'center', justifyContent: 'center', width: '100%' }}>
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <h2 className="title-lg">No anomalies detected</h2>
          <p className="text-muted body-md mt-4">The BSTS model found no significant deviations in the metric data.</p>
        </div>
      </div>
    )
  }

  const { timeseries, reports } = trace
  const report = reports[selectedIdx]
  const decomp = report.decomposition
  const primary = decomp.primary_driver
  const hyp = report.hypothesis.hypotheses[0]

  // Chart data
  const chartData = timeseries.data.map((d) => ({
    time: formatDate(d.timestamp),
    Actual: Math.round(d.actual),
    Expected: Math.round(d.predicted_mean),
  }))

  // Anomaly regions for the chart
  const anomalyRegions = timeseries.anomalies.map((a) => ({
    start: formatDate(a.start_time),
    end: formatDate(a.end_time),
    isSelected: a.start_time === report.anomaly_window.start_time
  }))

  return (
    <div className="app-layout">
      {/* 1. Slide-in Sidebar overlay & container */}
      {sidebarOpen && (
        <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />
      )}
      <nav className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="flex items-center gap-2">
            <div className="sidebar-logo">
              <BrainCircuit size={16} />
            </div>
            <div className="title-lg">Trace.ai</div>
          </div>
          <button className="btn-icon" onClick={() => setSidebarOpen(false)}>
            <X size={18} />
          </button>
        </div>
        <div className="flex flex-col gap-2">
          <button className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => { setActiveTab('dashboard'); setSidebarOpen(false); }} style={{ width: '100%', textAlign: 'left', background: activeTab === 'dashboard' ? 'var(--surface-container)' : 'transparent' }}>
            <LayoutDashboard size={16} /> Dashboard
          </button>
        </div>
        <div className="flex flex-col gap-2 mt-2">
          <button className="nav-item" onClick={() => navigate('/upload')} style={{ width: '100%', textAlign: 'left', background: 'transparent' }}>
            <Database size={16} /> Data Sources
          </button>
        </div>
        <div style={{ marginTop: 'auto' }}>
          <button className={`nav-item ${activeTab === 'costs' ? 'active' : ''}`} onClick={() => { setActiveTab('costs'); setSidebarOpen(false); }} style={{ width: '100%', textAlign: 'left', background: activeTab === 'costs' ? 'var(--surface-container)' : 'transparent' }}>
            <Settings size={16} /> Settings & Costs
          </button>
        </div>
      </nav>

      {/* Dashboard Content Area */}
      {activeTab === 'dashboard' ? (
      <div className="dashboard-content">
        
        {/* 2. Scrollable Anomaly Feed */}
        <div className="anomaly-feed">
          <div className="feed-header flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button className="btn-icon" onClick={() => setSidebarOpen(true)}>
                <Menu size={18} />
              </button>
              <h2 className="title-lg">Detected Issues</h2>
            </div>
            <button className="btn-icon" onClick={fetchTrace}>
              <RefreshCw size={14} />
            </button>
          </div>
          <div className="feed-list">
            {reports.map((r, idx) => {
              const aw = r.anomaly_window
              const topHyp = r.hypothesis.hypotheses[0]
              return (
                <div
                  key={idx}
                  className={`feed-item ${idx === selectedIdx ? 'active' : ''}`}
                  onClick={() => setSelectedIdx(idx)}
                >
                  <div className="flex justify-between items-center mb-2">
                    <span className="label-md text-muted">Incident #{idx + 1}</span>
                    <div className="flex items-center gap-2">
                      {topHyp && <span className={`badge ${getConfidenceClass(topHyp.evidence_strength)}`} style={{ fontSize: '9px', padding: '2px 4px' }}>{topHyp.evidence_strength}</span>}
                      <span className={`severity-dot ${aw.severity > 3 ? 'severity-high' : 'severity-medium'}`} />
                    </div>
                  </div>
                  <div className="body-md" style={{ fontWeight: 600, marginBottom: '6px' }}>
                    {topHyp?.cause_title || `${aw.metric_name} anomaly`}
                  </div>
                  <div className="label-md text-muted" style={{ textTransform: 'none' }}>
                    {formatDate(aw.start_time)} – {formatDate(aw.end_time)}<br/>
                    {Math.abs(aw.aggregate_deviation_pct).toFixed(1)}% drop · {aw.severity.toFixed(1)}σ
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* 3. Central Analysis Workspace */}
        <main className="main-workspace">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="headline-md">Analysis Workspace</h1>
              <p className="text-muted body-md mt-2">Investigating metric deviations and segment drivers</p>
              <p className="hero-tagline mt-2">"Don't just see what happened. Know why."</p>
            </div>
          </div>

          {/* Step 1: Time Series Chart */}
          <motion.section
            className="card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <div className="section-title">
              <span className="badge badge-step">Step 1</span>
              <span className="title-lg">Bayesian Anomaly Detection</span>
              
              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '16px' }}>
                <label className="flex items-center gap-2" style={{ cursor: 'pointer' }}>
                  <input 
                    type="checkbox" 
                    checked={showEvents} 
                    onChange={(e) => setShowEvents(e.target.checked)} 
                  />
                  <span className="label-md">Overlay System Events</span>
                </label>
                <span className="badge badge-critical">
                  <TrendingDown size={12} /> {Math.abs(report.anomaly_window.aggregate_deviation_pct).toFixed(1)}% DROP · {report.anomaly_window.severity.toFixed(1)}σ
                </span>
              </div>
            </div>

            <div style={{ height: '260px', marginTop: '16px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="2 2" stroke="var(--outline-variant)" vertical={false} />
                  <XAxis
                    dataKey="time"
                    stroke="var(--outline)"
                    tick={{ fill: 'var(--on-surface-variant)', fontSize: 11, fontFamily: 'var(--font-family)' }}
                    minTickGap={60}
                    axisLine={false}
                    tickLine={false}
                    dy={10}
                  />
                  <YAxis
                    stroke="var(--outline)"
                    tick={{ fill: 'var(--on-surface-variant)', fontSize: 11, fontFamily: 'var(--font-family)' }}
                    tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
                    domain={['auto', 'auto']}
                    axisLine={false}
                    tickLine={false}
                    dx={-10}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--surface-container-lowest)',
                      border: '1px solid var(--outline-variant)',
                      borderRadius: 'var(--radius-lg)',
                      fontSize: '12px',
                      fontFamily: 'var(--font-family)',
                      color: 'var(--on-surface)'
                    }}
                    itemStyle={{ color: 'var(--on-surface)' }}
                    formatter={(value: any) => [`$${value.toLocaleString()}`, undefined]}
                  />
                  {anomalyRegions.map((region, i) => (
                    <ReferenceArea
                      key={i}
                      x1={region.start}
                      x2={region.end}
                      fill={region.isSelected ? 'var(--error-container)' : 'var(--surface-container)'}
                      stroke="none"
                      className={region.isSelected ? "anomaly-zone" : ""}
                    />
                  ))}
                  {showEvents && systemEvents.map((evt: any, i: number) => (
                    <ReferenceLine 
                      key={`evt-${i}`} 
                      x={formatDate(evt.date)} 
                      stroke={evt.color} 
                      strokeDasharray="2 2"
                      label={{ position: 'insideTopLeft', value: evt.label, fill: evt.color, fontSize: 10, offset: 6 }} 
                    />
                  ))}
                  <Line type="stepAfter" dataKey="Actual" stroke="var(--error)" strokeWidth={1.5} dot={false} activeDot={{ r: 4, fill: 'var(--error)' }} animationDuration={1500} />
                  <Line type="stepAfter" dataKey="Expected" stroke="var(--outline)" strokeDasharray="3 3" strokeWidth={1.5} dot={false} animationDuration={1500} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </motion.section>

          {/* Step 2: Decomposition */}
          <motion.section
            className="card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
          >
            <div className="section-title">
              <span className="badge badge-step">Step 2</span>
              <span className="title-lg">Deterministic Decomposition</span>
            </div>

            <p className="text-muted body-md mb-6">
              Segment contribution analysis isolating the structural drop volume.
            </p>

            <div className="flex gap-6" style={{ flexWrap: 'wrap' }}>
              {/* Primary Driver */}
              <div style={{ flex: '1 1 260px' }}>
                <div className="flex justify-between items-center mb-2">
                  <span className="label-md text-muted">Primary Driver</span>
                  <span className="label-md">{(primary.contribution_to_total * 100).toFixed(0)}% contribution</span>
                </div>
                <div className="flex justify-between items-center mt-2">
                  <span className="body-md" style={{ fontWeight: 600 }}>
                    {primary.dimension} = {primary.segment_value}
                  </span>
                  <span className="body-md" style={{ color: 'var(--error)', fontWeight: 600 }}>
                    {primary.segment_percent_change.toFixed(1)}%
                  </span>
                </div>
                <div className="progress-bar-bg">
                  <div
                    className="progress-bar-fill progress-red"
                    style={{ width: `${primary.contribution_to_total * 100}%` }}
                  />
                </div>
              </div>

              {/* Secondary driver if ambiguous */}
              {decomp.is_ambiguous && decomp.secondary_driver && (
                <div style={{ flex: '1 1 260px' }}>
                  <div className="flex justify-between items-center mb-2">
                    <span className="label-md text-muted">Secondary Driver</span>
                    <span className="label-md">{(decomp.secondary_driver.contribution_to_total * 100).toFixed(0)}%</span>
                  </div>
                  <div className="body-md mt-2" style={{ fontWeight: 600 }}>
                    {decomp.secondary_driver.dimension} = {decomp.secondary_driver.segment_value}
                  </div>
                  <div className="progress-bar-bg">
                    <div
                      className="progress-bar-fill progress-blue"
                      style={{ width: `${decomp.secondary_driver.contribution_to_total * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Root Cause Contribution Tree */}
            <div className="drill-path" style={{ marginTop: '24px' }}>
              <span className="label-md text-muted mb-2" style={{ display: 'block' }}>Root Cause Contribution Tree</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px', background: 'var(--surface-container-lowest)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--outline-variant)' }}>
                <div style={{ padding: '6px 10px', background: 'var(--surface-container)', borderRadius: 'var(--radius-lg)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
                  {report.anomaly_window.metric_name} <span style={{ color: 'var(--error)' }}>-{Math.abs(report.anomaly_window.aggregate_deviation_pct).toFixed(1)}%</span>
                </div>
                <ChevronRight size={14} color="var(--outline)" />
                <div style={{ padding: '6px 10px', background: 'var(--surface-container)', borderRadius: 'var(--radius-lg)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
                  {primary.dimension} <span style={{ color: 'var(--error)' }}>-{primary.contribution_to_total > 0 ? (primary.contribution_to_total * 100).toFixed(0) : '0'}%</span>
                </div>
                <ChevronRight size={14} color="var(--outline)" />
                <div style={{ padding: '6px 10px', background: 'var(--error-container)', color: 'var(--on-error-container)', borderRadius: 'var(--radius-lg)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', border: '1px solid #fca5a5' }}>
                  {primary.segment_value} <span style={{ opacity: 0.8 }}>{primary.segment_percent_change.toFixed(1)}%</span>
                </div>
              </div>
            </div>

            {/* Reconciliation */}
            {report.reconciliation && (
              <div style={{ marginTop: '24px', padding: '12px', background: 'var(--surface-container-low)', borderRadius: 'var(--radius-md)', border: '1px solid var(--outline-variant)' }}>
                <div className="label-md text-muted mb-2">Reconciliation Summary</div>
                <div className="flex gap-4">
                  <div>
                    <span className="text-muted" style={{ fontSize: '11px', display: 'block' }}>Aggregate Delta</span>
                    <span className="body-md" style={{ fontWeight: 600 }}>{report.reconciliation.aggregate_delta?.toFixed(2) || '0.00'}</span>
                  </div>
                  <div>
                    <span className="text-muted" style={{ fontSize: '11px', display: 'block' }}>Explained Delta</span>
                    <span className="body-md" style={{ fontWeight: 600 }}>{report.reconciliation.explained_delta?.toFixed(2) || '0.00'}</span>
                  </div>
                  <div>
                    <span className="text-muted" style={{ fontSize: '11px', display: 'block' }}>Residual Delta</span>
                    <span className="body-md" style={{ fontWeight: 600 }}>{report.reconciliation.residual_delta?.toFixed(2) || '0.00'}</span>
                  </div>
                  <div>
                    <span className="text-muted" style={{ fontSize: '11px', display: 'block' }}>Explained Share</span>
                    <span className="body-md" style={{ fontWeight: 600 }}>{(report.reconciliation.explained_share * 100).toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            )}
          </motion.section>
        </main>

        {/* 4. Right-side Causal Intelligence Panel */}
        <motion.aside
          className="intelligence-panel"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          <div className="section-title">
            <span className="badge badge-step">Steps 3 & 4</span>
            <span className="title-lg">Causal Intelligence</span>
          </div>

          {/* Hypothesis */}
          {hyp && (
            <div className="hypothesis-box">
              {decomp.is_ambiguous && (
                <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px', padding: '12px', background: '#fffbeb', borderRadius: 'var(--radius-md)', color: '#92400e', border: '1px solid #fcd34d' }}>
                  <AlertTriangle size={18} />
                  <span className="label-md">AMBIGUOUS: Human review recommended.</span>
                </div>
              )}
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="badge" style={{ background: 'var(--primary)', color: 'var(--on-primary)', borderColor: 'var(--primary)' }}>
                        PRIMARY DIAGNOSIS
                      </span>
                      <span className={`badge ${getConfidenceClass(hyp.evidence_strength)}`}>
                        {hyp.evidence_strength} EVIDENCE
                      </span>
                    </div>
                    <div className="title-lg">{hyp.cause_title}</div>
                  </div>
                </div>
              
              <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '12px', padding: '12px', background: 'var(--error-container)', borderRadius: 'var(--radius-lg)', color: 'var(--on-error-container)', border: '1px solid #fca5a5' }}>
                <TrendingDown size={18} />
                <div style={{ flex: 1 }}>
                  <div className="label-md" style={{ opacity: 0.9 }}>Automated Impact Quantifier</div>
                  <div className="title-lg mt-1">
                    -${(Math.abs(report.anomaly_window.aggregate_deviation_pct) * 850).toLocaleString('en-US', {maximumFractionDigits: 0})} <span style={{ fontSize: '11px', fontWeight: 400 }}>/ hour</span>
                  </div>
                </div>
              </div>
              <p className="body-md text-muted" style={{ lineHeight: '1.5' }}>{hyp.reasoning}</p>

              {/* Evidence Checks Matrix */}
              {hyp.evidence_checks && hyp.evidence_checks.length > 0 && (
                <div className="mt-4 mb-4">
                  <div className="label-md text-muted mb-2">Evidence Checks</div>
                  <div className="flex flex-col gap-2">
                    {hyp.evidence_checks.map((check: any, i: number) => (
                      <div key={i} className="flex justify-between items-center" style={{ padding: '8px 12px', background: 'var(--surface-container)', borderRadius: 'var(--radius-md)', border: '1px solid var(--outline-variant)' }}>
                        <div className="flex flex-col">
                          <span className="body-md" style={{ fontWeight: 500, fontSize: '12px' }}>{check.check_name.replace(/_/g, ' ')}</span>
                          <span className="text-muted" style={{ fontSize: '10px' }}>{check.explanation}</span>
                        </div>
                        <span className={`badge ${check.result?.toUpperCase() === 'PASS' ? 'badge-success' : (check.result?.toUpperCase() === 'FAIL' ? 'badge-critical' : 'badge-warning')}`}>
                          {check.result?.toUpperCase()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommended Action */}
              {hyp.recommended_action && (
                <div className="action-box">
                  <Target size={16} color="var(--success)" style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <span className="label-md" style={{ color: 'var(--success)' }}>Recommended Action</span>
                    <p className="body-md mt-1">{hyp.recommended_action}</p>
                  </div>
                </div>
              )}

              {/* Recovery Validation */}
              {report.recovery_validation && (
                <div style={{ marginTop: '16px', padding: '12px', background: report.recovery_validation.metric_recovered ? '#f0fdf4' : '#fff1f2', borderRadius: 'var(--radius-md)', border: `1px solid ${report.recovery_validation.metric_recovered ? '#86efac' : '#fecdd3'}` }}>
                  <div className="flex items-center gap-2 mb-1">
                    <RefreshCw size={14} color={report.recovery_validation.metric_recovered ? 'var(--success)' : 'var(--error)'} />
                    <span className="label-md" style={{ color: report.recovery_validation.metric_recovered ? 'var(--success)' : 'var(--error)' }}>
                      {report.recovery_validation.metric_recovered ? 'RECOVERY DETECTED' : 'NO RECOVERY YET'}
                    </span>
                  </div>
                  <p className="body-md text-muted" style={{ fontSize: '11px' }}>{report.recovery_validation.recovery_summary || 'Monitoring post-incident trajectory.'}</p>
                </div>
              )}
            </div>
          )}

          {/* Timeline Sequence */}
          {report.timeline && report.timeline.length > 0 && (
            <div style={{ marginBottom: '24px' }}>
              <div className="label-md text-muted mb-2">Causal Sequence</div>
              <div className="flex flex-col gap-2 relative" style={{ paddingLeft: '8px' }}>
                <div style={{ position: 'absolute', left: '12px', top: '8px', bottom: '8px', width: '2px', background: 'var(--outline-variant)' }} />
                {report.timeline.map((evt: any, i: number) => (
                  <div key={i} className="flex gap-3 relative z-10">
                    <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: 'var(--primary)', border: '2px solid var(--surface-container-lowest)', marginTop: '4px' }} />
                    <div style={{ flex: 1 }}>
                      <div className="flex justify-between items-center">
                        <span className="body-md" style={{ fontWeight: 600, fontSize: '12px' }}>{evt.event_name}</span>
                        <span className="badge" style={{ fontSize: '9px' }}>{evt.role}</span>
                      </div>
                      <span className="text-muted" style={{ fontSize: '10px' }}>{formatDateTime(evt.timestamp)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Alternative Hypotheses */}
          {report.hypothesis.hypotheses.length > 1 && (
            <div style={{ marginBottom: '24px' }}>
              <div className="label-md text-muted mb-2">Alternative Hypotheses</div>
              <div className="flex flex-col gap-2">
                {report.hypothesis.hypotheses.slice(1).map((altHyp: any, i: number) => (
                  <div key={i} style={{ padding: '12px', background: 'var(--surface-container-low)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--outline-variant)' }}>
                    <div className="flex justify-between items-center mb-1">
                      <span className="title-md" style={{ fontSize: '13px', fontWeight: 600 }}>{altHyp.cause_title}</span>
                      <span className={`badge ${getConfidenceClass(altHyp.evidence_strength)}`}>{altHyp.evidence_strength}</span>
                    </div>
                    <p className="body-md text-muted" style={{ fontSize: '12px' }}>{altHyp.reasoning}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Evidence */}
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-3">
              <Search size={14} className="text-muted" />
              <span className="label-md text-muted">Supporting Evidence ({report.rag.retrieved_logs.length} logs)</span>
            </div>
            {report.rag.retrieved_logs.slice(0, 4).map((log) => (
              <div key={log.id} className="log-item">
                <div className="log-meta">
                  <span className="log-source" style={{ color: 'var(--primary)' }}>
                    <GitCommit size={10} /> {log.source}
                  </span>
                  <span className="text-muted" style={{ fontSize: '10px' }}>{formatDateTime(log.timestamp)}</span>
                </div>
                <div>{log.text_content}</div>
              </div>
            ))}
          </div>
        </motion.aside>

      </div>
      ) : (
      <div className="dashboard-content flex flex-col gap-6" style={{ padding: '32px', maxWidth: '800px', margin: '0 auto', width: '100%' }}>
        <div className="flex items-center gap-4">
          <button className="btn-icon" onClick={() => setSidebarOpen(true)}>
             <Menu size={20} />
          </button>
          <h1 className="headline-md">AI Usage Tracker</h1>
        </div>
        
        <div className="flex gap-4">
          <div className="card" style={{ flex: 1, textAlign: 'center' }}>
            <div className="label-md text-muted mb-2">Total Input Tokens</div>
            <div className="headline-md" style={{ color: 'var(--primary)', fontSize: '28px' }}>
              {costs?.history?.reduce((acc: number, c: any) => acc + c.input_tokens, 0).toLocaleString() || '0'}
            </div>
          </div>
          <div className="card" style={{ flex: 1, textAlign: 'center' }}>
            <div className="label-md text-muted mb-2">Total Output Tokens</div>
            <div className="headline-md" style={{ color: 'var(--success)', fontSize: '28px' }}>
              {costs?.history?.reduce((acc: number, c: any) => acc + c.output_tokens, 0).toLocaleString() || '0'}
            </div>
          </div>
        </div>

        <div className="card">
          <h2 className="title-lg mb-4">Usage Log</h2>
          {costs?.history?.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {costs.history.map((c: any, i: number) => (
                <div key={i} className="flex justify-between items-center" style={{ padding: '12px', background: 'var(--surface-container-lowest)', border: '1px solid var(--outline-variant)', borderRadius: 'var(--radius-lg)' }}>
                  <span className="body-md" style={{ fontWeight: 500 }}>{formatDateTime(c.timestamp)}</span>
                  <div className="flex gap-4">
                    <span className="badge" style={{ background: 'var(--primary-container)', color: 'var(--on-primary-container)' }}>{c.input_tokens.toLocaleString()} IN</span>
                    <span className="badge" style={{ background: 'var(--success-container)', color: 'var(--on-success-container)', borderColor: '#86efac' }}>{c.output_tokens.toLocaleString()} OUT</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted body-md">No usage recorded.</p>
          )}
        </div>
      </div>
      )}

      {/* Floating Chatbot */}
      <div className={`chatbot-container ${chatOpen ? 'open' : 'closed'}`} style={{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 1000, width: chatOpen ? '320px' : 'auto', transition: 'all 0.2s ease' }}>
        {!chatOpen ? (
          <button className="btn btn-primary" style={{ borderRadius: 'var(--radius-lg)', width: '48px', height: '48px', padding: 0 }} onClick={() => setChatOpen(true)}>
            <BrainCircuit size={20} />
          </button>
        ) : (
          <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '450px', padding: 0, overflow: 'hidden' }}>
            <div className="flex justify-between items-center" style={{ padding: '12px 16px', background: 'var(--primary)', color: 'var(--on-primary)' }}>
              <div className="flex items-center gap-2">
                <BrainCircuit size={16} />
                <span className="title-md" style={{ color: 'var(--on-primary)', fontSize: '14px', fontWeight: 600 }}>Data Assistant</span>
              </div>
              <button onClick={() => setChatOpen(false)} style={{ background: 'transparent', border: 'none', color: 'var(--on-primary)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}><X size={16}/></button>
            </div>
            
            <div style={{ flex: 1, padding: '16px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px', background: 'var(--surface-container-low)' }}>
              {chatMessages.map((msg, i) => (
                <div key={i} style={{ alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%', padding: '8px 12px', borderRadius: 'var(--radius-lg)', background: msg.role === 'user' ? 'var(--primary-container)' : 'var(--surface-container-lowest)', color: msg.role === 'user' ? 'var(--on-primary-container)' : 'var(--on-surface)', fontSize: '13px', lineHeight: '1.4', border: '1px solid var(--outline-variant)' }}>
                  {msg.content}
                </div>
              ))}
            </div>

            <form onSubmit={sendChatMessage} style={{ padding: '12px', borderTop: '1px solid var(--outline-variant)', background: 'var(--surface-container-lowest)' }}>
              <div className="flex gap-2">
                <input 
                  type="text" 
                  value={chatInput} 
                  onChange={e => setChatInput(e.target.value)} 
                  placeholder="Ask about the data..." 
                  style={{ flex: 1, padding: '8px 10px', borderRadius: 'var(--radius-lg)', border: '1px solid var(--outline)', background: 'var(--surface-container-lowest)', color: 'var(--on-surface)', fontSize: '13px' }}
                />
                <button type="submit" className="btn btn-primary" style={{ padding: '8px 12px' }}>Send</button>
              </div>
            </form>
          </div>
        )}
      </div>

    </div>
  )
}
