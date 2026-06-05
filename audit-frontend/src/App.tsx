
import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import AuthPage from './pages/AuthPage'
import Dashboard from './pages/Dashboard'
import Cases from './pages/Cases'
import CreateCase from './pages/CreateCase'
import CaseDetail from './pages/CaseDetail'
import {
  EvidencePage, DetectionPage, BNSPage, OCRPage,
  AuditPage, SettingsPage, PersonalPage,
  PlaceholderPage, GraphPage
} from './pages/OtherPages'
import { ProfilePage } from './pages/ProfilePage'
import UsersPage from './pages/UsersPage'
import ForcedPasswordPage from './pages/ForcedPasswordPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, user } = useAuth()
  if (isLoading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg)' }}>
      <div style={{ width: '32px', height: '32px', borderRadius: '50%', border: '2px solid var(--border2)', borderTopColor: 'var(--blue)', animation: 'spin 0.8s linear infinite' }} />
    </div>
  )
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (user?.must_change_password) {
    return <Navigate to="/forced-password-change" replace />
  }
  return <>{children}</>
}

function ForcedPasswordRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, user } = useAuth()
  if (isLoading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg)' }}>
      <div style={{ width: '32px', height: '32px', borderRadius: '50%', border: '2px solid var(--border2)', borderTopColor: 'var(--blue)', animation: 'spin 0.8s linear infinite' }} />
    </div>
  )
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (!user?.must_change_password) return <Navigate to="/dashboard" replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="/cases" element={<ProtectedRoute><Cases /></ProtectedRoute>} />
      <Route path="/cases/new" element={<ProtectedRoute><CreateCase /></ProtectedRoute>} />
      <Route path="/cases/:id" element={<ProtectedRoute><CaseDetail /></ProtectedRoute>} />
      <Route path="/personal" element={<ProtectedRoute><PersonalPage /></ProtectedRoute>} />
      <Route path="/evidence" element={<ProtectedRoute><EvidencePage /></ProtectedRoute>} />
      <Route path="/detection" element={<ProtectedRoute><DetectionPage /></ProtectedRoute>} />
      <Route path="/bns" element={<ProtectedRoute><BNSPage /></ProtectedRoute>} />
      <Route path="/ocr" element={<ProtectedRoute><OCRPage /></ProtectedRoute>} />
      <Route path="/photo3d" element={<ProtectedRoute><PlaceholderPage title="3D Scene Reconstruction" description="COLMAP Structure from Motion pipeline — upload 20+ overlapping crime scene photos to generate a 3D point cloud visualized in Three.js" /></ProtectedRoute>} />
      <Route path="/audio" element={<ProtectedRoute><PlaceholderPage title="Audio Forensics" description="pyAudioAnalysis — ENF authentication, speaker identification, tampering detection. Minimum 10 minutes of audio required for ENF analysis." /></ProtectedRoute>} />
      <Route path="/graph" element={<ProtectedRoute><GraphPage /></ProtectedRoute>} />
      <Route path="/cases/:id/graph" element={<ProtectedRoute><GraphPage /></ProtectedRoute>} />
      <Route path="/audit" element={<ProtectedRoute><AuditPage /></ProtectedRoute>} />
      <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
      <Route path="/users" element={<ProtectedRoute><UsersPage /></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
      <Route path="/forced-password-change" element={<ForcedPasswordRoute><ForcedPasswordPage /></ForcedPasswordRoute>} />

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </ThemeProvider>
  )
}
