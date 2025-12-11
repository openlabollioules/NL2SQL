import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Dialog, DialogContent, DialogTrigger, DialogTitle } from "@/components/ui/dialog"
import { Network, RefreshCw, Trash2, Download, Upload, Maximize2, Loader2 } from "lucide-react"
import { MermaidDiagram } from "../components/MermaidDiagram"
import { useRef } from "react"
import { api } from "@/services/api"

interface ModelingPageProps {
    tables: string[]
    fetchTables: () => void
    relationships: any[]
    mermaidChart: string
    newRelationship: any
    setNewRelationship: (val: any) => void
    columnsSource: string[]
    columnsTarget: string[]
    handleTableChange: (val: string, type: 'source' | 'target') => void
    addRelationship: () => void
    resetRelationships: () => void
    deleteRelationship: (rel: any) => void
}

export function ModelingPage({
    tables,
    fetchTables,
    relationships,
    mermaidChart,
    newRelationship,
    setNewRelationship,
    columnsSource,
    columnsTarget,
    handleTableChange,
    addRelationship,
    resetRelationships,
    deleteRelationship
}: ModelingPageProps) {
    const configInputRef = useRef<HTMLInputElement>(null)

    const handleConfigUpload = async (e: any) => {
        const file = e.target.files?.[0]
        if (!file) return

        try {
            await api.importConfig(file)
            alert("Configuration importée avec succès !")
            // Trigger refresh via parent or hook if needed, but fetchRelationships should be called by parent
            window.location.reload() // Simple reload for now or rely on hook
        } catch (error) {
            console.error("Error importing config:", error)
            alert("Erreur lors de l'importation.")
        }
        if (configInputRef.current) configInputRef.current.value = ''
    }

    const exportConfig = async () => {
        try {
            const blob = await api.exportConfig()
            const url = window.URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = 'relationships.json'
            document.body.appendChild(a)
            a.click()
            window.URL.revokeObjectURL(url)
            document.body.removeChild(a)
        } catch (error) {
            console.error("Error exporting config:", error)
        }
    }

    return (
        <div className="p-6 h-full flex flex-col max-w-4xl mx-auto w-full overflow-hidden">
            <h2 className="text-2xl font-bold mb-6 flex items-center gap-2 shrink-0">
                <Network className="h-6 w-6" />
                Modélisation des données
            </h2>
            <input
                type="file"
                ref={configInputRef}
                className="hidden"
                accept=".json"
                onChange={handleConfigUpload}
            />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8 shrink-0">
                {/* Left Column: Add Relationship */}
                <div className="bg-muted/30 p-6 rounded-lg border h-full">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="font-semibold">Ajouter une relation</h3>
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground">({tables.length} tables chargées)</span>
                            <Button variant="ghost" size="icon" onClick={fetchTables} title="Rafraîchir les tables">
                                <RefreshCw className="h-4 w-4" />
                            </Button>

                            <Button variant="ghost" size="sm" onClick={resetRelationships} className="text-destructive hover:text-destructive">
                                <Trash2 className="h-4 w-4 mr-2" />
                                Reset Tout
                            </Button>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 mb-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Table Source</label>
                            <select
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                value={newRelationship.table_source}
                                onChange={e => handleTableChange(e.target.value, 'source')}
                            >
                                <option value="">Sélectionner...</option>
                                {tables.map(t => <option key={t} value={t}>{t}</option>)}
                            </select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Colonne Source</label>
                            <select
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                value={newRelationship.column_source}
                                onChange={e => setNewRelationship({ ...newRelationship, column_source: e.target.value })}
                                disabled={!newRelationship.table_source}
                            >
                                <option value="">Sélectionner...</option>
                                {columnsSource.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Table Cible</label>
                            <select
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                value={newRelationship.table_target}
                                onChange={e => handleTableChange(e.target.value, 'target')}
                            >
                                <option value="">Sélectionner...</option>
                                {tables.map(t => <option key={t} value={t}>{t}</option>)}
                            </select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Colonne Cible</label>
                            <select
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                value={newRelationship.column_target}
                                onChange={e => setNewRelationship({ ...newRelationship, column_target: e.target.value })}
                                disabled={!newRelationship.table_target}
                            >
                                <option value="">Sélectionner...</option>
                                {columnsTarget.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                        </div>
                    </div>
                    <Button onClick={addRelationship} className="w-full">
                        Créer la relation
                    </Button>
                </div>

                {/* Right Column: Active Relations */}
                <div className="bg-muted/30 p-6 rounded-lg border h-full flex flex-col">
                    <h3 className="font-semibold mb-4">Relations actives</h3>
                    <ScrollArea className="flex-1 h-[200px] pr-4">
                        {relationships.length === 0 ? (
                            <div className="text-center p-8 text-muted-foreground border rounded-lg border-dashed h-full flex items-center justify-center">
                                Aucune relation définie. L'agent utilisera l'inférence automatique.
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {relationships.map((rel, i) => (
                                    <div key={i} className="flex items-center justify-between p-2 border rounded-lg bg-card shadow-sm gap-2">
                                        <div className="flex flex-col gap-0.5 text-xs flex-1 min-w-0 overflow-hidden">
                                            <div className="flex items-center gap-1 truncate">
                                                <span className="font-semibold text-primary truncate" title={rel.table_source}>{rel.table_source}</span>
                                                <span className="text-muted-foreground">.</span>
                                                <span className="truncate" title={rel.column_source}>{rel.column_source}</span>
                                            </div>
                                            <div className="flex items-center gap-1 truncate text-muted-foreground">
                                                <span className="mx-0.5">↳</span>
                                                <span className="font-semibold text-primary truncate" title={rel.table_target}>{rel.table_target}</span>
                                                <span>.</span>
                                                <span className="truncate" title={rel.column_target}>{rel.column_target}</span>
                                            </div>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-6 w-6 shrink-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                            onClick={() => deleteRelationship(rel)}
                                        >
                                            <Trash2 className="h-3 w-3" />
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </ScrollArea>
                </div>
            </div>

            {/* Bottom Row: Diagram */}
            <div className="bg-card border rounded-lg p-4 h-[500px] flex flex-col shadow-sm flex-1">
                <div className="flex items-center justify-between mb-4 shrink-0">
                    <h3 className="font-semibold flex items-center gap-2">
                        <Network className="h-4 w-4" />
                        Diagramme BDD
                    </h3>
                    <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={exportConfig} title="Exporter la configuration">
                            <Download className="h-4 w-4 mr-2" />
                            Exporter
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => configInputRef.current?.click()} title="Importer la configuration">
                            <Upload className="h-4 w-4 mr-2" />
                            Importer
                        </Button>
                        <Dialog>
                            <DialogTrigger asChild>
                                <Button variant="outline" size="sm">
                                    <Maximize2 className="h-4 w-4 mr-2" />
                                    Plein écran
                                </Button>
                            </DialogTrigger>
                            <DialogContent className="max-w-[95vw] h-[95vh] flex flex-col p-0" aria-describedby={undefined}>
                                <div className="p-4 border-b flex items-center justify-between bg-muted/30">
                                    <DialogTitle className="font-semibold text-lg">Diagramme BDD - Plein écran</DialogTitle>
                                </div>
                                <div className="flex-1 overflow-auto p-4 bg-white">
                                    {mermaidChart && <MermaidDiagram chart={mermaidChart} />}
                                </div>
                            </DialogContent>
                        </Dialog>
                    </div>
                </div>
                <div className="flex-1 overflow-auto bg-white rounded border p-4">
                    {mermaidChart ? (
                        <MermaidDiagram chart={mermaidChart} />
                    ) : (
                        <div className="h-full flex items-center justify-center text-muted-foreground flex-col gap-2">
                            <Loader2 className="h-8 w-8 animate-spin text-primary/50" />
                            <span>Chargement du diagramme...</span>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
