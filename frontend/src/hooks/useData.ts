import { useState, useEffect } from 'react';
import { api } from '../services/api';

export function useData() {
    const [tables, setTables] = useState<string[]>([]);
    const [selectedTable, setSelectedTable] = useState<string | null>(null);
    const [tableContent, setTableContent] = useState<{ columns: string[], data: any[] } | null>(null);

    // Relationships State
    const [relationships, setRelationships] = useState<any[]>([]);
    const [mermaidChart, setMermaidChart] = useState<string>('');
    const [newRelationship, setNewRelationship] = useState({
        table_source: '',
        column_source: '',
        table_target: '',
        column_target: ''
    });
    const [columnsSource, setColumnsSource] = useState<string[]>([]);
    const [columnsTarget, setColumnsTarget] = useState<string[]>([]);

    const fetchTables = async () => {
        try {
            const data = await api.getTables();
            setTables(data.tables);
        } catch (error) {
            console.error("Error fetching tables:", error);
        }
    };

    const fetchTableContent = async (tableName: string) => {
        try {
            const data = await api.getTableContent(tableName);
            setTableContent(data);
            setSelectedTable(tableName);
        } catch (error) {
            console.error("Error fetching table content:", error);
        }
    };

    const deleteTable = async (tableName: string) => {
        if (!confirm(`Voulez-vous vraiment supprimer la table "${tableName}" ?`)) return;
        try {
            await api.deleteTable(tableName);
            setTables(prev => prev.filter(t => t !== tableName));
            if (selectedTable === tableName) {
                setSelectedTable(null);
                setTableContent(null);
            }
        } catch (error) {
            console.error("Error deleting table:", error);
        }
    };

    // Relationship Logic
    const fetchRelationships = async () => {
        try {
            console.log("Fetching relationships...");
            const rels = await api.getRelationships();
            setRelationships(rels);
            const func = await api.getMermaidDiagram();
            setMermaidChart(func.mermaid);
        } catch (error) {
            console.error("Error fetching relationships:", error);
        }
    };

    useEffect(() => {
        fetchTables();
        fetchRelationships();
    }, []);

    const fetchColumns = async (tableName: string, type: 'source' | 'target') => {
        if (!tableName) return;
        try {
            const data = await api.getTableColumns(tableName);
            if (type === 'source') setColumnsSource(data.columns);
            else setColumnsTarget(data.columns);
        } catch (error) {
            console.error("Error fetching columns:", error);
        }
    };

    const handleTableChange = (value: string, type: 'source' | 'target') => {
        if (type === 'source') {
            setNewRelationship(prev => ({ ...prev, table_source: value, column_source: '' }));
            fetchColumns(value, 'source');
        } else {
            setNewRelationship(prev => ({ ...prev, table_target: value, column_target: '' }));
            fetchColumns(value, 'target');
        }
    };

    const addRelationship = async () => {
        if (!newRelationship.table_source || !newRelationship.column_source ||
            !newRelationship.table_target || !newRelationship.column_target) return;

        try {
            await api.addRelationship(newRelationship);
            await fetchRelationships();
            setNewRelationship({ table_source: '', column_source: '', table_target: '', column_target: '' });
            setColumnsSource([]);
            setColumnsTarget([]);
        } catch (error) {
            console.error("Error adding relationship:", error);
        }
    };

    const resetRelationships = async () => {
        if (!confirm("Voulez-vous vraiment supprimer TOUTES les relations ?")) return;
        try {
            await api.resetRelationships();
            fetchRelationships();
        } catch (e) { console.error(e) }
    };

    const deleteRelationship = async (rel: any) => {
        try {
            await api.deleteRelationship(rel);
            fetchRelationships();
        } catch (e) { console.error(e) }
    }

    return {
        tables,
        selectedTable,
        tableContent,
        fetchTables,
        fetchTableContent,
        deleteTable,
        relationships,
        mermaidChart,
        newRelationship,
        setNewRelationship,
        columnsSource,
        columnsTarget,
        fetchRelationships,
        handleTableChange,
        addRelationship,
        resetRelationships,
        deleteRelationship
    };
}
