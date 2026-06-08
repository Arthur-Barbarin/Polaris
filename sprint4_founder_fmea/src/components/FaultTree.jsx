import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

// Branch identity colors (box borders + connectors)
// Chosen AFTER risk % colors to avoid any overlap
const BRANCH_COLORS = {
  Capital: '#6366f1',  // indigo
  Revenue: '#ec4899',  // pink
  Team:    '#06b6d4',  // cyan  (changed from amber — amber conflicts with orange risk)
  Product: '#a78bfa',  // violet (changed from green — green conflicts with lime risk)
}

// Risk severity spectrum — these are the HERO colors (box percentage text + border on leaves)
// Red → Orange → Dark yellow → Lime (clearly readable, non-overlapping with branch colors)
function riskColor(p) {
  if (p >= 0.70) return '#ef4444'  // red
  if (p >= 0.45) return '#f97316'  // orange
  if (p >= 0.20) return '#eab308'  // yellow — completes green→yellow→orange→red spectrum
  return '#a3e635'                 // lime
}

function buildTreeData(leaves, branchProbs) {
  return {
    id: 'top',
    name: 'FAIL TO REACH\nNEXT MILESTONE',
    prob: branchProbs.top,
    isTop: true,
    children: [
      {
        id: 'capital', name: 'CAPITAL\nFAILURE', prob: branchProbs.capital, branch: 'Capital',
        children: [
          { id: 'C1', name: 'Runway\nExhaustion',     prob: leaves.C1, branch: 'Capital', leaf: true },
          { id: 'C2', name: 'Fundraise\nDelayed',      prob: leaves.C2, branch: 'Capital', leaf: true },
        ]
      },
      {
        id: 'revenue', name: 'REVENUE\nFAILURE', prob: branchProbs.revenue, branch: 'Revenue',
        children: [
          { id: 'R1', name: 'Poor\nRetention',         prob: leaves.R1, branch: 'Revenue', leaf: true },
          { id: 'R2', name: 'Growth\nStall',            prob: leaves.R2, branch: 'Revenue', leaf: true },
          { id: 'R3', name: 'Customer\nConc.',          prob: leaves.R3, branch: 'Revenue', leaf: true },
        ]
      },
      {
        id: 'team', name: 'TEAM\nFAILURE', prob: branchProbs.team, branch: 'Team',
        children: [
          { id: 'T1', name: 'Key Person\nRisk',         prob: leaves.T1, branch: 'Team', leaf: true },
          { id: 'T2', name: 'Hiring\nBottleneck',       prob: leaves.T2, branch: 'Team', leaf: true },
        ]
      },
      {
        id: 'product', name: 'PRODUCT\nFAILURE', prob: branchProbs.product, branch: 'Product',
        children: [
          { id: 'P1', name: 'Technical\nRisk',          prob: leaves.P1, branch: 'Product', leaf: true },
          { id: 'P2', name: 'Market\nMisfit',           prob: leaves.P2, branch: 'Product', leaf: true },
        ]
      },
    ]
  }
}

