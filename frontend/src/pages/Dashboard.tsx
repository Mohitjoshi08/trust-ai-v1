import { useEffect, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceArea, ReferenceLine
} from 'recharts'
import {
  GitCommit, BrainCircuit, RefreshCw,
  ChevronRight, AlertTriangle, TrendingDown, Search,
  Menu, X, Database, Sun, Moon, Activity, Server, Cpu,
  CheckCircle, XCircle, DollarSign, HelpCircle
} from 'lucide-react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { auth } from '../firebase'
import { Sidebar } from '../components/Sidebar'
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

type EvidenceStatus = 'PASS' | 'FAIL' | 'UNKNOWN'
type EvidenceStrength = 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT'

interface EvidenceItem {
  id: string
  log_id: string | null
  checkpoint: string
  status: EvidenceStatus
  timestamp: string | null
  details: string
}

interface RejectedLog {
  log_id: string
  timestamp: string
  rejection_reason: string
}

interface ActionRecommendation {
  lever: string
  action: string
  expected_impact: string
}

interface HypothesisResult {
  id: string
  rank: number
  title: string
  description: string
  evidence_strength: EvidenceStrength
  evidence_matrix: EvidenceItem[]
  analyst_feedback?: boolean | null
  recommended_actions?: ActionRecommendation[]
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
  hypotheses: HypothesisResult[]
  timeline?: any
  reconciliation?: any
  recovery_validation?: any
  rejected_logs?: RejectedLog[]
}

interface TraceData {
  timeseries: {
    data: { timestamp: string; actual: number; predicted_mean: number; upper_bound: number; lower_bound: number }[]
    anomalies: AnomalyWindow[]
  }
  reports: AnomalyReport[]
}

function getConfidenceClass(strength: string): string {
  if (strength === 'HIGH') return 'badge-success'
  if (strength === 'MEDIUM') return 'badge-warning'
  if (strength === 'LOW') return 'badge-warning'
  return 'badge-critical' // INSUFFICIENT
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function formatDateTime(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ── Evidence Status Icon Component ───────────────────────────────
function EvidenceIcon({ status }: { status: EvidenceStatus }) {
  if (status === 'PASS') return <span className="evidence-icon pass"><CheckCircle size={14} /></span>
  if (status === 'FAIL') return <span className="evidence-icon fail"><XCircle size={14} /></span>
  return <span className="evidence-icon unknown"><HelpCircle size={14} /></span>
}

// ── Loading Skeleton Component ───────────────────────────────────
function LoadingSkeleton() {
  return (
    <div className="app-layout">
      <div className="dashboard-content">
        {/* Feed skeleton */}
        <div className="anomaly-feed">
          <div className="feed-header flex items-center gap-3" style={{ height: 56 }}>
            <div className="skeleton skeleton-line short" />
          </div>
          <div className="feed-list">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="skeleton skeleton-feed-item" />
            ))}
          </div>
        </div>

        {/* Main workspace skeleton */}
        <main className="main-workspace">
          <div className="skeleton skeleton-line medium" style={{ height: 24, marginBottom: 8 }} />
          <div className="skeleton skeleton-line short" style={{ height: 14 }} />

          <div className="card">
            <div className="skeleton skeleton-line short" style={{ height: 16, marginBottom: 16 }} />
            <div className="skeleton skeleton-chart" />
          </div>

          <div className="card">
            <div className="skeleton skeleton-line short" style={{ height: 16, marginBottom: 16 }} />
            <div className="skeleton skeleton-card" />
          </div>
        </main>

        {/* Intelligence panel skeleton */}
        <aside className="intelligence-panel">
          <div className="skeleton skeleton-line medium" style={{ height: 18, marginBottom: 16 }} />
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-line long" />
          <div className="skeleton skeleton-line medium" />
        </aside>
      </div>
    </div>
  )
}

