/**
 * DataPage Component
 * Displays table data with virtualization for large datasets
 */
import { Button } from "@/components/ui/button"
import { VirtualizedTable } from "@/components/ui/VirtualizedTable"
import { Download } from "lucide-react"
import type { TableData } from "../types"

interface DataPageProps {
    selectedTable: string | null
    tableContent: TableData | null
}

export function DataPage({ selectedTable, tableContent }: DataPageProps) {
    if (!selectedTable) {
        return (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
                Sélectionnez une table pour voir son contenu
            </div>
        )
    }

    if (!tableContent) {
        return (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
                <div className="flex flex-col items-center gap-2">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    Chargement...
                </div>
            </div>
        )
    }

    const handleExport = () => {
        // Generate CSV content
        const headers = tableContent.columns.join(',');
        const rows = tableContent.data.map(row =>
            tableContent.columns.map(col => {
                const val = row[col];
                // Escape quotes and wrap in quotes if contains comma
                if (typeof val === 'string' && (val.includes(',') || val.includes('"'))) {
                    return `"${val.replace(/"/g, '""')}"`;
                }
                return val ?? '';
            }).join(',')
        );
        const csv = [headers, ...rows].join('\n');

        // Download
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `${selectedTable}.csv`;
        link.click();
    };

    return (
        <div className="flex-1 flex flex-col p-4 overflow-hidden gap-4">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-xl font-bold">{selectedTable}</h2>
                    <p className="text-sm text-muted-foreground">
                        {tableContent.data.length.toLocaleString('fr-FR')} lignes • {tableContent.columns.length} colonnes
                    </p>
                </div>
                <Button variant="outline" size="sm" onClick={handleExport}>
                    <Download className="h-4 w-4 mr-2" />
                    Export CSV
                </Button>
            </div>

            <div className="flex-1 min-h-0">
                <VirtualizedTable
                    data={tableContent}
                    maxHeight={600}
                />
            </div>
        </div>
    )
}
