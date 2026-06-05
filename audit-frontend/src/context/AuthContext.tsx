import React, { createContext, useContext, useEffect, useReducer, useCallback } from 'react'
import type { User, AuthState } from '../types'
import { api } from '../services/api'

type Action =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'LOGIN_SUCCESS'; payload: { user: User; token: string } }
  | { type: 'LOGOUT' }
  | { type: 'UPDATE_USER'; payload: User }

function reducer(state: AuthState, action: Action): AuthState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload }
    case 'LOGIN_SUCCESS':
      return { ...state, user: action.payload.user, token: action.payload.token, isAuthenticated: true, isLoading: false }
    case 'LOGOUT':
      return { user: null, token: null, isAuthenticated: false, isLoading: false }
    case 'UPDATE_USER':
      return { ...state, user: action.payload }
    default:
      return state
  }
}

const initialState: AuthState = {
  user: null,
  token: null,
  isLoading: true,
  isAuthenticated: false
}

interface AuthContextType extends AuthState {
  login: (token: string, user: User) => void
  logout: () => void
  updateUser: (user: User) => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)

  useEffect(() => {
    const token = localStorage.getItem('sa_token')
    if (!token) {
      dispatch({ type: 'SET_LOADING', payload: false })
      return
    }
    api.getMe()
      .then((res) => {
        dispatch({ type: 'LOGIN_SUCCESS', payload: { user: res.data as User, token } })
      })
      .catch(() => {
        localStorage.removeItem('sa_token')
        dispatch({ type: 'SET_LOADING', payload: false })
      })
  }, [])

  const login = useCallback((token: string, user: User) => {
    localStorage.setItem('sa_token', token)
    dispatch({ type: 'LOGIN_SUCCESS', payload: { user, token } })
  }, [])

  const logout = useCallback(async () => {
    try { await api.logout() } catch { /* ignore */ }
    localStorage.removeItem('sa_token')
    localStorage.removeItem('sa_session_start')
    dispatch({ type: 'LOGOUT' })
  }, [])

  const updateUser = useCallback((user: User) => {
    dispatch({ type: 'UPDATE_USER', payload: user })
  }, [])

  useEffect(() => {
    if (!state.isAuthenticated) return
    const interval = setInterval(() => {
      if (document.hidden) return
      api.getMe().catch((err) => {
        const status = err.response?.status
        const detail = err.response?.data?.detail || ''
        if (status === 403 && typeof detail === 'string' && detail.toLowerCase().includes('deactivated')) {
          logout()
        }
      })
    }, 10000) // Poll user status every 10 seconds
    return () => clearInterval(interval)
  }, [state.isAuthenticated, logout])

  return (
    <AuthContext.Provider value={{ ...state, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