// ── Investigation Timeline Component ─────────────────────────────
function InvestigationTimeline({ report }: { report: AnomalyReport }) {
  const aw = report.anomaly_window

  // Metrics lane events
  const metricsEvents = [
    { title: 'Anomaly Start', time: aw.start_time, color: 'var(--error)' },
    { title: `Peak Deviation (${Math.abs(aw.aggregate_deviation_pct).toFixed(1)}%)`, time: aw.start_time, color: 'var(--error)' },
    { title: 'Anomaly End', time: aw.end_time, color: 'var(--warning)' },
  ]
  if (report.recovery_validation?.metric_recovered) {
    metricsEvents.push({
      title: 'Recovery Detected',
      time: report.recovery_validation.recovery_event_timestamp || aw.end_time,
      color: 'var(--success)'
    })
  }

  // Ops events from RAG logs
  const opsEvents = report.rag.retrieved_logs
    .filter(log => ['deploy', 'deployment', 'config', 'error', 'incident', 'ops'].some(
      kw => log.source.toLowerCase().includes(kw) || log.text_content.toLowerCase().includes(kw)
    ))
    .slice(0, 5)
    .map(log => ({
      title: log.text_content.length > 60 ? log.text_content.substring(0, 60) + '...' : log.text_content,
      time: log.timestamp,
      color: 'var(--primary)'
    }))

  // If no ops events matched the keyword filter, show all RAG logs as ops events
  const finalOpsEvents = opsEvents.length > 0 ? opsEvents : report.rag.retrieved_logs.slice(0, 4).map(log => ({
    title: log.text_content.length > 60 ? log.text_content.substring(0, 60) + '...' : log.text_content,
    time: log.timestamp,
    color: 'var(--primary)'
  }))

  // AI analysis events from hypotheses
  const aiEvents = report.hypotheses.map((h, idx) => ({
    title: `H${idx + 1}: ${h.title}`,
    time: aw.start_time, // hypotheses are formed at analysis time
    color: idx === 0 ? 'var(--success)' : 'var(--on-surface-variant)'
  }))

  const renderLane = (
    label: string,
    icon: React.ReactNode,
    dotColor: string,
    events: { title: string; time: string; color: string }[]
  ) => (
    <div className="timeline-lane">
      <div className="timeline-lane-header">
        <div className="timeline-lane-dot" style={{ background: dotColor }} />
        <span className="label-md">{label}</span>
        {icon}
      </div>
      {events.length > 0 ? events.map((evt, i) => (
        <div key={i} className="timeline-event">
          <div className="timeline-event-dot" style={{ background: evt.color }} />
          <div className="timeline-event-content">
            <div className="timeline-event-title">{evt.title}</div>
          </div>
        </div>
      )) : (
        <div className="text-muted" style={{ fontSize: '11px', padding: '8px', fontStyle: 'italic' }}>No events</div>
      )}
    </div>
  )

  return (
    <div className="timeline-container">
      <div className="timeline-lanes">
        {renderLane('Metrics', <Activity size={12} className="text-muted" />, 'var(--error)', metricsEvents)}
        {renderLane('Ops Events', <Server size={12} className="text-muted" />, 'var(--primary)', finalOpsEvents)}
        {renderLane('AI Analysis', <Cpu size={12} className="text-muted" />, 'var(--success)', aiEvents)}
      </div>
    </div>
  )
}

