import { useState, useEffect, useRef } from "react"
import { apiFetch } from "../api"

function TimeRangeChart({ data, keyPerf, keyBurnout }) {
  const svgRef       = useRef(null)
  const containerRef = useRef(null)
  const [hover,  setHover]  = useState(null)
  const [range,  setRange]  = useState(30)
  const [dims,   setDims]   = useState({ w: 800, h: 220 })

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect
      setDims({ w: Math.floor(width), h: Math.floor(height) })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  if (!data || data.length < 2) return null
  const sliced = data.slice(-range)
  if (sliced.length < 2) return null

  const { w: W, h: H } = dims
  const pL = 34, pR = 10, pT = 10, pB = 24

  const perf    = sliced.map(d => d[keyPerf]    ?? 0)
  const burnout = sliced.map(d => d[keyBurnout] ?? 0)
  const cx = i => pL + (i / (sliced.length - 1)) * (W - pL - pR)
  const cy = v => pT + (1 - v / 100) * (H - pT - pB)
  const lp = vals => vals.map((v,i) => `${i===0?"M":"L"}${cx(i).toFixed(1)},${cy(v).toFixed(1)}`).join(" ")
  const ap = vals => `${lp(vals)} L${cx(vals.length-1).toFixed(1)},${cy(0).toFixed(1)} L${cx(0).toFixed(1)},${cy(0).toFixed(1)} Z`

  const yTicks = [0,25,50,75,100]
  const xIdxs  = Array.from({length:Math.min(8,sliced.length)},(_,i)=>Math.round(i*(sliced.length-1)/(Math.min(8,sliced.length)-1)))
  const gc = "rgba(128,128,120,0.12)", gs = "rgba(128,128,120,0.22)", lc = "#9e9b94"

  const onMove = e => {
    const svg = svgRef.current; if (!svg) return
    const rect  = svg.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, ((e.clientX - rect.left) / rect.width * W - pL) / (W - pL - pR)))
    setHover(Math.round(ratio * (sliced.length - 1)))
  }

  const hP = hover !== null ? perf[hover]    : perf[perf.length-1]
  const hB = hover !== null ? burnout[hover] : burnout[burnout.length-1]
  const hD = hover !== null ? sliced[hover]?.date : null
  const pc = hP > 65 ? "#1D9E75" : hP > 40 ? "#EF9F27" : "#D85A30"
  const bc = hB < 35 ? "#1D9E75" : hB < 60 ? "#EF9F27" : "#D85A30"

  const last7=data.slice(-7), prev7=data.slice(-14,-7)
  const pTrend = last7.length&&prev7.length?(last7.reduce((s,d)=>s+(d[keyPerf]??0),0)/last7.length)-(prev7.reduce((s,d)=>s+(d[keyPerf]??0),0)/prev7.length):null
  const bTrend = last7.length&&prev7.length?(last7.reduce((s,d)=>s+(d[keyBurnout]??0),0)/last7.length)-(prev7.reduce((s,d)=>s+(d[keyBurnout]??0),0)/prev7.length):null

  return (
    <div style={{display:"flex",flexDirection:"column",gap:8,height:"100%"}}>
      {/* Scores + controls */}
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",flexShrink:0}}>
        <div style={{display:"flex",alignItems:"center",gap:20}}>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <div style={{width:8,height:8,borderRadius:"50%",background:"#1D9E75"}}/>
            <span style={{fontSize:11,color:"var(--faint)"}}>Performance</span>
            <span style={{fontSize:22,fontWeight:500,color:pc}}>{hP.toFixed(0)}</span>
            {pTrend!==null&&<span style={{fontSize:10,color:pTrend>0?"#1D9E75":"#D85A30"}}>{pTrend>0?"↑":"↓"}{Math.abs(pTrend).toFixed(1)}</span>}
          </div>
          <div style={{width:1,height:16,background:"var(--border)"}}/>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <div style={{width:8,height:8,borderRadius:"50%",background:"#D85A30"}}/>
            <span style={{fontSize:11,color:"var(--faint)"}}>Burnout</span>
            <span style={{fontSize:22,fontWeight:500,color:bc}}>{hB.toFixed(0)}</span>
            {bTrend!==null&&<span style={{fontSize:10,color:bTrend<0?"#1D9E75":"#D85A30"}}>{bTrend>0?"↑":"↓"}{Math.abs(bTrend).toFixed(1)}</span>}
          </div>
          {hD&&<><div style={{width:1,height:16,background:"var(--border)"}}/><span style={{fontSize:10,color:"var(--faint)"}}>{hD.slice(5)}</span></>}
        </div>
        <div style={{display:"flex",gap:4}}>
          {[7,14,30].map(r=>(
            <button key={r} onClick={()=>setRange(r)} style={{padding:"3px 10px",borderRadius:99,fontSize:10,cursor:"pointer",fontFamily:"inherit",border:"1px solid var(--border)",background:range===r?"var(--text)":"transparent",color:range===r?"var(--bg)":"var(--faint)",transition:"all 0.15s"}}>{r}d</button>
          ))}
        </div>
      </div>

      {/* Chart — fills remaining height, full width */}
      <div ref={containerRef} style={{flex:1,minHeight:0,width:"100%"}}>
        <svg
          ref={svgRef}
          width={W}
          height={H}
          style={{display:"block",width:"100%",height:"100%",cursor:"crosshair"}}
          onMouseMove={onMove}
          onMouseLeave={()=>setHover(null)}
        >
          <defs>
            <linearGradient id="gp" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#1D9E75" stopOpacity="0.18"/><stop offset="100%" stopColor="#1D9E75" stopOpacity="0"/></linearGradient>
            <linearGradient id="gb" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#D85A30" stopOpacity="0.14"/><stop offset="100%" stopColor="#D85A30" stopOpacity="0"/></linearGradient>
          </defs>
          {yTicks.map(t=>(
            <g key={t}>
              <line x1={pL} y1={cy(t)} x2={W-pR} y2={cy(t)} stroke={t%25===0?gs:gc} strokeWidth={t%25===0?0.75:0.5} strokeDasharray={t%25===0?"none":"2 4"}/>
              <text x={pL-5} y={cy(t)} fontSize="9" fill={lc} textAnchor="end" dominantBaseline="central" fontFamily="DM Sans,sans-serif">{t}</text>
            </g>
          ))}
          {xIdxs.map(i=>(
            <text key={i} x={cx(i)} y={H-5} fontSize="9" fill={lc} textAnchor="middle" fontFamily="DM Sans,sans-serif">{sliced[i]?.date?.slice(5)}</text>
          ))}
          <line x1={pL} y1={pT} x2={pL} y2={H-pB} stroke={gs} strokeWidth="0.75"/>
          <path d={ap(perf)}    fill="url(#gp)"/>
          <path d={ap(burnout)} fill="url(#gb)"/>
          <path d={lp(perf)}    fill="none" stroke="#1D9E75" strokeWidth="1.5" strokeLinejoin="round"/>
          <path d={lp(burnout)} fill="none" stroke="#D85A30" strokeWidth="1.5" strokeLinejoin="round"/>
          {hover!==null&&<>
            <line x1={cx(hover)} y1={pT} x2={cx(hover)} y2={H-pB} stroke="rgba(128,128,120,0.3)" strokeWidth="1" strokeDasharray="3 3"/>
            <circle cx={cx(hover)} cy={cy(perf[hover])}    r="4" fill="#1D9E75" stroke="var(--surface)" strokeWidth="1.5"/>
            <circle cx={cx(hover)} cy={cy(burnout[hover])} r="4" fill="#D85A30" stroke="var(--surface)" strokeWidth="1.5"/>
          </>}
          {hover===null&&<>
            <circle cx={cx(sliced.length-1)} cy={cy(perf[perf.length-1])}       r="3.5" fill="#1D9E75"/>
            <circle cx={cx(sliced.length-1)} cy={cy(burnout[burnout.length-1])} r="3.5" fill="#D85A30"/>
          </>}
        </svg>
      </div>
    </div>
  )
}



