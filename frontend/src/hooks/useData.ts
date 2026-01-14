/**
 * useData Hook
 * Manages data-related state with memoized callbacks
 */
import { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import type { Relationship, TableData } from '../types';

interface NewRelationship {
    table_source: string;
    column_source: string;
    table_target: string;
    column_target: string;
}

export function useData() {
    // Table state
    const [tables, setTables] = useState<string[]>([]);
    const [selectedTable, setSelectedTable] = useState<string | null>(null);
    const [tableContent, setTableContent] = useState<TableData | null>(null);

    // Relationships state
    const [relationships, setRelationships] = useState<Relationship[]>([]);
    const [graphvizChart, setGraphvizChart] = useState<string>('');
    const [newRelationship, setNewRelationship] = useState<NewRelationship>({
        table_source: '',
        column_source: '',
        table_target: '',
        column_target: ''
    });
    const [columnsSource, setColumnsSource] = useState<string[]>([]);
    const [columnsTarget, setColumnsTarget] = useState<string[]>([]);

    // Memoized table fetching
    const fetchTables = useCallback(async () => {
        try {
            const data = await api.getTables();
            setTables(data.tables);
        } catch (error) {
            console.error("Error fetching tables:", error);
        }
    }, []);

    // Memoized table content fetching
    const fetchTableContent = useCallback(async (tableName: string) => {
        try {
            const data = await api.getTableContent(tableName);
            setTableContent(data);
            setSelectedTable(tableName);
        } catch (error) {
            console.error("Error fetching table content:", error);
        }
    }, []);

    // Memoized table deletion
    const deleteTable = useCallback(async (tableName: string) => {
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
    }, [selectedTable]);

    // Memoized relationship fetching
    const fetchRelationships = useCallback(async () => {
        try {
            const rels = await api.getRelationships();
            setRelationships(rels);
            const diagram = await api.getGraphvizDiagram();
            setGraphvizChart(diagram.graphviz);
        } catch (error) {
            console.error("Error fetching relationships:", error);
        }
    }, []);

    // Initial data fetch
    useEffect(() => {
        fetchTables();
        fetchRelationships();
    }, [fetchTables, fetchRelationships]);

    // Memoized column fetching
    const fetchColumns = useCallback(async (tableName: string, type: 'source' | 'target') => {
        if (!tableName) return;
        try {
            const data = await api.getTableColumns(tableName);
            if (type === 'source') {
                setColumnsSource(data.columns);
            } else {
                setColumnsTarget(data.columns);
            }
        } catch (error) {
            console.error("Error fetching columns:", error);
        }
    }, []);

    // Memoized table change handler
    const handleTableChange = useCallback((value: string, type: 'source' | 'target') => {
        if (type === 'source') {
            setNewRelationship(prev => ({ ...prev, table_source: value, column_source: '' }));
            fetchColumns(value, 'source');
        } else {
            setNewRelationship(prev => ({ ...prev, table_target: value, column_target: '' }));
            fetchColumns(value, 'target');
        }
    }, [fetchColumns]);

    // Memoized relationship addition
    const addRelationship = useCallback(async () => {
        if (!newRelationship.table_source || !newRelationship.column_source ||
            !newRelationship.table_target || !newRelationship.column_target) {
            return;
        }

        try {
            await api.addRelationship(newRelationship);
            await fetchRelationships();
            setNewRelationship({
                table_source: '',
                column_source: '',
                table_target: '',
                column_target: ''
            });
            setColumnsSource([]);
            setColumnsTarget([]);
        } catch (error) {
            console.error("Error adding relationship:", error);
        }
    }, [newRelationship, fetchRelationships]);

    // Memoized relationship reset
    const resetRelationships = useCallback(async () => {
        if (!confirm("Voulez-vous vraiment supprimer TOUTES les relations ?")) return;
        try {
            await api.resetRelationships();
            await fetchRelationships();
        } catch (error) {
            console.error("Error resetting relationships:", error);
        }
    }, [fetchRelationships]);

    // Memoized single relationship deletion
    const deleteRelationship = useCallback(async (rel: Relationship) => {
        try {
            await api.deleteRelationship(rel);
            await fetchRelationships();
        } catch (error) {
            console.error("Error deleting relationship:", error);
        }
    }, [fetchRelationships]);

    return {
        // Table data
        tables,
        selectedTable,
        tableContent,
        fetchTables,
        fetchTableContent,
        deleteTable,

        // Relationship data
        relationships,
        graphvizChart,
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
