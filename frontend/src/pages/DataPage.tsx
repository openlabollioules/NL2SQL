import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Download } from "lucide-react"

interface DataPageProps {
    selectedTable: string | null
    tableContent: { columns: string[], data: any[] } | null
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
                Chargement...
            </div>
        )
    }

    return (
        <div className="flex-1 flex flex-col p-4 overflow-hidden">
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold">{selectedTable}</h2>
                <Button variant="outline" size="sm">
                    <Download className="h-4 w-4 mr-2" />
                    Export CSV
                </Button>
            </div>

            <div className="border rounded-md overflow-hidden bg-background shadow-sm flex-1">
                <ScrollArea className="h-full">
                    <div className="">
                        <table className="w-full text-sm text-left">
                            <thead className="bg-muted text-muted-foreground sticky top-0 z-10">
                                <tr>
                                    {tableContent.columns.map((col: string) => (
                                        <th key={col} className="px-4 py-2 font-medium whitespace-nowrap bg-muted">{col}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {tableContent.data.map((row: any, idx: number) => (
                                    <tr key={idx} className="border-b last:border-0 hover:bg-muted/50">
                                        {tableContent.columns.map((col: string) => (
                                            <td key={col} className="px-4 py-2 whitespace-nowrap">{row[col]}</td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </ScrollArea>
            </div>
        </div>
    )
}
