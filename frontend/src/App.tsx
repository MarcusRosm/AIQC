import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { Flex, Heading, Text, Badge } from '@radix-ui/themes'
import { ActivityLogIcon, FileTextIcon, GearIcon, HeartIcon } from '@radix-ui/react-icons'
import { Dashboard } from './pages/Dashboard'
import { Reports } from './pages/Reports'
import { ReportDetail } from './pages/ReportDetail'
import { useState, useEffect } from 'react'

function Sidebar() {
  const [health, setHealth] = useState<{ status: string; ollama: boolean; chromadb: boolean } | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then(r => r.json())
      .then(setHealth)
      .catch(() => {})
  }, [])

  return (
    <nav className="sidebar">
      {/* Logo */}
      <Flex direction="column" gap="1" mb="6">
        <Flex align="center" gap="2">
          <div style={{
            width: 32, height: 32,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            borderRadius: 8,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16
          }}>🧬</div>
          <div>
            <Text size="2" weight="bold" style={{ color: '#e2e8f0', lineHeight: 1.2 }}>AI QA</Text>
            <Text size="1" style={{ color: '#64748b', display: 'block', lineHeight: 1.2 }}>Platform</Text>
          </div>
        </Flex>
      </Flex>

      {/* Nav links */}
      <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
        <ActivityLogIcon /> Dashboard
      </NavLink>
      <NavLink to="/reports" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
        <FileTextIcon /> Reports
      </NavLink>

      {/* Health indicator */}
      {health && (
        <div style={{ marginTop: 'auto', paddingTop: 16 }}>
          <Text size="1" style={{ color: '#475569', display: 'block', marginBottom: 8 }}>SERVICES</Text>
          <ServiceRow label="Ollama" ok={health.ollama} />
          <ServiceRow label="ChromaDB" ok={health.chromadb} />
        </div>
      )}
    </nav>
  )
}

function ServiceRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <Flex align="center" justify="between" mb="1" px="1">
      <Text size="1" style={{ color: '#64748b' }}>{label}</Text>
      <div style={{
        width: 8, height: 8, borderRadius: '50%',
        background: ok ? '#10b981' : '#ef4444',
        boxShadow: ok ? '0 0 6px rgba(16,185,129,0.6)' : '0 0 6px rgba(239,68,68,0.6)'
      }} />
    </Flex>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Sidebar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/reports/:runId" element={<ReportDetail />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