// ── Cross-Hypothesis Evidence Grid ───────────────────────────────
function EvidenceComparisonGrid({ hypotheses }: { hypotheses: HypothesisResult[] }) {
  if (!hypotheses || hypotheses.length === 0) return null

  // Collect all unique checkpoints across all hypotheses
  const allCheckpoints = new Map<string, Map<string, EvidenceStatus>>()

  hypotheses.forEach(h => {
    h.evidence_matrix?.forEach(ev => {
      if (!allCheckpoints.has(ev.checkpoint)) {
        allCheckpoints.set(ev.checkpoint, new Map())
      }
      allCheckpoints.get(ev.checkpoint)!.set(h.id, ev.status)
    })
  })

  if (allCheckpoints.size === 0) return null

  return (
    <div className="evidence-grid">
      <table>
        <thead>
          <tr>
            <th style={{ minWidth: '160px' }}>Evidence Check</th>
            {hypotheses.map((h, idx) => (
              <th key={h.id}>H{idx + 1}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from(allCheckpoints.entries()).map(([checkpoint, statusMap]) => (
            <tr key={checkpoint}>
              <td>{checkpoint}</td>
              {hypotheses.map(h => (
                <td key={h.id}>
                  <EvidenceIcon status={statusMap.get(h.id) || 'UNKNOWN'} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'

export default function Dashboard() {
  const [trace, setTrace] = useState<TraceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [activeTab] = useState('dashboard')
  const [costs, setCosts] = useState<any>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Theme state
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined') {
      return (localStorage.getItem('trace-theme') as 'light' | 'dark') || 'light'
    }
    return 'light'
  })

  // Hypothesis tab state
  const [activeHypothesisTab, setActiveHypothesisTab] = useState(0)
  
  // Persona state
  const [persona, setPersona] = useState<'analyst' | 'executive'>('analyst')
  const [isRegenerating, setIsRegenerating] = useState(false)

  const handlePersonaChange = async (newPersona: 'analyst' | 'executive') => {
    setPersona(newPersona)
    if (!trace || !trace.reports || !trace.reports[selectedIdx]) return
    
    setIsRegenerating(true)
    const report = trace.reports[selectedIdx]
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/analyze/regenerate_hypotheses`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          anomaly_window: report.anomaly_window,
          decomposition: report.decomposition,
          retrieved_logs: report.rag.retrieved_logs,
          persona: newPersona
        })
      })
      
      if (res.ok) {
        const data = await res.json()
        const newTrace = { ...trace }
        newTrace.reports[selectedIdx].hypotheses = data.hypotheses
        newTrace.reports[selectedIdx].rejected_logs = data.rejected_logs
        setTrace(newTrace)
        setActiveHypothesisTab(0)
      }
    } catch (err) {
      console.error("Failed to regenerate hypotheses for new persona", err)
    } finally {
      setIsRegenerating(false)
    }
  }
  
  // Telemetry state
  const [showTelemetry, setShowTelemetry] = useState(false)
  
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

  const [datasets, setDatasets] = useState<any[]>(DEMO_MODE ? ['demo'] : []);
  const navigate = useNavigate();

  // Apply theme on mount and change
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('trace-theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  const fetchTrace = async () => {
    setLoading(true)
    setError(null)
    try {
      const token = DEMO_MODE ? 'demo' : await auth.currentUser?.getIdToken();
      const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {};
      
      // Check if user has uploaded any datasets
      const dsRes = await fetch(`${API_BASE_URL}/api/v1/datasets/`, { headers });
      if (dsRes.ok) {
          const ds = await dsRes.json();
          setDatasets(ds);
          
          // Filter to only datasets that have been mapped (status === 'mapped')
          const mappedDs = ds.filter((d: any) => d.status === 'mapped');
          if (mappedDs.length > 0) {
              // Grab the most recently uploaded mapped dataset
              const latestDs = mappedDs[mappedDs.length - 1];
              const res = await fetch(`${API_BASE_URL}/api/v1/trace_full?dataset_id=${latestDs.id}`, { headers })
              if (!res.ok) throw new Error('Failed to fetch trace data for dataset')
              const data = await res.json()
              setTrace(data)
              setSelectedIdx(0)
              setLoading(false)
              return
          }
      }

      // Fetch the fallback trace reports
      const res = await fetch(`${API_BASE_URL}/api/v1/trace_full`, { headers })
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

  // Reset hypothesis tab when selected report changes
  useEffect(() => {
    setActiveHypothesisTab(0)
  }, [selectedIdx])

  if (loading) {
    return <LoadingSkeleton />
  }

  if (error) {
    return (
      <div className="app-layout">
        <Sidebar open={sidebarOpen} setOpen={setSidebarOpen} />
        <div className="dashboard-content h-full">
          <div className="flex items-center gap-4 mb-6">
            <button className="btn-icon" onClick={() => setSidebarOpen(true)}>
              <Menu size={18} />
            </button>
          </div>
          <div className="flex justify-center items-center h-full">
            <div className="card text-center" style={{ padding: '48px', maxWidth: '400px' }}>
              <AlertTriangle size={48} color="var(--error)" className="mx-auto" />
              <h2 className="title-lg mt-4">Connection Error</h2>
              <p className="text-muted body-md mt-4">{error}</p>
              <button className="btn mt-4 mx-auto" onClick={fetchTrace}>
                <RefreshCw size={16} /> Retry
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (datasets.length === 0) {
    return (
      <div className="app-layout">
        <Sidebar open={sidebarOpen} setOpen={setSidebarOpen} />
        <div className="dashboard-content h-full">
          <div className="flex items-center gap-4 mb-6">
            <button className="btn-icon" onClick={() => setSidebarOpen(true)}>
              <Menu size={18} />
            </button>
          </div>
          <div className="flex justify-center items-center h-full">
            <div className="card text-center" style={{ padding: '48px', maxWidth: '400px' }}>
              <Database size={48} color="var(--primary)" className="mx-auto" />
              <h2 className="title-lg mt-4">Welcome to Trace.ai</h2>
              <p className="text-muted body-md mt-4">You haven't uploaded any data yet. Upload your first CSV dataset to start monitoring for anomalies.</p>
              <button className="btn btn-primary mt-4 mx-auto" onClick={() => navigate('/upload')}>
                Upload Dataset
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!trace || !trace.reports || trace.reports.length === 0) {
    return (
      <div className="app-layout">
        <Sidebar open={sidebarOpen} setOpen={setSidebarOpen} />
        <div className="dashboard-content h-full">
          <div className="flex items-center gap-4 mb-6">
            <button className="btn-icon" onClick={() => setSidebarOpen(true)}>
              <Menu size={18} />
            </button>
          </div>
          <div className="flex justify-center items-center h-full">
            <div className="card text-center" style={{ padding: '48px', maxWidth: '400px' }}>
              <h2 className="title-lg">No anomalies detected</h2>
              <p className="text-muted body-md mt-4">The BSTS model found no significant deviations in the metric data.</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const { timeseries, reports } = trace
  const report = reports[selectedIdx]
  const decomp = report.decomposition
  const primary = decomp.primary_driver
  const activeHypothesis = report.hypotheses?.[activeHypothesisTab]

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
      <Sidebar open={sidebarOpen} setOpen={setSidebarOpen} />

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
            <div className="flex items-center gap-2">
              <button className="btn-icon" onClick={() => setShowTelemetry(true)} title="View LLM Telemetry & Costs">
                <DollarSign size={14} />
              </button>
              <button className="theme-toggle" onClick={toggleTheme} title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}>
                {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
              </button>
              <button className="btn-icon" onClick={fetchTrace}>
                <RefreshCw size={14} />
              </button>
            </div>
          </div>
          <div className="feed-list">
            {reports.map((r, idx) => {
              const aw = r.anomaly_window
              const topHyp = r.hypotheses?.[0]
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
                    {topHyp?.title || `${aw.metric_name} anomaly`}
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
                    tickFormatter={(v: number) => {
                      if (v >= 1000000) return `$${(v / 1000000).toFixed(1)}M`
                      if (v >= 1000) return `$${(v / 1000).toFixed(0)}k`
                      return `$${v.toFixed(0)}`
                    }}
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

          {/* Step 3: Investigation Timeline */}
          <motion.section
            className="card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.5 }}
          >
            <div className="section-title">
              <span className="badge badge-step">Step 3</span>
              <span className="title-lg">Investigation Timeline</span>
            </div>
            <p className="text-muted body-md mb-4">
              Multi-lane temporal view of metrics, operational events, and AI analysis.
            </p>
            <InvestigationTimeline report={report} />
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
            <span className="badge badge-step">Step 4</span>
            <span className="title-lg">Causal Intelligence</span>
          </div>

          {/* Persona Toggle */}
          <div className="flex items-center gap-2 mb-4">
            <span className="label-md text-muted">Persona:</span>
            <select 
              value={persona} 
              onChange={(e) => handlePersonaChange(e.target.value as 'analyst' | 'executive')}
              disabled={isRegenerating}
              style={{ padding: '4px 8px', borderRadius: 'var(--radius-md)', border: '1px solid var(--outline-variant)', background: 'var(--surface-container)', color: 'var(--on-surface)', outline: 'none' }}
            >
              <option value="analyst">Data Analyst</option>
              <option value="executive">Executive</option>
            </select>
            {isRegenerating && <RefreshCw size={14} className="text-muted" style={{ animation: 'spin 1s linear infinite' }} />}
          </div>

          {/* Ambiguity Warning */}
          {decomp.is_ambiguous && (
            <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px', padding: '12px', background: 'var(--warning)', borderRadius: 'var(--radius-md)', color: 'var(--on-warning)', border: '1px solid var(--warning)', opacity: 0.9 }}>
              <AlertTriangle size={18} />
              <span className="label-md" style={{ color: 'inherit' }}>AMBIGUOUS: Human review recommended.</span>
            </div>
          )}

          {/* Ranking Rationale */}
          {report.hypotheses?.length > 1 && report.hypotheses[0] && (
            <div className="ranking-rationale">
              <strong>Ranking Rationale</strong>
              H1 "{report.hypotheses[0].title}" ranked above{' '}
              {report.hypotheses.slice(1).map((h, i) => (
                <span key={h.id}>{i > 0 ? ', ' : ''}H{i + 2} "{h.title}"</span>
              ))}{' '}
              based on evidence strength ({report.hypotheses[0].evidence_strength}) and deterministic checkpoint evaluation.
              {report.hypotheses[0].description && (
                <span style={{ display: 'block', marginTop: '4px', opacity: 0.85 }}>
                  {report.hypotheses[0].description.length > 200
                    ? report.hypotheses[0].description.substring(0, 200) + '...'
                    : report.hypotheses[0].description}
                </span>
              )}
            </div>
          )}

          {/* Cross-Hypothesis Evidence Comparison Grid */}
          {report.hypotheses?.length > 1 && (
            <div style={{ marginBottom: '16px' }}>
              <div className="label-md text-muted mb-2">Evidence Comparison Matrix</div>
              <EvidenceComparisonGrid hypotheses={report.hypotheses} />
            </div>
          )}

          {/* Hypothesis Tabs */}
          {report.hypotheses && report.hypotheses.length > 0 && (
            <>
              <div className="hypothesis-tabs">
                {report.hypotheses.map((h, idx) => (
                  <button
                    key={h.id}
                    className={`hypothesis-tab ${idx === activeHypothesisTab ? 'active' : ''}`}
                    onClick={() => setActiveHypothesisTab(idx)}
                  >
                    H{idx + 1} · {h.evidence_strength}
                  </button>
                ))}
              </div>

              {/* Active Hypothesis Detail */}
              {activeHypothesis && (
                <div className="hypothesis-box" style={{ 
                  padding: '16px', 
                  background: 'var(--surface-container-low)', 
                  borderRadius: 'var(--radius-lg)', 
                  border: '1px solid var(--outline-variant)',
                  opacity: activeHypothesis.analyst_feedback === false ? 0.5 : 1,
                  filter: activeHypothesis.analyst_feedback === false ? 'grayscale(100%)' : 'none',
                  transition: 'all 0.2s ease-in-out'
                }}>
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        {activeHypothesisTab === 0 && (
                          <span className="badge" style={{ background: 'var(--primary)', color: 'var(--on-primary)', borderColor: 'var(--primary)' }}>
                            PRIMARY HYPOTHESIS
                          </span>
                        )}
                        <span className={`badge ${getConfidenceClass(activeHypothesis.evidence_strength)}`}>
                          {activeHypothesis.evidence_strength} EVIDENCE
                        </span>
                      </div>
                      <div className="title-lg">{activeHypothesis.title}</div>
                    </div>
                    {/* Analyst Feedback Toggles */}
                    <div className="flex items-center gap-2">
                      <button 
                        className="btn" 
                        style={{ 
                          padding: '4px 8px', fontSize: '11px', 
                          background: activeHypothesis.analyst_feedback === true ? 'var(--success-container)' : 'transparent',
                          color: activeHypothesis.analyst_feedback === true ? 'var(--on-success-container)' : 'var(--on-surface-variant)',
                          border: activeHypothesis.analyst_feedback === true ? '1px solid #86efac' : '1px solid var(--outline-variant)'
                        }}
                        onClick={() => {
                          const previousState = activeHypothesis.analyst_feedback;
                          const newTrace = {...trace!};
                          newTrace.reports[selectedIdx].hypotheses[activeHypothesisTab].analyst_feedback = true;
                          setTrace(newTrace);
                          
                          fetch(`${API_BASE_URL}/api/v1/analyze/feedback/${activeHypothesis.id}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ is_correct: true })
                          }).catch(err => {
                            console.error("Failed to save feedback", err);
                            const revertTrace = {...trace!};
                            revertTrace.reports[selectedIdx].hypotheses[activeHypothesisTab].analyst_feedback = previousState;
                            setTrace(revertTrace);
                          });
                        }}
                      >
                        Approve
                      </button>
                      <button 
                        className="btn" 
                        style={{ 
                          padding: '4px 8px', fontSize: '11px',
                          background: activeHypothesis.analyst_feedback === false ? 'var(--error-container)' : 'transparent',
                          color: activeHypothesis.analyst_feedback === false ? 'var(--on-error-container)' : 'var(--on-surface-variant)',
                          border: activeHypothesis.analyst_feedback === false ? '1px solid #fca5a5' : '1px solid var(--outline-variant)'
                        }}
                        onClick={() => {
                          const previousState = activeHypothesis.analyst_feedback;
                          const newTrace = {...trace!};
                          newTrace.reports[selectedIdx].hypotheses[activeHypothesisTab].analyst_feedback = false;
                          setTrace(newTrace);
                          
                          fetch(`${API_BASE_URL}/api/v1/analyze/feedback/${activeHypothesis.id}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ is_correct: false })
                          }).catch(err => {
                            console.error("Failed to save feedback", err);
                            const revertTrace = {...trace!};
                            revertTrace.reports[selectedIdx].hypotheses[activeHypothesisTab].analyst_feedback = previousState;
                            setTrace(revertTrace);
                          });
                        }}
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                  
                  <p className="body-md text-muted mb-4" style={{ lineHeight: '1.5' }}>{activeHypothesis.description}</p>
                  
                  {/* Action Recommendations */}
                  {activeHypothesis.recommended_actions && activeHypothesis.recommended_actions.length > 0 && (
                    <div className="mt-4 mb-4">
                      <div className="label-md text-muted mb-2">Recommended Actions</div>
                      <div className="flex flex-col gap-2">
                        {activeHypothesis.recommended_actions.map((action: any, i: number) => (
                          <div key={i} style={{ padding: '12px', background: 'var(--surface-container)', borderRadius: 'var(--radius-md)', border: '1px solid var(--outline-variant)' }}>
                            <div className="flex gap-2 items-center mb-1">
                              <span className="badge" style={{ background: 'var(--primary-container)', color: 'var(--on-primary-container)' }}>{action.driver}</span>
                              <span className="text-muted" style={{ fontSize: '12px' }}>→</span>
                              <span className="badge" style={{ background: 'var(--surface-container-highest)', color: 'var(--on-surface)' }}>{action.lever}</span>
                            </div>
                            <div className="body-md mb-1" style={{ fontWeight: 500 }}>{action.action}</div>
                            <div className="text-muted" style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <Activity size={12} /> Expected Impact: {action.expected_impact}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Evidence Matrix Data Table */}
                  {activeHypothesis.evidence_matrix && activeHypothesis.evidence_matrix.length > 0 && (
                    <div className="evidence-matrix">
                      <div className="label-md text-muted mb-2">Evidence Matrix</div>
                      <div style={{ border: '1px solid var(--outline-variant)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                          <thead style={{ background: 'var(--surface-container)' }}>
                            <tr>
                              <th style={{ padding: '8px 12px', borderBottom: '1px solid var(--outline-variant)', fontWeight: 600 }}>Checkpoint</th>
                              <th style={{ padding: '8px 12px', borderBottom: '1px solid var(--outline-variant)', fontWeight: 600 }}>Status</th>
                              <th style={{ padding: '8px 12px', borderBottom: '1px solid var(--outline-variant)', fontWeight: 600 }}>Timestamp</th>
                              <th style={{ padding: '8px 12px', borderBottom: '1px solid var(--outline-variant)', fontWeight: 600 }}>Details</th>
                            </tr>
                          </thead>
                          <tbody>
                            {activeHypothesis.evidence_matrix.map((ev) => (
                              <tr key={ev.id} style={{ borderBottom: '1px solid var(--outline-variant)' }}>
                                <td style={{ padding: '8px 12px', verticalAlign: 'top', fontWeight: 500 }}>{ev.checkpoint}</td>
                                <td style={{ padding: '8px 12px', verticalAlign: 'top' }}>
                                  <span className={`badge ${ev.status === 'PASS' ? 'badge-success' : ev.status === 'FAIL' ? 'badge-critical' : 'badge-warning'}`}>
                                    {ev.status}
                                  </span>
                                </td>
                                <td style={{ padding: '8px 12px', verticalAlign: 'top', color: 'var(--on-surface-variant)' }}>
                                  {ev.timestamp ? formatDateTime(ev.timestamp) : '-'}
                                </td>
                                <td style={{ padding: '8px 12px', verticalAlign: 'top', color: 'var(--on-surface-variant)' }}>{ev.details}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                  
                  {/* Red Herrings */}
                  {activeHypothesisTab === 0 && report.rejected_logs && report.rejected_logs.length > 0 && (
                    <div className="evidence-matrix mt-4">
                      <div className="label-md text-muted mb-2">Rejected Evidence (Red Herrings)</div>
                      <div style={{ border: '1px solid var(--outline-variant)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left', opacity: 0.7 }}>
                          <thead style={{ background: 'var(--surface-container)' }}>
                            <tr>
                              <th style={{ padding: '8px 12px', borderBottom: '1px solid var(--outline-variant)', fontWeight: 600 }}>Log ID</th>
                              <th style={{ padding: '8px 12px', borderBottom: '1px solid var(--outline-variant)', fontWeight: 600 }}>Timestamp</th>
                              <th style={{ padding: '8px 12px', borderBottom: '1px solid var(--outline-variant)', fontWeight: 600 }}>Rejection Reason</th>
                            </tr>
                          </thead>
                          <tbody>
                            {report.rejected_logs.map((rl, i) => (
                              <tr key={i} style={{ borderBottom: '1px solid var(--outline-variant)' }}>
                                <td style={{ padding: '8px 12px', verticalAlign: 'top', fontWeight: 500, textDecoration: 'line-through' }}>{rl.log_id}</td>
                                <td style={{ padding: '8px 12px', verticalAlign: 'top', color: 'var(--on-surface-variant)' }}>{formatDateTime(rl.timestamp)}</td>
                                <td style={{ padding: '8px 12px', verticalAlign: 'top', color: 'var(--error)' }}>{rl.rejection_reason}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                  
                  {/* Recovery Validation (Only on top hypothesis) */}
                  {activeHypothesisTab === 0 && report.recovery_validation && (
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
            </>
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

      {/* Telemetry Modal */}
      {showTelemetry && (
        <div className="modal-overlay" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setShowTelemetry(false)}>
          <div className="modal-content card" style={{ padding: '24px', width: '500px', maxWidth: '90%', maxHeight: '80vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="title-lg">LLM Telemetry & Cost</h3>
              <button className="btn-icon" onClick={() => setShowTelemetry(false)}><X size={16} /></button>
            </div>
            {costs ? (
              <div>
                <div className="mb-4" style={{ padding: '16px', background: 'var(--surface-container-highest)', borderRadius: 'var(--radius-md)' }}>
                  <div className="label-md text-muted">Total Estimated Cost</div>
                  <div className="title-lg" style={{ color: 'var(--primary)' }}>${costs.total_usd?.toFixed(4)}</div>
                </div>
                <div className="label-md mb-2">History</div>
                <div className="flex flex-col gap-2">
                  {costs.history?.slice().reverse().map((c: any, i: number) => (
                    <div key={i} style={{ padding: '12px', border: '1px solid var(--outline-variant)', borderRadius: 'var(--radius-md)' }}>
                      <div className="flex justify-between text-muted" style={{ fontSize: '12px', marginBottom: '4px' }}>
                        <span>{new Date(c.timestamp).toLocaleString()}</span>
                        <span>{c.model}</span>
                      </div>
                      <div className="flex justify-between mt-2 text-sm">
                        <span>Tokens: {c.input_tokens} In / {c.output_tokens} Out</span>
                        <span>{c.latency_ms}ms</span>
                      </div>
                      <div className="mt-1" style={{ fontSize: '12px', color: 'var(--primary)' }}>
                        Cost: ${c.cost_usd?.toFixed(5)} | Persona: {c.persona}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-muted">Loading telemetry data...</p>
            )}
          </div>
        </div>
      )}

    </div>
  )
}
