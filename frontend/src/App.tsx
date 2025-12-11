import { BrowserRouter, Routes, Route } from "react-router-dom"
import { useState, useEffect } from "react"
import { MainLayout } from "./components/layout/MainLayout"
import { ChatPage } from "./pages/ChatPage"
import { DataPage } from "./pages/DataPage"
import { ModelingPage } from "./pages/ModelingPage"
import { useTheme } from "./hooks/useTheme"
import { useChat } from "./hooks/useChat"
import { useData } from "./hooks/useData"
import { api } from "./services/api"

function AppContent() {
  const { theme, toggleTheme } = useTheme()

  // Session State
  const [sessions, setSessions] = useState<{ id: string, title: string, created_at: string }[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string>(() => 'session_' + Date.now())
  const [sqlMode, setSqlMode] = useState(false)
  const [input, setInput] = useState('')

  // Hooks
  const { messages, setMessages, sendMessage, agentState, setAgentState } = useChat(sqlMode, currentSessionId)
  const data = useData()

  // Session Logic
  const fetchSessions = async () => {
    try {
      const data = await api.getSessions()
      setSessions(data)
    } catch (error) {
      console.error("Error fetching sessions:", error)
    }
  }

  const loadSession = async (sessionId: string) => {
    try {
      const data = await api.getSessionMessages(sessionId)
      // Convert history messages to UI format
      const uiMessages = data.map((msg: any) => {
        if (msg.role === 'assistant' && msg.content.startsWith('{')) {
          try {
            const parsed = JSON.parse(msg.content)
            if (parsed.type === 'data_result') {
              return {
                role: 'assistant',
                content: parsed.summary,
                type: 'table',
                tableData: { columns: parsed.columns, data: parsed.data }
              }
            }
            if (parsed.type === 'chart_result') {
              return {
                role: 'assistant',
                content: "Voici le graphique demandé :",
                type: 'chart',
                chartConfig: parsed.config
              }
            }
            if (parsed.type === 'chart_suggestions') {
              return {
                role: 'assistant',
                content: "Voici quelques suggestions de graphiques :",
                type: 'chart_suggestions',
                suggestions: parsed.suggestions
              }
            }
          } catch (e) { }
        }
        return { role: msg.role, content: msg.content }
      })
      setMessages(uiMessages)
      setCurrentSessionId(sessionId)
      // Reset agent state on session switch
      setAgentState(null)
    } catch (error) {
      console.error("Error loading session:", error)
    }
  }

  const createNewSession = () => {
    const newId = 'session_' + Date.now()
    setCurrentSessionId(newId)
    setMessages([{ role: 'assistant', content: 'Bonjour ! Je suis votre assistant Data Intelligence. Chargez un fichier CSV pour commencer.' }])
    setAgentState(null)
  }

  const deleteSession = async (sessionId: string, e: any) => {
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
  }

  useEffect(() => {
    fetchSessions()
  }, [])

  const handleSendWrapper = () => {
    sendMessage(input)
    setInput('')
  }

  // Pass Props
  const sidebarProps = {
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
    onFileUpload: async (e: any) => {
      const file = e.target.files?.[0]
      if (!file) return

      setMessages(prev => [...prev, { role: 'user', content: `Chargement du fichier: ${file.name} ` }])
      try {
        const res = await api.uploadFile(file)
        setMessages(prev => [...prev, { role: 'assistant', content: res.message }])
        // Refresh tables
        if (data.fetchTables) data.fetchTables()
      } catch (error: any) {
        setMessages(prev => [...prev, { role: 'assistant', content: `Erreur: ${error.message}` }])
      }
    }
  }

  return (
    <MainLayout {...sidebarProps}>
      <Routes>
        <Route path="/" element={
          <ChatPage
            messages={messages}
            input={input}
            setInput={setInput}
            handleSend={handleSendWrapper}
            sqlMode={sqlMode}
            setSqlMode={setSqlMode}
            agentState={agentState}
          />
        } />
        <Route path="/data" element={
          <DataPage
            selectedTable={data.selectedTable}
            tableContent={data.tableContent}
          />
        } />
        <Route path="/modeling" element={
          <ModelingPage
            tables={data.tables}
            fetchTables={data.fetchTables}
            relationships={data.relationships}
            mermaidChart={data.mermaidChart}
            newRelationship={data.newRelationship}
            setNewRelationship={data.setNewRelationship}
            columnsSource={data.columnsSource}
            columnsTarget={data.columnsTarget}
            handleTableChange={data.handleTableChange}
            addRelationship={data.addRelationship}
            resetRelationships={data.resetRelationships}
            deleteRelationship={data.deleteRelationship}
          />
        } />
      </Routes>
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
