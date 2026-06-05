import React, { useEffect, useState } from 'react'
import { AppShell } from '../components/Layout'
import { Card, CardTitle, CardHeader, Btn, Badge, AlertBox } from '../components/UI'
import { api } from '../services/api'
import { useAuth } from '../context/AuthContext'

export default function UsersPage() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  // Confirmation Dialog States
  const [showConfirm, setShowConfirm] = useState(false)
  const [confirmType, setConfirmType] = useState<'deactivate' | 'reset' | 'role' | null>(null)
  const [confirmTargetUser, setConfirmTargetUser] = useState<any>(null)
  const [confirmData, setConfirmData] = useState<any>(null)

  // Form states for new user
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('Investigator')
  const [department, setDepartment] = useState('Forensics')
  const [badgeNumber, setBadgeNumber] = useState('')
  const [clearanceLevel, setClearanceLevel] = useState(1)
  const [creating, setCreating] = useState(false)

  const fetchUsers = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.getUsers()
      setUsers(res.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch users')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
  }, [])

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!fullName || !email || !password || !badgeNumber) {
      setError('Please fill in all required fields.')
      return
    }
    setCreating(true)
    setError('')
    setSuccess('')
    try {
      await api.createUserAdmin({
        email,
        password,
        full_name: fullName,
        role,
        department,
        badge_number: badgeNumber,
        clearance_level: Number(clearanceLevel)
      })
      setSuccess('User created successfully.')
      setFullName('')
      setEmail('')
      setPassword('')
      setBadgeNumber('')
      setClearanceLevel(1)
      fetchUsers()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create user')
    } finally {
      setCreating(false)
    }
  }

  const handleToggleActive = async (user: any) => {
    setError('')
    setSuccess('')
    if (user.id === currentUser?.id) {
      setError("Cannot deactivate your own administrative account.")
      return
    }
    if (user.role === 'Admin' && user.is_active) {
      const activeAdminsCount = users.filter(u => u.role === 'Admin' && u.is_active).length
      if (activeAdminsCount <= 1) {
        setError("Cannot modify the last active administrator account.")
        return
      }
    }
    try {
      const nextActive = !user.is_active
      await api.updateUserAdmin(user.id, { is_active: nextActive })
      setSuccess(`User ${user.full_name} has been ${nextActive ? 'activated' : 'deactivated'}.`)
      fetchUsers()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update user status')
    }
  }

  const handleChangeRole = async (user: any, newRole: string) => {
    setError('')
    setSuccess('')
    if (user.id === currentUser?.id) {
      setError("Cannot modify your own role.")
      return
    }
    if (user.role === 'Admin' && user.is_active && newRole !== 'Admin') {
      const activeAdminsCount = users.filter(u => u.role === 'Admin' && u.is_active).length
      if (activeAdminsCount <= 1) {
        setError("Cannot modify the last active administrator account.")
        return
      }
    }
    try {
      await api.updateUserAdmin(user.id, { role: newRole })
      setSuccess(`User ${user.full_name} role updated to ${newRole}.`)
      fetchUsers()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update user role')
    }
  }

  const handleResetAccess = async (user: any) => {
    setError('')
    setSuccess('')
    if (user.id === currentUser?.id) {
      setError("Cannot reset access for your own administrative account.")
      return
    }
    try {
      const res = await api.resetAccess(user.id)
      setSuccess(res.message || 'Password recovery request generated. User must verify identity and create a new password.')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset access.')
    }
  }

  const handleToggleActiveClick = (user: any) => {
    if (user.is_active) {
      setConfirmType('deactivate')
      setConfirmTargetUser(user)
      setShowConfirm(true)
    } else {
      handleToggleActive(user)
    }
  }

  const handleChangeRoleClick = (user: any, nextRole: string) => {
    setConfirmType('role')
    setConfirmTargetUser(user)
    setConfirmData(nextRole)
    setShowConfirm(true)
  }

  const handleResetAccessClick = (user: any) => {
    setConfirmType('reset')
    setConfirmTargetUser(user)
    setShowConfirm(true)
  }

  const formatLastLogin = (ts: string | null) => {
    if (!ts) return 'Never Logged In'
    try {
      const date = new Date(ts)
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
      const day = String(date.getDate()).padStart(2, '0')
      const month = months[date.getMonth()]
      const year = date.getFullYear()
      const hours = String(date.getHours()).padStart(2, '0')
      const minutes = String(date.getMinutes()).padStart(2, '0')
      const formattedDate = `${day} ${month} ${year}, ${hours}:${minutes}`
      
      const now = new Date()
      const diffMs = now.getTime() - date.getTime()
      const diffMins = Math.floor(diffMs / (60 * 1000))
      const diffHours = Math.floor(diffMs / (60 * 60 * 1000))
      const diffDays = Math.floor(diffMs / (24 * 60 * 60 * 1000))
      
      let relativeStr = ''
      if (diffMs < 0 || diffMins < 1) {
        relativeStr = 'just now'
      } else if (diffMins < 60) {
        relativeStr = `${diffMins} min${diffMins > 1 ? 's' : ''} ago`
      } else if (diffHours < 24) {
        relativeStr = `${diffHours} hr${diffHours > 1 ? 's' : ''} ago`
      } else {
        relativeStr = `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
      }
      
      return `${formattedDate} (${relativeStr})`
    } catch {
      return ts
    }
  }

  // Filter and sort users list
  const filteredUsers = users.filter((u) => {
    if (!searchQuery) return true
    const q = searchQuery.toLowerCase()
    return (
      (u.full_name || '').toLowerCase().includes(q) ||
      (u.email || '').toLowerCase().includes(q) ||
      (u.badge_number || '').toLowerCase().includes(q)
    )
  })

  const sortedAndFilteredUsers = [...filteredUsers]
    .filter((u) => u.id !== currentUser?.id)
    .sort((a, b) => {
      const aIsAdmin = a.role === 'Admin' ? 1 : 0
      const bIsAdmin = b.role === 'Admin' ? 1 : 0
      if (aIsAdmin !== bIsAdmin) return bIsAdmin - aIsAdmin
      
      return (a.full_name || '').localeCompare(b.full_name || '')
    })

  return (
    <AppShell title="User Management">
      <div style={{ display: 'grid', gridTemplateColumns: '7fr 3fr', gap: '16px', alignItems: 'start' }}>
        {/* Left Column: Users List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Current Logged-In Admin Card */}
          {currentUser && (
            <Card>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid var(--border)', marginBottom: '12px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.8px' }}>Current Logged-In Admin</span>
                <span style={{
                  background: 'var(--blue-bg)',
                  border: '1px solid var(--blue)',
                  color: 'var(--blue)',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontSize: '9px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '.4px'
                }}>Current Account</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 16px 16px 16px' }}>
                <div>
                  <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text)' }}>{currentUser.full_name || currentUser.name || 'Amisha'}</div>
                  <div style={{ fontSize: '13px', color: 'var(--text2)', marginTop: '4px' }}>{currentUser.email}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text3)', marginTop: '4px', fontFamily: 'var(--mono)' }}>Badge: {currentUser.badge_number || currentUser.badge_id || 'BDG-ADMIN'} · Dept: {currentUser.department || 'Administration'}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.4px' }}>Access Role</div>
                  <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--blue)', marginTop: '4px' }}>{currentUser.role}</div>
                </div>
              </div>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Other Users</CardTitle>
              <span style={{ fontSize: '11px', color: 'var(--text3)' }}>{sortedAndFilteredUsers.length} total users</span>
            </CardHeader>

          {/* Search Box */}
          <div style={{ padding: '0 12px 12px 12px', borderBottom: '1px solid var(--border)', marginBottom: '12px' }}>
            <input
              type="text"
              placeholder="Search Officer..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                background: 'var(--bg3)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--r)',
                padding: '8px 12px',
                fontSize: '13px',
                color: 'var(--text)',
                fontFamily: 'var(--font)',
                outline: 'none'
              }}
            />
          </div>

          {error && <div style={{ marginBottom: '12px', padding: '0 12px' }}><AlertBox type="error">{error}</AlertBox></div>}
          {success && <div style={{ marginBottom: '12px', padding: '0 12px' }}><AlertBox type="success">{success}</AlertBox></div>}

          {loading ? (
            <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text3)' }}>Loading users...</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['Officer Name', 'Email', 'Role', 'Department', 'Badge ID', 'Status', 'Last Login', 'Actions'].map((h) => (
                      <th key={h} style={{ textAlign: 'left', padding: '10px 12px', color: 'var(--text3)', fontWeight: 500, fontSize: '11px' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedAndFilteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={8} style={{ padding: '24px', textAlign: 'center', color: 'var(--text3)' }}>No users found</td>
                    </tr>
                  ) : (
                    sortedAndFilteredUsers.map((u) => {
                      const isSelf = u.id === currentUser?.id
                      return (
                        <tr key={u.id} style={{ borderBottom: '1px solid var(--border)' }} onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }} onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}>
                          <td style={{ padding: '10px 12px', fontWeight: 600, color: 'var(--text)' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              {u.full_name}
                              {isSelf && (
                                <span style={{
                                  background: 'var(--blue-bg)',
                                  border: '1px solid var(--blue)',
                                  color: 'var(--blue)',
                                  padding: '1px 6px',
                                  borderRadius: '4px',
                                  fontSize: '9px',
                                  fontWeight: 700,
                                  textTransform: 'uppercase',
                                  letterSpacing: '.4px'
                                }}>CURRENT ACCOUNT</span>
                              )}
                            </div>
                          </td>
                          <td style={{ padding: '10px 12px', color: 'var(--text2)' }}>{u.email}</td>
                          <td style={{ padding: '10px 12px' }}>
                            <select
                              value={u.role}
                              disabled={isSelf}
                              onChange={(e) => handleChangeRoleClick(u, e.target.value)}
                              style={{
                                background: 'var(--bg3)',
                                border: '1px solid var(--border)',
                                borderRadius: '4px',
                                padding: '3px 6px',
                                fontSize: '11px',
                                color: 'var(--text)',
                                fontFamily: 'var(--font)',
                                outline: 'none',
                                opacity: isSelf ? 0.6 : 1,
                                cursor: isSelf ? 'not-allowed' : 'pointer'
                              }}
                            >
                              {['Admin', 'Investigator'].map((r) => (
                                <option key={r} value={r}>{r}</option>
                              ))}
                            </select>
                          </td>
                          <td style={{ padding: '10px 12px', color: 'var(--text2)' }}>{u.department}</td>
                          <td style={{ padding: '10px 12px', fontFamily: 'var(--mono)', color: 'var(--text3)' }}>{u.badge_number || 'N/A'}</td>
                          <td style={{ padding: '10px 12px' }}>
                            <Badge label={u.is_active ? 'Active' : 'Inactive'} />
                          </td>
                          <td style={{ padding: '10px 12px', fontFamily: 'var(--mono)', color: 'var(--text3)', fontSize: '11px' }}>
                            {formatLastLogin(u.last_login)}
                          </td>
                          <td style={{ padding: '10px 12px' }}>
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <Btn
                                size="xs"
                                variant={u.is_active ? 'default' : 'primary'}
                                disabled={isSelf}
                                onClick={() => handleToggleActiveClick(u)}
                              >
                                {u.is_active ? 'Deactivate' : 'Activate'}
                              </Btn>
                              <Btn
                                size="xs"
                                disabled={isSelf}
                                onClick={() => handleResetAccessClick(u)}
                              >
                                Reset Access
                              </Btn>
                            </div>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

        {/* Right Column: Register User Form */}
        <Card>
          <CardTitle>Register New Officer</CardTitle>
          <form onSubmit={handleCreateUser} style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '10px' }}>
            <div>
              <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Full Name *</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. Officer Ancilla Dsouza"
                required
                style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
              />
            </div>

            <div>
              <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Email Address *</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="officer@secureaudits.gov"
                required
                style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
              />
            </div>

            <div>
              <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Temporary Password *</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Role</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
                >
                  {['Investigator', 'Admin'].map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Clearance Lvl</label>
                <select
                  value={clearanceLevel}
                  onChange={(e) => setClearanceLevel(Number(e.target.value))}
                  style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
                >
                  {[1, 2, 3, 4, 5].map((lvl) => (
                    <option key={lvl} value={lvl}>Lvl {lvl}</option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Department</label>
                <input
                  type="text"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  placeholder="e.g. Forensics"
                  style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Badge Number *</label>
                <input
                  type="text"
                  value={badgeNumber}
                  onChange={(e) => setBadgeNumber(e.target.value)}
                  placeholder="e.g. BDG-7749"
                  required
                  style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
                />
              </div>
            </div>

            <Btn type="submit" variant="primary" full loading={creating} style={{ marginTop: '6px' }}>
              Register Officer
            </Btn>
          </form>
        </Card>
      </div>

      {showConfirm && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(5, 7, 10, 0.85)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          backdropFilter: 'blur(4px)'
        }}>
          <div style={{
            background: 'var(--bg2)',
            border: '1.5px solid var(--border2)',
            borderRadius: 'var(--r3)',
            padding: '24px 28px',
            width: '420px',
            maxWidth: '90%',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)'
          }}>
            {confirmType === 'deactivate' && (
              <>
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--red)', marginBottom: '8px', fontFamily: 'var(--font)' }}>Deactivate Officer?</h3>
                <p style={{ fontSize: '13px', color: 'var(--text2)', marginBottom: '20px', lineHeight: 1.5 }}>
                  This will immediately block system access.
                </p>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                  <Btn size="sm" variant="default" onClick={() => { setShowConfirm(false); setConfirmTargetUser(null); setConfirmType(null); }}>Cancel</Btn>
                  <Btn size="sm" variant="primary" style={{ background: 'var(--red)', border: '1px solid var(--red)' }} onClick={() => {
                    handleToggleActive(confirmTargetUser);
                    setShowConfirm(false);
                    setConfirmTargetUser(null);
                    setConfirmType(null);
                  }}>Deactivate</Btn>
                </div>
              </>
            )}

            {confirmType === 'reset' && (
              <>
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--amber)', marginBottom: '8px', fontFamily: 'var(--font)' }}>Reset Officer Access?</h3>
                <p style={{ fontSize: '13px', color: 'var(--text2)', marginBottom: '20px', lineHeight: 1.5 }}>
                  The officer will be required to create a new password during their next login.
                </p>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                  <Btn size="sm" variant="default" onClick={() => { setShowConfirm(false); setConfirmTargetUser(null); setConfirmType(null); }}>Cancel</Btn>
                  <Btn size="sm" variant="primary" style={{ background: 'var(--amber)', border: '1px solid var(--amber)', color: '#000' }} onClick={() => {
                    handleResetAccess(confirmTargetUser);
                    setShowConfirm(false);
                    setConfirmTargetUser(null);
                    setConfirmType(null);
                  }}>Reset Access</Btn>
                </div>
              </>
            )}

            {confirmType === 'role' && (
              <>
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--blue)', marginBottom: '8px', fontFamily: 'var(--font)' }}>Change Officer Role?</h3>
                <p style={{ fontSize: '13px', color: 'var(--text2)', marginBottom: '20px', lineHeight: 1.5 }}>
                  Role changes affect permissions after the next login.
                </p>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                  <Btn size="sm" variant="default" onClick={() => { setShowConfirm(false); setConfirmTargetUser(null); setConfirmType(null); setConfirmData(null); }}>Cancel</Btn>
                  <Btn size="sm" variant="primary" onClick={() => {
                    handleChangeRole(confirmTargetUser, confirmData);
                    setShowConfirm(false);
                    setConfirmTargetUser(null);
                    setConfirmType(null);
                    setConfirmData(null);
                  }}>Confirm</Btn>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </AppShell>
  )
}