export default function FaultTree({ leaves, branchProbs }) {
  const svgRef = useRef(null)

  useEffect(() => {
    if (!leaves || !branchProbs) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    // Layout
    const root = d3.hierarchy(buildTreeData(leaves, branchProbs))
    d3.tree().nodeSize([158, 195])(root)

    const allNodes = root.descendants()
    const PAD_X = 92, PAD_Y = 64
    const x0 = Math.min(...allNodes.map(n => n.x)) - PAD_X
    const x1 = Math.max(...allNodes.map(n => n.x)) + PAD_X
    const y0 = Math.min(...allNodes.map(n => n.y)) - PAD_Y
    const y1 = Math.max(...allNodes.map(n => n.y)) + PAD_Y

    // viewBox = exact content bounds → SVG scales to fit any container, no clipping, no scroll
    svg
      .attr('viewBox', `${x0} ${y0} ${x1 - x0} ${y1 - y0}`)
      .attr('preserveAspectRatio', 'xMidYMid meet')
    // width/height set via CSS (100% / auto) — no JS measurement needed → no shift bug

    const g = svg.append('g')

    // Links
    g.selectAll('path.link')
      .data(root.links())
      .join('path')
      .attr('class', 'link')
      .attr('fill', 'none')
      .attr('stroke', d => {
        const branch = d.target.data.branch
        return branch ? BRANCH_COLORS[branch] + '55' : '#ffffff22'
      })
      .attr('stroke-width', 1.5)
      .attr('d', d3.linkVertical().x(d => d.x).y(d => d.y))

    // Nodes
    const node = g.selectAll('g.node')
      .data(root.descendants())
      .join('g')
      .attr('class', 'node')
      .attr('transform', d => `translate(${d.x},${d.y})`)

    node.each(function(d) {
      const sel   = d3.select(this)
      const isTop  = d.data.isTop
      const isLeaf = d.data.leaf
      const color  = d.data.branch ? BRANCH_COLORS[d.data.branch] : '#6366f1'
      const risk   = riskColor(d.data.prob)

      const bw = isTop ? 176 : isLeaf ? 134 : 150
      const bh = isTop ? 70  : isLeaf ? 68  : 66

      // Box
      sel.append('rect')
        .attr('x', -bw / 2).attr('y', -bh / 2)
        .attr('width', bw).attr('height', bh)
        .attr('rx', isLeaf ? 7 : 9)
        .attr('fill', isTop ? '#1a1f35' : isLeaf ? '#111520' : '#181d2a')
        .attr('stroke', isTop ? '#6366f1' : isLeaf ? risk : color)
        .attr('stroke-width', isTop ? 2 : 1.5)

      // OR gate badge on non-leaf nodes
      if (!isLeaf) {
        sel.append('circle')
          .attr('cx', 0).attr('cy', bh / 2 + 10)
          .attr('r', 9)
          .attr('fill', '#111520')
          .attr('stroke', isTop ? '#6366f1' : color)
          .attr('stroke-width', 1.5)
        sel.append('text')
          .attr('x', 0).attr('y', bh / 2 + 14)
          .attr('text-anchor', 'middle')
          .attr('fill', isTop ? '#818cf8' : color)
          .attr('font-size', '8px')
          .attr('font-family', 'JetBrains Mono, monospace')
          .attr('font-weight', '700')
          .text('OR')
      }

      // ── Text layout ──────────────────────────────────────────
      // All node names have exactly 2 lines (name always contains '\n').
      // Standard SVG baseline positioning (NO dominant-baseline override).
      // Hardcoded y positions centered in the box for 2-line + probability layout.
      //
      // For non-top nodes (2 lines + prob below):
      //   line1 baseline at -14, line2 at 0, prob at +17
      //   Visual span: [-14-9, 17+3] = [-23, 20] → centered in bh=68 ✓
      //
      // For top node (2 lines, no prob):
      //   line1 at -7, line2 at +7  → centered in bh=70 ✓

      const lines = d.data.name.split('\n')
      const LABEL_FS = isTop ? 12.5 : isLeaf ? 11.5 : 12
      const PROB_FS  = 14

      const yL1   = isTop ? -7 : -14    // first label line baseline
      const yL2   = isTop ?  7 :   0    // second label line baseline
      const yProb = 17                  // probability baseline (non-top only)

      const yLines = [yL1, yL2]
      lines.forEach((line, i) => {
        sel.append('text')
          .attr('x', 0)
          .attr('y', yLines[i])
          .attr('text-anchor', 'middle')
          .attr('fill', isTop ? '#e2e8f0' : isLeaf ? '#b0bec5' : '#cbd5e1')
          .attr('font-size', `${LABEL_FS}px`)
          .attr('font-weight', isTop ? '700' : isLeaf ? '500' : '600')
          .attr('font-family', 'Inter, sans-serif')
          .text(line)
      })

      // Probability — skip top node
      if (!isTop) {
        const pct = Math.round(d.data.prob * 100)
        sel.append('text')
          .attr('x', 0)
          .attr('y', yProb)
          .attr('text-anchor', 'middle')
          .attr('fill', risk)
          .attr('font-size', `${PROB_FS}px`)
          .attr('font-weight', '700')
          .attr('font-family', 'JetBrains Mono, monospace')
          .text(`${pct}%`)
      }
    })

  }, [leaves, branchProbs])

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 12,
      padding: '16px 12px 10px',
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
        <span style={{
          fontSize: 11, color: 'var(--muted)',
          textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600,
        }}>
          Failure Mode Visualization
        </span>
        <span style={{ fontSize: 11, color: '#64748b' }}>
          — leaf & branch risk levels · OR-gate structure · separate from Resilience Index scoring
        </span>
      </div>

      {/* width: 100% + height: auto → scales to fit container.
          min-height ensures the tree is always readable even on very wide screens. */}
      <svg
        ref={svgRef}
        style={{ display: 'block', width: '100%', height: 'auto', minHeight: 380 }}
      />

      {/* Risk level legend only — branch names already shown on the boxes */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
        gap: 16, flexWrap: 'wrap',
        paddingTop: 8, borderTop: '1px solid var(--border)', marginTop: 4,
      }}>
        <span style={{ fontSize: 11, color: '#64748b' }}>Box border = risk level:</span>
        {[
          { color: '#ef4444', label: '≥70% Critical' },
          { color: '#f97316', label: '45–70% High' },
          { color: '#eab308', label: '20–45% Moderate' },
          { color: '#a3e635', label: '<20% Low' },
        ].map(({ color, label }) => (
          <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: color, display: 'inline-block', flexShrink: 0 }} />
            <span style={{ fontSize: 11, color }}>{label}</span>
          </span>
        ))}
      </div>
    </div>
  )
}
