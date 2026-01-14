import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Sun, Moon, Trash2, Plus, Upload, RefreshCw } from "lucide-react"
import { useNavigate, useLocation } from "react-router-dom"
import { useRef } from "react"
import { api } from "@/services/api"

interface SidebarProps {
    theme: 'light' | 'dark'
    toggleTheme: () => void
    // Chat Props
    sessions?: any[]
    currentSessionId?: string
    onLoadSession?: (id: string) => void
    onNewSession?: () => void
    onDeleteSession?: (id: string, e: any) => void
    // Data Props
    tables?: string[]
    selectedTable?: string | null
    onSelectTable?: (name: string) => void
    onDeleteTable?: (name: string, e: any) => void
    // Upload
    onFileUpload?: (e: any) => void
    onRefreshTables?: () => void
}

export function Sidebar({
    theme,
    toggleTheme,
    sessions,
    currentSessionId,
    onLoadSession,
    onNewSession,
    onDeleteSession,
    tables,
    selectedTable,
    onSelectTable,
    onDeleteTable,
    onFileUpload,
    onRefreshTables
}: SidebarProps) {
    const navigate = useNavigate()
    const location = useLocation()
    const fileInputRef = useRef<HTMLInputElement>(null)

    const activeTab = location.pathname === '/' ? 'chat'
        : location.pathname === '/data' ? 'tables'
            : location.pathname === '/modeling' ? 'modeling'
                : 'chat';

    return (
        <div className="w-64 border-r bg-muted/20 flex flex-col">
            {/* Logo Area */}
            <div className="w-full relative group">
                <img
                    src={theme === 'dark' ? "/NDI_DARK.png" : "/LOGO_NDI_.png"}
                    alt="Naval Data Intelligence"
                    className="w-full h-auto object-cover transition-opacity duration-300"
                />
                <Button
                    variant="ghost"
                    size="icon"
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-background/50 backdrop-blur-sm hover:bg-background/80"
                    onClick={toggleTheme}
                    title={theme === 'dark' ? "Passer en mode clair" : "Passer en mode sombre"}
                >
                    {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                </Button>
            </div>

            {/* Navigation */}
            <div className="p-4 flex flex-col flex-1 overflow-hidden">
                <div className="flex gap-2 mb-4 shrink-0">
                    <Button
                        variant={activeTab === 'chat' ? "default" : "ghost"}
                        className="flex-1 px-2 text-xs"
                        onClick={() => navigate('/')}
                    >
                        Chat
                    </Button>
                    <Button
                        variant={activeTab === 'tables' ? "default" : "ghost"}
                        className="flex-1 px-2 text-xs"
                        onClick={() => navigate('/data')}
                    >
                        Tables
                    </Button>
                    <Button
                        variant={activeTab === 'modeling' ? "default" : "ghost"}
                        className="flex-1 px-2 text-xs"
                        onClick={() => navigate('/modeling')}
                    >
                        Modèle
                    </Button>
                </div>

                {/* Dynamic Content based on functionality */}
                {activeTab === 'chat' && sessions && (
                    <>
                        <input
                            type="file"
                            ref={fileInputRef}
                            className="hidden"
                            accept=".csv,.parquet"
                            onChange={onFileUpload}
                        />
                        <Button
                            variant="outline"
                            className="w-full justify-start gap-2 mb-4"
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <Upload className="h-4 w-4" />
                            Charger CSV
                        </Button>

                        <div className="flex-1">
                            <div className="flex items-center justify-between mb-2">
                                <h2 className="text-sm font-semibold text-muted-foreground">Historique</h2>
                                <div className="flex gap-1">
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-6 w-6 text-muted-foreground hover:text-destructive"
                                        onClick={async () => {
                                            if (!confirm("Tout effacer ?")) return;
                                            await api.deleteAllSessions();
                                            if (onNewSession) onNewSession(); // Trigger refresh
                                        }}
                                        title="Tout effacer"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onNewSession} title="Nouvelle conversation">
                                        <Plus className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                            <ScrollArea className="h-[calc(100vh-250px)]">
                                {sessions.map(session => (
                                    <div key={session.id} className="group flex items-center gap-1 mb-1">
                                        <Button
                                            variant={currentSessionId === session.id ? "secondary" : "ghost"}
                                            className="flex-1 justify-start text-sm truncate"
                                            onClick={() => onLoadSession && onLoadSession(session.id)}
                                        >
                                            {session.title || "Nouvelle conversation"}
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                                            onClick={(e) => onDeleteSession && onDeleteSession(session.id, e)}
                                        >
                                            <Trash2 className="h-3 w-3 text-muted-foreground hover:text-destructive" />
                                        </Button>
                                    </div>
                                ))}
                            </ScrollArea>
                        </div>
                    </>
                )}

                {/* Tables List */}
                {(activeTab === 'tables' || activeTab === 'modeling') && tables && (
                    <div className="flex-1">
                        <div className="flex items-center justify-between mb-2">
                            <h2 className="text-sm font-semibold text-muted-foreground">Tables disponibles</h2>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6 text-muted-foreground hover:text-foreground"
                                onClick={onRefreshTables}
                                title="Actualiser les tables"
                            >
                                <RefreshCw className="h-4 w-4" />
                            </Button>
                        </div>
                        <ScrollArea className="h-[calc(100vh-200px)]">
                            {tables.map(table => (
                                <div key={table} className="flex items-center gap-1 mb-1">
                                    <Button
                                        variant={selectedTable === table ? "secondary" : "ghost"}
                                        className="flex-1 justify-start text-sm truncate"
                                        onClick={() => onSelectTable && onSelectTable(table)}
                                    >
                                        {table}
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                                        onClick={(e) => onDeleteTable && onDeleteTable(table, e)}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            ))}
                        </ScrollArea>
                    </div>
                )}
            </div>
        </div>
    )
}