function DonutChart({ sleep, study, training }) {
  const free = Math.max(0, 24-sleep-study-training)
  const segs = [{label:"Sleep",value:sleep,color:"#378ADD"},{label:"Study",value:study,color:"#1D9E75"},{label:"Training",value:training,color:"#7F77DD"},{label:"Free",value:free,color:"rgba(128,128,120,0.2)"}]
  const r=30,sw=8,circ=2*Math.PI*r
  let off=0
  const arcs = segs.map(s=>{const dash=(s.value/24)*circ;const a={...s,dash,gap:circ-dash,off};off+=dash;return a})
  return (
    <div style={{display:"flex",alignItems:"center",gap:12,flex:1}}>
      <div style={{position:"relative",width:74,height:74,flexShrink:0}}>
        <svg width="74" height="74" viewBox="0 0 74 74" style={{transform:"rotate(-90deg)"}}>
          {arcs.map((a,i)=><circle key={i} cx="37" cy="37" r={r} fill="none" stroke={a.color} strokeWidth={sw} strokeDasharray={`${a.dash} ${a.gap}`} strokeDashoffset={-a.off}/>)}
        </svg>
        <div style={{position:"absolute",inset:0,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center"}}>
          <div style={{fontSize:13,fontWeight:500,color:"var(--text)",lineHeight:1}}>{free.toFixed(1)}</div>
          <div style={{fontSize:7,color:"var(--faint)",marginTop:1}}>free</div>
        </div>
      </div>
      <div style={{flex:1,display:"flex",flexDirection:"column",gap:4}}>
        {segs.filter(s=>s.label!=="Free").map(s=>(
          <div key={s.label} style={{display:"flex",justifyContent:"space-between",alignItems:"center",fontSize:10,color:"var(--muted)"}}>
            <div style={{display:"flex",alignItems:"center",gap:4}}>
              <div style={{width:6,height:6,borderRadius:"50%",background:s.color}}/><span>{s.label}</span>
            </div>
            <span style={{fontWeight:500,color:"var(--text)"}}>{s.value.toFixed(1)}h</span>
          </div>
        ))}
        <div style={{fontSize:8,color:"var(--faint)",paddingTop:2,borderTop:"1px solid var(--border)"}}>{free.toFixed(1)}h of 24h free</div>
      </div>
    </div>
  )
}


function DonutChartLarge({ sleep, study, training }) {
  const free = Math.max(0, 24-sleep-study-training)
  const segs = [{label:"Sleep",value:sleep,color:"#378ADD"},{label:"Study",value:study,color:"#1D9E75"},{label:"Training",value:training,color:"#7F77DD"},{label:"Free",value:free,color:"rgba(128,128,120,0.2)"}]
  const r=40,sw=11,circ=2*Math.PI*r
  let off=0
  const arcs = segs.map(s=>{const dash=(s.value/24)*circ;const a={...s,dash,gap:circ-dash,off};off+=dash;return a})
  return (
    <div style={{display:"flex",alignItems:"center",gap:16,flex:1}}>
      <div style={{position:"relative",width:98,height:98,flexShrink:0}}>
        <svg width="98" height="98" viewBox="0 0 98 98" style={{transform:"rotate(-90deg)"}}>
          {arcs.map((a,i)=><circle key={i} cx="49" cy="49" r={r} fill="none" stroke={a.color} strokeWidth={sw} strokeDasharray={`${a.dash} ${a.gap}`} strokeDashoffset={-a.off}/>)}
        </svg>
        <div style={{position:"absolute",inset:0,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center"}}>
          <div style={{fontSize:16,fontWeight:500,color:"var(--text)",lineHeight:1}}>{free.toFixed(1)}</div>
          <div style={{fontSize:9,color:"var(--faint)",marginTop:2}}>hrs free</div>
        </div>
      </div>
      <div style={{flex:1,display:"flex",flexDirection:"column",gap:7}}>
        {segs.filter(s=>s.label!=="Free").map(s=>(
          <div key={s.label}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",fontSize:12,color:"var(--muted)",marginBottom:3}}>
              <div style={{display:"flex",alignItems:"center",gap:5}}>
                <div style={{width:8,height:8,borderRadius:"50%",background:s.color}}/><span>{s.label}</span>
              </div>
              <span style={{fontWeight:500,color:"var(--text)"}}>{s.value.toFixed(1)}h</span>
            </div>
            <div style={{height:3,background:"var(--border)",borderRadius:99,overflow:"hidden"}}>
              <div style={{height:"100%",width:`${(s.value/24)*100}%`,background:s.color,borderRadius:99}}/>
            </div>
          </div>
        ))}
        <div style={{fontSize:10,color:"var(--faint)",paddingTop:4,borderTop:"1px solid var(--border)"}}>{free.toFixed(1)}h of 24h free</div>
      </div>
    </div>
  )
}

function ModeCard({ plan, isActive, isRecommended, accent, onClick }) {
  if (!plan) return null
  const bBg  = plan.pred_burnout>55?"var(--red-bg)":plan.pred_burnout>35?"var(--amber-bg)":"var(--green-bg)"
  const bTxt = plan.pred_burnout>55?"var(--red-txt)":plan.pred_burnout>35?"var(--amber-txt)":"var(--green-txt)"
  return (
    <div onClick={onClick} style={{background:"var(--surface)",border:isActive?`2px solid ${accent}`:"1px solid var(--border)",borderRadius:"var(--radius-lg)",padding:"18px 20px",cursor:"pointer",position:"relative",transition:"border-color 0.15s"}}>
      {isRecommended&&<div style={{position:"absolute",top:-10,left:18,background:accent,color:"white",fontSize:10,padding:"3px 10px",borderRadius:99,fontWeight:500}}>recommended</div>}
      <div style={{display:"flex",alignItems:"center",gap:20}}>
        <div style={{width:110,flexShrink:0}}>
          <div style={{fontSize:9,color:"var(--faint)",textTransform:"uppercase",letterSpacing:"0.06em",marginBottom:4}}>{plan.mode}</div>
          <div style={{fontSize:15,fontWeight:500,color:"var(--text)",lineHeight:1.3}}>{plan.description}</div>
          <div style={{fontSize:11,color:"var(--faint)",marginTop:4,lineHeight:1.4}}>{plan.context}</div>
        </div>
        <div style={{flex:1,minWidth:0}}><DonutChartLarge sleep={plan.sleep} study={plan.study} training={plan.training}/></div>
        <div style={{display:"flex",flexDirection:"column",gap:7,flexShrink:0,width:90}}>
          <div style={{background:"var(--green-bg)",borderRadius:"var(--radius-md)",padding:"10px 14px",textAlign:"center"}}>
            <div style={{fontSize:9,color:"var(--green-txt)",marginBottom:2}}>performance</div>
            <div style={{fontSize:26,fontWeight:500,color:"var(--green-txt)",lineHeight:1}}>{plan.pred_perf}</div>
          </div>
          <div style={{background:bBg,borderRadius:"var(--radius-md)",padding:"10px 14px",textAlign:"center"}}>
            <div style={{fontSize:9,color:bTxt,marginBottom:2}}>burnout</div>
            <div style={{fontSize:26,fontWeight:500,color:bTxt,lineHeight:1}}>{plan.pred_burnout}</div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Dashboard({ username, onNavigate }) {
  const [data,         setData]         = useState(null)
  const [tasks,        setTasks]        = useState([])
  const [progress,     setProgress]     = useState(null)
  const [loading,      setLoading]      = useState(true)
  const [error,        setError]        = useState(null)
  const [selectedMode, setSelectedMode] = useState(null)

  useEffect(() => {
    setLoading(true); setError(null)
    apiFetch(`/users/${username}/analysis`)
      .then(r=>{ if(!r.ok) return r.json().then(e=>Promise.reject(e.detail)); return r.json() })
      .then(d=>{
        setData(d)
        const recMode = d.recommended_mode || 'comfortable'; const recPlan = d.plans?.[recMode] || d.optimal_plan; return apiFetch(`/tasks/${username}?recommended_hours=${recPlan?.study??3.5}`)
      })
      .then(r=>r.json())
      .then(t=>{ setTasks(t.tasks||[]); setProgress(t.progress||null); setLoading(false) })
      .catch(e=>{ setError(String(e)); setLoading(false) })
  }, [username])

  // Refetch tasks when user picks a different plan mode
  useEffect(() => {
    if (!data) return
    const mode = selectedMode || data.recommended_mode || "comfortable"
    const plan = data.plans?.[mode] || data.optimal_plan
    const recHours = plan?.study ?? 3.5
    apiFetch(`/tasks/${username}?recommended_hours=${recHours}`)
      .then(r => r.json())
      .then(t => { setTasks(t.tasks||[]); setProgress(t.progress||null) })
      .catch(() => {})
  }, [selectedMode, data])

  if (loading) return <div className="loading">Loading your data…</div>
  if (error) return (
    <div className="empty-state">
      <p>{error==="Not enough data yet"?"Keep logging — you need at least a few entries to unlock your dashboard.":`Could not load data: ${error}`}</p>
      <button className="btn-primary" onClick={()=>onNavigate("log")}>Log an entry</button>
    </div>
  )

  const { baselines, chart_data, profile, plans, recommended_mode } = data
  const hour       = new Date().getHours()
  const greeting   = hour<12?"Good morning":hour<17?"Good afternoon":"Good evening"
  const today      = new Date().toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"})
  const activeMode = selectedMode||recommended_mode||"comfortable"
  const pct        = progress?.progress_pct??0
  const barColor   = pct>=100?"var(--green)":pct>=50?"var(--blue)":"var(--amber)"
  const accents    = {recovery:"var(--blue)",comfortable:"var(--green)",challenge:"var(--purple)"}

  // Sleep debt
  const baselineSleep = chart_data.reduce((s,d)=>s+(d.avg_sleep_7??0),0)/Math.max(1,chart_data.length)
  const sleepDebt     = Math.max(0,chart_data.slice(-7).reduce((s,d)=>s+Math.max(0,baselineSleep-(d.avg_sleep_7??0)),0))
  const debtRounded   = Math.round(sleepDebt*10)/10
  const daysToRecover = sleepDebt>0?Math.ceil(sleepDebt/0.5):0
  const dColor = sleepDebt<2?"var(--green-txt)":sleepDebt<5?"var(--amber-txt)":"var(--red-txt)"
  const dBg    = sleepDebt<2?"var(--green-bg)":sleepDebt<5?"var(--amber-bg)":"var(--red-bg)"

  // Trends
  const last7=chart_data.slice(-7), prev7=chart_data.slice(-14,-7)
  const perfTrend   = last7.length&&prev7.length?(last7.reduce((s,d)=>s+(d.performance_score??0),0)/last7.length)-(prev7.reduce((s,d)=>s+(d.performance_score??0),0)/prev7.length):null
  const burnoutTrend= last7.length&&prev7.length?(last7.reduce((s,d)=>s+(d.burnout_risk??0),0)/last7.length)-(prev7.reduce((s,d)=>s+(d.burnout_risk??0),0)/prev7.length):null

  const insight = () => {
    if (!profile||!Object.keys(profile).length) return null
    const top = Object.entries(profile).sort((a,b)=>b[1]-a[1])[0]?.[0]?.replace("_importance","").replace("_"," ")
    return top?`Your model weights ${top} most heavily.`:null
  }

  return (
    <div style={{display:"flex",flexDirection:"column",gap:12}}>
      {/* Header */}
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
        <div>
          <h1 style={{fontSize:16,fontWeight:500,color:"var(--text)"}}>{greeting}, {username}</h1>
          <p style={{fontSize:12,color:"var(--faint)",marginTop:2}}>Here's how you're doing</p>
        </div>
        <span style={{fontSize:12,color:"var(--faint)",background:"var(--surface)",border:"1px solid var(--border)",borderRadius:"var(--radius-sm)",padding:"5px 10px"}}>{today}</span>
      </div>

      {/* Tasks bar */}
      <div style={{background:"var(--surface)",border:"1px solid var(--border)",borderRadius:"var(--radius-lg)",padding:"12px 16px"}}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:tasks.length>0?8:0}}>
          <div style={{display:"flex",alignItems:"center",gap:14}}>
            <span style={{fontSize:13,fontWeight:500,color:"var(--text)"}}>Today's tasks</span>
            {progress&&(
              <div style={{display:"flex",alignItems:"center",gap:8}}>
                <div style={{width:100,height:4,background:"var(--border)",borderRadius:99,overflow:"hidden"}}>
                  <div style={{height:"100%",width:`${pct}%`,background:barColor,borderRadius:99,transition:"width 0.8s ease"}}/>
                </div>
                <span style={{fontSize:11,color:pct>=100?"var(--green-txt)":"var(--faint)"}}>{pct>=100?"Goal reached!":`${progress.completed_hours}h / ${progress.recommended}h · ${activeMode} plan`}</span>
              </div>
            )}
          </div>
          <button onClick={()=>onNavigate("tasks")} style={{background:"none",border:"1px solid var(--border)",borderRadius:"var(--radius-sm)",fontSize:11,padding:"4px 10px",cursor:"pointer",color:"var(--muted)",fontFamily:"inherit"}}>manage →</button>
        </div>
        {tasks.length===0?(
          <span style={{fontSize:12,color:"var(--faint)"}}>No tasks yet. <button onClick={()=>onNavigate("tasks")} style={{background:"none",border:"none",color:"var(--blue-txt)",cursor:"pointer",fontSize:12,padding:0,fontFamily:"inherit"}}>Add one →</button></span>
        ):(
          <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
            {tasks.slice(0,7).map(task=>(
              <div key={task.id} style={{display:"flex",alignItems:"center",gap:5,padding:"3px 10px",background:"var(--bg)",borderRadius:99,fontSize:11,border:"1px solid var(--border)"}}>
                <div style={{width:10,height:10,borderRadius:3,border:task.completed?"none":"1px solid var(--border-md)",background:task.completed?"var(--green)":"transparent",flexShrink:0,display:"flex",alignItems:"center",justifyContent:"center"}}>
                  {task.completed&&<div style={{width:4,height:2,borderLeft:"1.5px solid white",borderBottom:"1.5px solid white",transform:"rotate(-45deg) translateY(-1px)"}}/>}
                </div>
                <span style={{color:task.completed?"var(--faint)":"var(--text)",textDecoration:task.completed?"line-through":"none"}}>{task.name}</span>
                <span style={{color:"var(--faint)",fontSize:10}}>{task.hours}h</span>
              </div>
            ))}
            {tasks.length>7&&<span style={{fontSize:11,color:"var(--faint)",alignSelf:"center"}}>+{tasks.length-7} more</span>}
          </div>
        )}
      </div>

      {/* Chart — full width */}
      <div style={{background:"var(--surface)",border:"1px solid var(--border)",borderRadius:"var(--radius-lg)",padding:"1rem"}}>
        <div style={{height:360}}>
          <TimeRangeChart data={chart_data} keyPerf="performance_score" keyBurnout="burnout_risk"/>
        </div>
      </div>

      {/* Plans + stats side by side */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,alignItems:"start"}}>

        {/* LEFT — stats */}
        <div style={{display:"flex",flexDirection:"column",gap:12}}>

          {/* Sleep debt */}
          <div style={{background:dBg,border:`1px solid ${dColor}33`,borderRadius:"var(--radius-lg)",padding:"14px 16px"}}>
            <div style={{display:"flex",alignItems:"center",gap:16}}>
              <div style={{textAlign:"center",flexShrink:0,width:60}}>
                <div style={{fontSize:8,color:dColor,textTransform:"uppercase",letterSpacing:"0.05em",marginBottom:3}}>Sleep debt</div>
                <div style={{fontSize:30,fontWeight:500,color:dColor,lineHeight:1}}>{debtRounded}</div>
                <div style={{fontSize:8,color:dColor,marginTop:2,opacity:0.8}}>hrs (7d)</div>
              </div>
              <div style={{flex:1,borderLeft:`1px solid ${dColor}44`,paddingLeft:14}}>
                <div style={{fontSize:12,fontWeight:500,color:dColor,marginBottom:3}}>
                  {sleepDebt<1?"Well rested":sleepDebt<3?"Mild deficit":sleepDebt<6?"Significant debt":"High debt"}
                </div>
                <div style={{fontSize:11,color:dColor,opacity:0.85,lineHeight:1.4}}>
                  {sleepDebt<1?"Sleep consistent with your baseline this week.":`${debtRounded}h behind baseline.${daysToRecover>0?` ~${daysToRecover} days to recover.`:""}`}
                </div>
                <div style={{marginTop:7,height:3,background:`${dColor}22`,borderRadius:99,overflow:"hidden"}}>
                  <div style={{height:"100%",width:`${Math.min(100,(sleepDebt/10)*100)}%`,background:dColor,borderRadius:99}}/>
                </div>
              </div>
            </div>
          </div>

          {/* Weekly snapshot */}
          <div style={{background:"var(--surface)",border:"1px solid var(--border)",borderRadius:"var(--radius-lg)",padding:"14px 16px"}}>
            <div style={{fontSize:13,fontWeight:500,color:"var(--text)",marginBottom:10}}>Weekly snapshot</div>
            {[
              {label:"Sleep debt recovery",  value:daysToRecover===0?"Fully recovered":`~${daysToRecover} days`, color:daysToRecover===0?"var(--green-txt)":daysToRecover<4?"var(--amber-txt)":"var(--red-txt)"},
              {label:"Performance vs last week", value:perfTrend!==null?`${perfTrend>0?"+":""}${perfTrend.toFixed(1)}`:"—", color:perfTrend===null?"var(--faint)":perfTrend>0?"var(--green-txt)":"var(--red-txt)"},
              {label:"Burnout vs last week",     value:burnoutTrend!==null?`${burnoutTrend>0?"+":""}${burnoutTrend.toFixed(1)}`:"—", color:burnoutTrend===null?"var(--faint)":burnoutTrend<0?"var(--green-txt)":"var(--red-txt)"},
              {label:"Avg sleep this week",      value:`${(last7.reduce((s,d)=>s+(d.avg_sleep_7??0),0)/Math.max(1,last7.length)).toFixed(1)}h`, color:"var(--blue-txt)"},
              {label:"Avg stress this week",     value:`${(last7.reduce((s,d)=>s+(d.avg_stress_7??0),0)/Math.max(1,last7.length)).toFixed(1)}/10`, color:"var(--muted)"},
            ].map(row=>(
              <div key={row.label} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"7px 0",borderBottom:"1px solid var(--border)"}}>
                <span style={{fontSize:12,color:"var(--muted)"}}>{row.label}</span>
                <span style={{fontSize:13,fontWeight:500,color:row.color}}>{row.value}</span>
              </div>
            ))}
          </div>

          {/* Baselines */}
          <div style={{background:"var(--surface)",border:"1px solid var(--border)",borderRadius:"var(--radius-lg)",padding:"14px 16px"}}>
            <div style={{fontSize:13,fontWeight:500,color:"var(--text)",marginBottom:10}}>Your baselines</div>
            {[
              {label:"Optimal sleep",    val:`${baselines.optimal_sleep}h`,      pct:(baselines.optimal_sleep/12)*100,color:"var(--blue)"},
              {label:"Optimal load",     val:`${baselines.optimal_load}h`,       pct:(baselines.optimal_load/8)*100,  color:"var(--green)"},
              {label:"Baseline stress",  val:`${baselines.baseline_stress}/10`,  pct:baselines.baseline_stress*10,    color:"var(--amber)"},
              {label:"Baseline fatigue", val:`${baselines.baseline_fatigue}/10`, pct:baselines.baseline_fatigue*10,   color:"var(--red)"},
            ].map(b=>(
              <div key={b.label} style={{marginBottom:9}}>
                <div style={{display:"flex",justifyContent:"space-between",fontSize:12,color:"var(--muted)",marginBottom:3}}>
                  <span>{b.label}</span><span style={{fontWeight:500,color:"var(--text)"}}>{b.val}</span>
                </div>
                <div style={{height:4,background:"var(--border)",borderRadius:99,overflow:"hidden"}}>
                  <div style={{height:"100%",width:`${Math.min(100,b.pct)}%`,background:b.color,borderRadius:99}}/>
                </div>
              </div>
            ))}
            {insight()&&(
              <div style={{background:"var(--bg)",borderRadius:"var(--radius-sm)",padding:"9px 12px",marginTop:4}}>
                <div style={{fontSize:10,color:"var(--faint)",marginBottom:2}}>model insight</div>
                <div style={{fontSize:12,color:"var(--muted)",lineHeight:1.5}}>{insight()}</div>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT — plan cards */}
        <div>
          <div style={{fontSize:13,fontWeight:500,color:"var(--text)",marginBottom:10}}>Tomorrow's plan</div>
          {plans&&Object.keys(plans).filter(k=>k!=="recommended").length>0?(
            <div style={{display:"flex",flexDirection:"column",gap:10}}>
              {["recovery","comfortable","challenge"].map(mk=>(
                <ModeCard key={mk} plan={plans[mk]} isActive={activeMode===mk} isRecommended={recommended_mode===mk} accent={accents[mk]} onClick={()=>setSelectedMode(mk)}/>
              ))}
            </div>
          ):(
            <p style={{fontSize:12,color:"var(--faint)"}}>Log more entries to unlock recommendations.</p>
          )}
        </div>
      </div>
    </div>
  )
}