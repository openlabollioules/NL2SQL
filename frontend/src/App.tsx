/**
 * Main Application Component
 * Uses React.lazy for code splitting and useCallback/useMemo for optimization
 */
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom"
import { useState, useEffect, useCallback, useMemo, lazy, Suspense } from "react"
import { MainLayout } from "./components/layout/MainLayout"
import { useTheme } from "./hooks/useTheme"
import { useChat } from "./hooks/useChat"
import { useData } from "./hooks/useData"
import { api } from "./services/api"
import type { Message, Session } from "./types"

// Lazy load pages for better initial load time
const ChatPage = lazy(() => import("./pages/ChatPage").then(m => ({ default: m.ChatPage })))
const DataPage = lazy(() => import("./pages/DataPage").then(m => ({ default: m.DataPage })))
const ModelingPage = lazy(() => import("./pages/ModelingPage").then(m => ({ default: m.ModelingPage })))

// Loading fallback component
function PageLoader() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
    </div>
  )
}

function AppContent() {
  const { theme, toggleTheme } = useTheme()

  // Session State
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string>(() => 'session_' + Date.now())
  const [sqlMode, setSqlMode] = useState(false)
  const [input, setInput] = useState('')

  // Hooks
  const { messages, setMessages, sendMessage, agentState, setAgentState } = useChat(sqlMode, currentSessionId)
  const data = useData()

  // Memoized session fetching
  const fetchSessions = useCallback(async () => {
    try {
      const data = await api.getSessions()
      setSessions(data)
    } catch (error) {
      console.error("Error fetching sessions:", error)
    }
  }, [])

  // Memoized session loading
  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const data = await api.getSessionMessages(sessionId)
      // Convert history messages to UI format
      const uiMessages: Message[] = data.map((msg) => {
        if (msg.role === 'assistant' && msg.content.startsWith('{')) {
          try {
            const parsed = JSON.parse(msg.content)
            if (parsed.type === 'data_result') {
              return {
                role: 'assistant' as const,
                content: parsed.summary as string,
                type: 'table' as const,
                tableData: { columns: parsed.columns, data: parsed.data }
              }
            }
            if (parsed.type === 'chart_result') {
              return {
                role: 'assistant' as const,
                content: "Voici le graphique demandé :",
                type: 'chart' as const,
                chartConfig: parsed.config
              }
            }
            if (parsed.type === 'chart_suggestions') {
              return {
                role: 'assistant' as const,
                content: "Voici quelques suggestions de graphiques :",
                type: 'chart_suggestions' as const,
                suggestions: parsed.suggestions
              }
            }
          } catch { /* ignore parse errors */ }
        }
        return {
          role: (msg.role === 'user' ? 'user' : msg.role === 'system' ? 'system' : 'assistant') as Message['role'],
          content: msg.content
        }
      })
      setMessages(uiMessages)
      setCurrentSessionId(sessionId)
      setAgentState(null)
    } catch (error) {
      console.error("Error loading session:", error)
    }
  }, [setMessages, setAgentState])

  // Memoized new session creation
  const createNewSession = useCallback(() => {
    const newId = 'session_' + Date.now()
    setCurrentSessionId(newId)
    setMessages([{ role: 'assistant', content: 'Bonjour ! Je suis votre assistant Data Intelligence. Chargez un fichier CSV pour commencer.' }])
    setAgentState(null)
  }, [setMessages, setAgentState])

  // Memoized session deletion
  const deleteSession = useCallback(async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm("Supprimer cette conversation ?")) return
    try {
      await api.deleteSession(sessionId)
      fetchSessions()
      if (currentSessionId === sessionId) {
        createNewSession()
      }
    } catch (error) {
      console.error("Error deleting session:", error)
    }
  }, [fetchSessions, currentSessionId, createNewSession])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  // Auto-refresh tables when entering data page
  const location = useLocation()
  useEffect(() => {
    if (location.pathname === '/data' || location.pathname === '/modeling') {
      data.fetchTables()
    }
  }, [location.pathname, data.fetchTables])

  // Memoized send handler
  const handleSendWrapper = useCallback(() => {
    if (input.trim()) {
      sendMessage(input)
      setInput('')
    }
  }, [input, sendMessage])

  // Memoized file upload handler
  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setMessages(prev => [...prev, { role: 'user', content: `Chargement du fichier: ${file.name}` }])
    try {
      const res = await api.uploadFile(file)
      setMessages(prev => [...prev, { role: 'assistant', content: res.message }])
      if (data.fetchTables) data.fetchTables()
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Erreur inconnue'
      setMessages(prev => [...prev, { role: 'assistant', content: `Erreur: ${errorMessage}` }])
    }
  }, [setMessages, data.fetchTables])

  // Memoized sidebar props to prevent unnecessary re-renders
  const sidebarProps = useMemo(() => ({
    theme,
    toggleTheme,
    sessions,
    currentSessionId,
    onLoadSession: loadSession,
    onNewSession: createNewSession,
    onDeleteSession: deleteSession,
    tables: data.tables,
    selectedTable: data.selectedTable,
    onSelectTable: data.fetchTableContent,
    onDeleteTable: data.deleteTable,
    onFileUpload: handleFileUpload,
    onRefreshTables: data.fetchTables
  }), [
    theme, toggleTheme, sessions, currentSessionId,
    loadSession, createNewSession, deleteSession,
    data.tables, data.selectedTable, data.fetchTableContent,
    data.deleteTable, data.fetchTables, handleFileUpload
  ])

  // Memoized chat page props
  const chatPageProps = useMemo(() => ({
    messages,
    input,
    setInput,
    handleSend: handleSendWrapper,
    sqlMode,
    setSqlMode,
    agentState
  }), [messages, input, setInput, handleSendWrapper, sqlMode, setSqlMode, agentState])

  // Memoized data page props
  const dataPageProps = useMemo(() => ({
    selectedTable: data.selectedTable,
    tableContent: data.tableContent
  }), [data.selectedTable, data.tableContent])

  // Memoized modeling page props
  const modelingPageProps = useMemo(() => ({
    tables: data.tables,
    fetchTables: data.fetchTables,
    relationships: data.relationships,
    graphvizChart: data.graphvizChart,
    newRelationship: data.newRelationship,
    setNewRelationship: data.setNewRelationship,
    columnsSource: data.columnsSource,
    columnsTarget: data.columnsTarget,
    handleTableChange: data.handleTableChange,
    addRelationship: data.addRelationship,
    resetRelationships: data.resetRelationships,
    deleteRelationship: data.deleteRelationship
  }), [
    data.tables, data.fetchTables, data.relationships, data.graphvizChart,
    data.newRelationship, data.setNewRelationship, data.columnsSource,
    data.columnsTarget, data.handleTableChange, data.addRelationship,
    data.resetRelationships, data.deleteRelationship
  ])

  return (
    <MainLayout {...sidebarProps}>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<ChatPage {...chatPageProps} />} />
          <Route path="/data" element={<DataPage {...dataPageProps} />} />
          <Route path="/modeling" element={<ModelingPage {...modelingPageProps} />} />
        </Routes>
      </Suspense>
    </MainLayout>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
}

export default App
