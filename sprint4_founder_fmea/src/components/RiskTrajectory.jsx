import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

const BRANCH_COLORS = {
  capital: '#6366f1',
  revenue: '#ec4899',
  team:    '#06b6d4',
  product: '#a78bfa',
}

function resilienceColor(r) {
  if (r <= 0.20) return '#ef4444'
  if (r <= 0.35) return '#f97316'
  if (r <= 0.50) return '#eab308'
  return '#a3e635'
}

export default function RiskTrajectory({ trajectory, baseInputs }) {
  const svgRef = useRef(null)

  useEffect(() => {
    if (!trajectory || !trajectory.points.length) return

    const { points, milestones } = trajectory
    const W = 900, H = 320
    const M = { top: 24, right: 72, bottom: 40, left: 48 }
    const IW = W - M.left - M.right
    const IH = H - M.top - M.bottom

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()
    svg.attr('viewBox', `0 0 ${W} ${H}`)
       .attr('width', '100%').attr('height', 'auto')
       .attr('preserveAspectRatio', 'xMidYMid meet')

    const g = svg.append('g').attr('transform', `translate(${M.left},${M.top})`)

    const xScale = d3.scaleLinear().domain([0, points.length - 1]).range([0, IW])
    const yScale = d3.scaleLinear().domain([0, 1]).range([IH, 0])

    // ── Background risk zones ─────────────────────────────────
    const zones = [
      { y0: 0,    y1: 0.20, color: '#ef444408' },
      { y0: 0.20, y1: 0.35, color: '#f9731608' },
      { y0: 0.35, y1: 0.50, color: '#eab30808' },
      { y0: 0.50, y1: 1.00, color: '#a3e63508' },
    ]
    zones.forEach(z => {
      g.append('rect')
        .attr('x', 0).attr('width', IW)
        .attr('y', yScale(z.y1))
        .attr('height', yScale(z.y0) - yScale(z.y1))
        .attr('fill', z.color)
    })

    // Zone labels on right edge
    const zoneLabels = [
      { y: 0.10, label: 'Critical', color: '#ef444466' },
      { y: 0.275, label: 'High',    color: '#f9731666' },
      { y: 0.425, label: 'Moderate', color: '#eab30866' },
      { y: 0.70, label: 'Low',      color: '#a3e63566' },
    ]
    zoneLabels.forEach(({ y, label, color }) => {
      g.append('text')
        .attr('x', IW + 4).attr('y', yScale(y))
        .attr('dominant-baseline', 'middle')
        .attr('fill', color).attr('font-size', '9px')
        .attr('font-family', 'Inter, sans-serif')
        .text(label)
    })

    // ── Grid lines ────────────────────────────────────────────
    g.append('g')
      .selectAll('line.grid')
      .data([0.25, 0.50, 0.75])
      .join('line')
      .attr('x1', 0).attr('x2', IW)
      .attr('y1', d => yScale(d)).attr('y2', d => yScale(d))
      .attr('stroke', '#ffffff08').attr('stroke-dasharray', '3,4')

    // ── Health lines: (1 - failure_prob), so higher = healthier ──
    ;[
      { key: 'capital', color: BRANCH_COLORS.capital },
      { key: 'revenue', color: BRANCH_COLORS.revenue },
    ].forEach(({ key, color }) => {
      const line = d3.line()
        .x((_, i) => xScale(i))
        .y(d => yScale(1 - d[key]))   // invert: health = 1 - failure
        .curve(d3.curveMonotoneX)

      g.append('path')
        .datum(points)
        .attr('fill', 'none')
        .attr('stroke', color + '99')
        .attr('stroke-width', 1.5)
        .attr('stroke-dasharray', '4,3')
        .attr('d', line)
    })

    // ── Resilience line — single smooth path, color tracks current level ──
    const resColor = resilienceColor(points[0].resilience)
    const resLine = d3.line()
      .x((_, i) => xScale(i))
      .y(d => yScale(d.resilience))
      .curve(d3.curveMonotoneX)

    g.append('path')
      .datum(points)
      .attr('fill', 'none')
      .attr('stroke', resColor)
      .attr('stroke-width', 2.5)
      .attr('stroke-linecap', 'round')
      .attr('d', resLine)

    // ── Milestone markers ─────────────────────────────────────
    const milestoneList = [
      { month: milestones.capitalCritical,    label: 'Capital critical',    color: '#6366f1' },
      { month: milestones.runwayExhausted,    label: 'Runway exhausted',    color: '#ef4444' },
      { month: milestones.resilienceCritical, label: 'Resilience critical', color: '#f97316' },
    ].filter(m => m.month !== null && m.month > 0 && m.month <= points.length - 1)

    // Deduplicate by month (only show first milestone per month)
    const seen = new Set()
    milestoneList.filter(m => {
      if (seen.has(m.month)) return false
      seen.add(m.month)
      return true
    }).forEach((m, idx) => {
      const x = xScale(m.month)
      const resAtM = points[m.month]?.resilience ?? 0

      g.append('line')
        .attr('x1', x).attr('x2', x)
        .attr('y1', 0).attr('y2', IH)
        .attr('stroke', m.color + '66')
        .attr('stroke-width', 1)
        .attr('stroke-dasharray', '4,3')

      g.append('circle')
        .attr('cx', x).attr('cy', yScale(resAtM))
        .attr('r', 4)
        .attr('fill', m.color)
        .attr('stroke', '#0a0c10').attr('stroke-width', 1.5)

      // Label above
      g.append('text')
        .attr('x', x).attr('y', -6 - idx * 12)
        .attr('text-anchor', 'middle')
        .attr('fill', m.color)
        .attr('font-size', '9px')
        .attr('font-family', 'Inter, sans-serif')
        .text(`M${m.month}: ${m.label}`)
    })

    // ── Today marker (month 0) ────────────────────────────────
    const r0 = points[0].resilience
    g.append('circle')
      .attr('cx', 0).attr('cy', yScale(r0))
      .attr('r', 5)
      .attr('fill', resilienceColor(r0))
      .attr('stroke', '#0a0c10').attr('stroke-width', 2)

    g.append('text')
      .attr('x', 4).attr('y', yScale(r0) - 8)
      .attr('fill', '#94a3b8').attr('font-size', '9px')
      .attr('font-family', 'Inter, sans-serif')
      .text('Today')

    // ── Axes ──────────────────────────────────────────────────
    // X axis
    const xAxis = d3.axisBottom(xScale)
      .ticks(Math.min(points.length - 1, 9))
      .tickFormat(d => `M${d}`)
    g.append('g').attr('transform', `translate(0,${IH})`).call(xAxis)
      .call(ax => {
        ax.select('.domain').attr('stroke', '#1e293b')
        ax.selectAll('text').attr('fill', '#64748b').attr('font-size', '10px').attr('font-family', 'Inter, sans-serif')
        ax.selectAll('line').attr('stroke', '#1e293b')
      })

    // Y axis
    const yAxis = d3.axisLeft(yScale)
      .ticks(5).tickFormat(d => `${Math.round(d * 100)}%`)
    g.append('g').call(yAxis)
      .call(ax => {
        ax.select('.domain').attr('stroke', '#1e293b')
        ax.selectAll('text').attr('fill', '#64748b').attr('font-size', '10px').attr('font-family', 'Inter, sans-serif')
        ax.selectAll('line').attr('stroke', '#1e293b')
      })

  }, [trajectory])

  if (!trajectory) return null

  const { points, milestones } = trajectory
  const lastPoint = points[points.length - 1]
  const rawNetBurn = baseInputs.monthly_burn - (baseInputs.current_mrr || 0)
  const isProfitable = rawNetBurn <= 0
  // Use the trajectory-derived exhaustion month so card and chart marker always agree
  const runwayExhaustedMonth = milestones.runwayExhausted  // null = lasts beyond 18 mo
  const runwayValue = isProfitable
    ? 'Profitable'
    : runwayExhaustedMonth
      ? `Month ${runwayExhaustedMonth}`
      : '> 18 mo'
  const runwayColor = isProfitable || !runwayExhaustedMonth
    ? '#a3e635'
    : runwayExhaustedMonth < 9 ? '#ef4444' : runwayExhaustedMonth < 15 ? '#f97316' : '#a3e635'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Summary stats — top row: dynamic metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        {[
          {
            label: 'Runway exhausted',
            value: runwayValue,
            sub: isProfitable
              ? `MRR covers burn (+$${Math.round(-rawNetBurn/1000)}k/mo)`
              : runwayExhaustedMonth
                ? 'cash hits zero — matches chart marker'
                : 'cash lasts beyond chart range',
            color: runwayColor,
          },
          {
            label: `Resilience at M${points.length - 1}`,
            value: `${Math.round(lastPoint.resilience * 100)}%`,
            sub: `from ${Math.round(points[0].resilience * 100)}% today`,
            color: resilienceColor(lastPoint.resilience),
          },
          {
            label: 'Capital critical at',
            value: milestones.capitalCritical ? `Month ${milestones.capitalCritical}` : 'Not in range',
            sub: 'when capital failure ≥ 85%',
            color: milestones.capitalCritical ? '#6366f1' : '#64748b',
          },
        ].map(({ label, value, sub, color }) => (
          <div key={label} style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            padding: '14px 16px',
          }}>
            <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
              {label}
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--mono)', color, lineHeight: 1 }}>
              {value}
            </div>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>{sub}</div>
          </div>
        ))}
      </div>

      {/* Static branch risks — constant over time, shown as context not chart lines */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12,
      }}>
        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 10, padding: '12px 16px',
          gridColumn: '1 / -1',
        }}>
          <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10, fontWeight: 600 }}>
            Fixed risk factors — team & product (unchanged over 18 months)
          </div>
          <div style={{ display: 'flex', gap: 32 }}>
            {[
              { key: 'team',    color: BRANCH_COLORS.team },
              { key: 'product', color: BRANCH_COLORS.product },
            ].map(({ key, color }) => {
              const val = points[0][key]
              const riskLabel = val >= 0.85 ? 'Critical' : val >= 0.65 ? 'High' : val >= 0.45 ? 'Moderate' : 'Low'
              const riskColor = val >= 0.85 ? '#ef4444' : val >= 0.65 ? '#f97316' : val >= 0.45 ? '#eab308' : '#a3e635'
              return (
                <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
                  <span style={{ fontSize: 12, color: '#94a3b8', textTransform: 'capitalize' }}>{key}</span>
                  <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--mono)', color: riskColor }}>
                    {Math.round(val * 100)}%
                  </span>
                  <span style={{ fontSize: 11, color: riskColor, opacity: 0.7 }}>({riskLabel})</span>
                </div>
              )
            })}
            <div style={{ marginLeft: 'auto', fontSize: 11, color: '#334155', fontStyle: 'italic', alignSelf: 'center' }}>
              Adjust inputs left to model improvements
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '16px 16px 8px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div>
            <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>
              18-Month Health Outlook
            </span>
            <span style={{ fontSize: 11, color: '#64748b', marginLeft: 10 }}>
              — all lines: higher = healthier
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <span style={{ fontSize: 11, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6 }}>
              <svg width="20" height="10"><line x1="0" y1="5" x2="20" y2="5" stroke="#e2e8f0" strokeWidth="2.5" strokeLinecap="round"/></svg>
              Resilience ↑ safer
            </span>
            {[
              { key: 'capital', label: 'Capital health' },
              { key: 'revenue', label: 'Revenue health' },
            ].map(({ key, label }) => (
              <span key={key} style={{ fontSize: 11, color: BRANCH_COLORS[key], display: 'flex', alignItems: 'center', gap: 6 }}>
                <svg width="20" height="10"><line x1="0" y1="5" x2="20" y2="5" stroke={BRANCH_COLORS[key]} strokeWidth="1.5" strokeDasharray="4,3" strokeLinecap="round"/></svg>
                {label}
              </span>
            ))}
          </div>
        </div>

        <svg ref={svgRef} style={{ display: 'block', width: '100%', height: 'auto' }} />

        <div style={{ fontSize: 10, color: '#334155', textAlign: 'center', marginTop: 4 }}>
          Dynamic: cash depletes at net burn; MRR compounds monthly; customer concentration shrinks as MRR grows. Team & product risks fixed.
        </div>
      </div>
    </div>
  )
}
