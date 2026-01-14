/**
 * VirtualizedTable Component
 * Efficiently renders large datasets using virtualization
 */
import { useRef, useMemo } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { TableData } from '../../types';

interface VirtualizedTableProps {
    data: TableData;
    maxHeight?: number;
    rowHeight?: number;
}

export function VirtualizedTable({
    data,
    maxHeight = 400,
    rowHeight = 40
}: VirtualizedTableProps) {
    const parentRef = useRef<HTMLDivElement>(null);

    const { columns, data: rows } = data;

    // Determine if virtualization is needed (> 100 rows)
    const useVirtual = rows.length > 100;

    const rowVirtualizer = useVirtualizer({
        count: rows.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => rowHeight,
        overscan: 10,
        enabled: useVirtual,
    });

    // Calculate column widths based on content
    const columnWidths = useMemo(() => {
        const widths: Record<string, number> = {};
        columns.forEach(col => {
            // Min width based on header + some samples
            const headerLen = col.length;
            let maxLen = headerLen;

            // Sample first 20 rows
            for (let i = 0; i < Math.min(20, rows.length); i++) {
                const val = String(rows[i][col] ?? '');
                maxLen = Math.max(maxLen, val.length);
            }

            // Convert to pixels (rough approximation)
            widths[col] = Math.min(Math.max(80, maxLen * 10), 300);
        });
        return widths;
    }, [columns, rows]);

    const totalWidth = Object.values(columnWidths).reduce((a, b) => a + b, 0);

    // Render non-virtualized table for small datasets
    if (!useVirtual) {
        return (
            <div className="overflow-auto rounded-lg border border-border" style={{ maxHeight }}>
                <table className="min-w-full divide-y divide-border">
                    <thead className="bg-muted sticky top-0 z-10">
                        <tr>
                            {columns.map((col) => (
                                <th
                                    key={col}
                                    className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap"
                                    style={{ minWidth: columnWidths[col] }}
                                >
                                    {col}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="bg-background divide-y divide-border">
                        {rows.map((row, idx) => (
                            <tr key={idx} className="hover:bg-muted/50 transition-colors">
                                {columns.map((col) => (
                                    <td
                                        key={col}
                                        className="px-4 py-2 text-sm text-foreground whitespace-nowrap"
                                    >
                                        {formatCellValue(row[col])}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        );
    }

    // Virtualized table for large datasets
    return (
        <div
            ref={parentRef}
            className="overflow-auto rounded-lg border border-border"
            style={{ maxHeight }}
        >
            {/* Header */}
            <div
                className="sticky top-0 z-10 bg-muted flex border-b border-border"
                style={{ minWidth: totalWidth }}
            >
                {columns.map((col) => (
                    <div
                        key={col}
                        className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider flex-shrink-0"
                        style={{ width: columnWidths[col] }}
                    >
                        {col}
                    </div>
                ))}
            </div>

            {/* Virtualized body */}
            <div
                style={{
                    height: `${rowVirtualizer.getTotalSize()}px`,
                    width: totalWidth,
                    position: 'relative',
                }}
            >
                {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                    const row = rows[virtualRow.index];
                    return (
                        <div
                            key={virtualRow.index}
                            className={`flex absolute left-0 w-full hover:bg-muted/50 transition-colors ${virtualRow.index % 2 === 0 ? 'bg-background' : 'bg-muted/20'
                                }`}
                            style={{
                                height: `${virtualRow.size}px`,
                                transform: `translateY(${virtualRow.start}px)`,
                            }}
                        >
                            {columns.map((col) => (
                                <div
                                    key={col}
                                    className="px-4 py-2 text-sm text-foreground flex-shrink-0 truncate"
                                    style={{ width: columnWidths[col] }}
                                    title={String(row[col] ?? '')}
                                >
                                    {formatCellValue(row[col])}
                                </div>
                            ))}
                        </div>
                    );
                })}
            </div>

            {/* Row count indicator */}
            <div className="sticky bottom-0 bg-muted/80 backdrop-blur px-4 py-2 text-xs text-muted-foreground border-t border-border">
                {rows.length.toLocaleString()} lignes (virtualisé)
            </div>
        </div>
    );
}

/**
 * Format cell values for display
 */
function formatCellValue(value: unknown): string {
    if (value === null || value === undefined) {
        return '—';
    }
    if (typeof value === 'number') {
        // Format numbers with French locale
        return value.toLocaleString('fr-FR');
    }
    if (typeof value === 'boolean') {
        return value ? 'Oui' : 'Non';
    }
    if (value instanceof Date) {
        return value.toLocaleDateString('fr-FR');
    }
    return String(value);
}
