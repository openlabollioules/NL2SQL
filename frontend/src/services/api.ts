const API_URL = 'http://127.0.0.1:8000/api/v1';

export const api = {
    uploadFile: async (file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`${API_URL}/upload`, {
            method: 'POST',
            body: formData,
        });
        return response.json();
    },

    getSessions: async () => {
        const response = await fetch(`${API_URL}/history/sessions`);
        return response.json();
    },

    getSessionMessages: async (sessionId: string) => {
        const response = await fetch(`${API_URL}/history/sessions/${sessionId}/messages`);
        return response.json();
    },

    deleteSession: async (sessionId: string) => {
        return fetch(`${API_URL}/history/sessions/${sessionId}`, { method: 'DELETE' });
    },

    deleteAllSessions: async () => {
        return fetch(`${API_URL}/history/sessions`, { method: 'DELETE' });
    },

    getTables: async () => {
        const response = await fetch(`${API_URL}/tables`);
        return response.json();
    },

    getTableContent: async (tableName: string) => {
        const response = await fetch(`${API_URL}/tables/${encodeURIComponent(tableName)}/preview`);
        return response.json();
    },

    deleteTable: async (tableName: string) => {
        return fetch(`${API_URL}/tables/${encodeURIComponent(tableName)}`, {
            method: 'DELETE'
        });
    },

    getRelationships: async () => {
        const response = await fetch(`${API_URL}/relationships`);
        return response.json();
    },

    getMermaidDiagram: async () => {
        const response = await fetch(`${API_URL}/relationships/mermaid`);
        return response.json();
    },

    getTableColumns: async (tableName: string) => {
        const response = await fetch(`${API_URL}/tables/${encodeURIComponent(tableName)}/columns`);
        return response.json();
    },

    addRelationship: async (relationship: any) => {
        return fetch(`${API_URL}/relationships`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(relationship)
        });
    },

    resetRelationships: async () => {
        return fetch(`${API_URL}/relationships/all`, {
            method: 'DELETE'
        });
    },

    deleteRelationship: async (relationship: any) => {
        const params = new URLSearchParams({
            table_source: relationship.table_source,
            column_source: relationship.column_source,
            table_target: relationship.table_target,
            column_target: relationship.column_target
        });
        return fetch(`${API_URL}/relationships?${params.toString()}`, {
            method: 'DELETE'
        });
    },

    exportConfig: async () => {
        const response = await fetch(`${API_URL}/relationships/export`);
        return response.blob();
    },

    importConfig: async (file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        return fetch(`${API_URL}/relationships/import`, {
            method: 'POST',
            body: formData
        });
    }
};
