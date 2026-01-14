/**
 * API Service
 * Centralized API client with proper error handling
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';

/**
 * Custom error class for API errors
 */
export class ApiError extends Error {
    status: number;
    statusText: string;

    constructor(status: number, statusText: string, message?: string) {
        super(message || `API Error: ${status} ${statusText}`);
        this.name = 'ApiError';
        this.status = status;
        this.statusText = statusText;
    }
}

/**
 * Fetch wrapper with error handling
 */
async function fetchWithError<T>(url: string, options?: RequestInit): Promise<T> {
    const response = await fetch(url, options);

    if (!response.ok) {
        let errorMessage: string | undefined;
        try {
            const errorBody = await response.json();
            errorMessage = errorBody.detail || errorBody.message || JSON.stringify(errorBody);
        } catch {
            // Response body is not JSON
        }
        throw new ApiError(response.status, response.statusText, errorMessage);
    }

    return response.json();
}

/**
 * Fetch wrapper for operations that don't return JSON
 */
async function fetchWithErrorNoBody(url: string, options?: RequestInit): Promise<Response> {
    const response = await fetch(url, options);

    if (!response.ok) {
        let errorMessage: string | undefined;
        try {
            const errorBody = await response.json();
            errorMessage = errorBody.detail || errorBody.message;
        } catch {
            // Response body is not JSON
        }
        throw new ApiError(response.status, response.statusText, errorMessage);
    }

    return response;
}

// Type definitions
interface TableListResponse {
    tables: string[];
}

interface TableContentResponse {
    columns: string[];
    data: Record<string, unknown>[];
}

interface TableColumnsResponse {
    columns: string[];
}

interface UploadResponse {
    message: string;
    table_name?: string;
}

interface MermaidResponse {
    mermaid: string;
}

interface GraphvizResponse {
    graphviz: string;
}

interface Session {
    id: string;
    title: string;
    created_at: string;
}

interface Message {
    id: number;
    session_id: string;
    role: string;
    content: string;
    type: string;
    metadata: Record<string, unknown> | null;
    created_at: string;
}

interface Relationship {
    table_source: string;
    column_source: string;
    table_target: string;
    column_target: string;
    description?: string;
}

export const api = {
    /**
     * Upload a CSV/Excel file
     */
    uploadFile: async (file: File): Promise<UploadResponse> => {
        const formData = new FormData();
        formData.append('file', file);
        return fetchWithError<UploadResponse>(`${API_URL}/upload`, {
            method: 'POST',
            body: formData,
        });
    },

    // ==================== Session Management ====================

    getSessions: async (): Promise<Session[]> => {
        return fetchWithError<Session[]>(`${API_URL}/history/sessions`);
    },

    getSessionMessages: async (sessionId: string): Promise<Message[]> => {
        return fetchWithError<Message[]>(`${API_URL}/history/sessions/${encodeURIComponent(sessionId)}/messages`);
    },

    deleteSession: async (sessionId: string): Promise<void> => {
        await fetchWithErrorNoBody(`${API_URL}/history/sessions/${encodeURIComponent(sessionId)}`, {
            method: 'DELETE'
        });
    },

    deleteAllSessions: async (): Promise<void> => {
        await fetchWithErrorNoBody(`${API_URL}/history/sessions`, {
            method: 'DELETE'
        });
    },

    // ==================== Table Management ====================

    getTables: async (): Promise<TableListResponse> => {
        return fetchWithError<TableListResponse>(`${API_URL}/tables`);
    },

    getTableContent: async (tableName: string): Promise<TableContentResponse> => {
        return fetchWithError<TableContentResponse>(
            `${API_URL}/tables/${encodeURIComponent(tableName)}/preview`
        );
    },

    getTableColumns: async (tableName: string): Promise<TableColumnsResponse> => {
        return fetchWithError<TableColumnsResponse>(
            `${API_URL}/tables/${encodeURIComponent(tableName)}/columns`
        );
    },

    deleteTable: async (tableName: string): Promise<void> => {
        await fetchWithErrorNoBody(`${API_URL}/tables/${encodeURIComponent(tableName)}`, {
            method: 'DELETE'
        });
    },

    // ==================== Relationship Management ====================

    getRelationships: async (): Promise<Relationship[]> => {
        return fetchWithError<Relationship[]>(`${API_URL}/relationships`);
    },

    getMermaidDiagram: async (): Promise<MermaidResponse> => {
        return fetchWithError<MermaidResponse>(`${API_URL}/relationships/mermaid`);
    },

    getGraphvizDiagram: async (): Promise<GraphvizResponse> => {
        return fetchWithError<GraphvizResponse>(`${API_URL}/relationships/graphviz`);
    },

    addRelationship: async (relationship: Relationship): Promise<void> => {
        await fetchWithErrorNoBody(`${API_URL}/relationships`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(relationship)
        });
    },

    deleteRelationship: async (relationship: Relationship): Promise<void> => {
        const params = new URLSearchParams({
            table_source: relationship.table_source,
            column_source: relationship.column_source,
            table_target: relationship.table_target,
            column_target: relationship.column_target
        });
        await fetchWithErrorNoBody(`${API_URL}/relationships?${params.toString()}`, {
            method: 'DELETE'
        });
    },

    resetRelationships: async (): Promise<void> => {
        await fetchWithErrorNoBody(`${API_URL}/relationships/all`, {
            method: 'DELETE'
        });
    },

    // ==================== Import/Export ====================

    exportConfig: async (): Promise<Blob> => {
        const response = await fetchWithErrorNoBody(`${API_URL}/relationships/export`);
        return response.blob();
    },

    importConfig: async (file: File): Promise<void> => {
        const formData = new FormData();
        formData.append('file', file);
        await fetchWithErrorNoBody(`${API_URL}/relationships/import`, {
            method: 'POST',
            body: formData
        });
    }
};
