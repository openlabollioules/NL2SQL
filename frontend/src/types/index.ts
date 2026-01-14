/**
 * Type Definitions
 * Centralized TypeScript types for the application
 */

// ==================== Chat Types ====================

export type MessageRole = 'user' | 'assistant' | 'system';
export type MessageType = 'table' | 'chart' | 'chart_suggestions' | 'error';

export interface TableData {
    columns: string[];
    data: Record<string, unknown>[];
}

export interface ChartSuggestion {
    title: string;
    type: 'bar' | 'line' | 'pie' | 'scatter' | 'histogram' | 'area';
    description: string;
    intent: string;
}

export interface PlotlyTrace {
    type?: string;
    x?: unknown[];
    y?: unknown[];
    values?: unknown[];
    labels?: string[];
    name?: string;
    mode?: string;
    marker?: Record<string, unknown>;
    [key: string]: unknown;
}

export interface PlotlyLayout {
    title?: string | { text: string };
    xaxis?: Record<string, unknown>;
    yaxis?: Record<string, unknown>;
    template?: string;
    [key: string]: unknown;
}

export interface PlotlyConfig {
    data: PlotlyTrace[];
    layout: PlotlyLayout;
}

export interface Message {
    role: MessageRole;
    content: string;
    type?: MessageType;
    tableData?: TableData;
    chartConfig?: PlotlyConfig;
    suggestions?: ChartSuggestion[];
}

// ==================== Session Types ====================

export interface Session {
    id: string;
    title: string;
    created_at: string;
}

export interface HistoryMessage {
    id: number;
    session_id: string;
    role: MessageRole;
    content: string;
    type: string;
    metadata: Record<string, unknown> | null;
    created_at: string;
}

// ==================== Data Types ====================

export interface TableInfo {
    name: string;
}

export interface Relationship {
    table_source: string;
    column_source: string;
    table_target: string;
    column_target: string;
    description?: string;
}

// ==================== Agent State Types ====================

export interface AgentState {
    node: string;
    content: string;
}

// ==================== API Response Types ====================

export interface ApiErrorResponse {
    detail?: string;
    message?: string;
}

export interface UploadResponse {
    message: string;
    table_name?: string;
}

export interface TableListResponse {
    tables: string[];
}

export interface TableColumnsResponse {
    columns: string[];
}

export interface MermaidDiagramResponse {
    mermaid: string;
}

// ==================== Component Props Types ====================

export interface SidebarProps {
    theme: 'light' | 'dark';
    toggleTheme: () => void;
    sessions: Session[];
    currentSessionId: string;
    onLoadSession: (sessionId: string) => Promise<void>;
    onNewSession: () => void;
    onDeleteSession: (sessionId: string, e: React.MouseEvent) => Promise<void>;
    tables: string[];
    selectedTable: string | null;
    onSelectTable: (tableName: string) => Promise<void>;
    onDeleteTable: (tableName: string) => Promise<void>;
    onFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
    onRefreshTables: () => Promise<void>;
}

export interface ChatPageProps {
    messages: Message[];
    input: string;
    setInput: (value: string) => void;
    handleSend: () => void;
    sqlMode: boolean;
    setSqlMode: (value: boolean) => void;
    agentState: AgentState | null;
}

export interface DataPageProps {
    selectedTable: string | null;
    tableContent: TableData | null;
}

export interface ModelingPageProps {
    tables: string[];
    fetchTables: () => Promise<void>;
    relationships: Relationship[];
    mermaidChart: string;
    newRelationship: Relationship;
    setNewRelationship: (rel: Relationship) => void;
    columnsSource: string[];
    columnsTarget: string[];
    handleTableChange: (value: string, type: 'source' | 'target') => void;
    addRelationship: () => Promise<void>;
    resetRelationships: () => Promise<void>;
    deleteRelationship: (rel: Relationship) => Promise<void>;
}
