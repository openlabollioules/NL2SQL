import type { ReactNode } from "react"
import { Sidebar } from "./Sidebar"

interface MainLayoutProps {
    children: ReactNode
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
}

export function MainLayout({ children, ...sidebarProps }: MainLayoutProps) {
    return (
        <div className="flex h-screen bg-background text-foreground">
            <Sidebar {...sidebarProps} />
            <div className="flex-1 flex flex-col overflow-hidden">
                {children}
            </div>
        </div>
    )
}
