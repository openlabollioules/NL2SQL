export interface Message {
    role: string;
    content: string;
    type?: 'table' | 'chart' | 'chart_suggestions' | 'error';
    tableData?: {
        columns: string[];
        data: any[];
    };
    chartConfig?: any;
    suggestions?: string[];
}

export interface Session {
    id: string;
    title: string;
    created_at: string;
}

export interface TableInfo {
    name: string;
}

export interface TableData {
    columns: string[];
    data: any[];
}

export interface Relationship {
    table_source: string;
    column_source: string;
    table_target: string;
    column_target: string;
}
