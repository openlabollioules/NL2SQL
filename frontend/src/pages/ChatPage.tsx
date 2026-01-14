import { useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { MessageSquare, Database, Send, Upload } from "lucide-react"
import { PlotlyChart } from "@/components/PlotlyChart"

interface ChatPageProps {
    messages: any[]
    input: string
    setInput: (val: string) => void
    handleSend: () => void
    sqlMode: boolean
    setSqlMode: (val: boolean) => void
    agentState: any
}

export function ChatPage({
    messages,
    input,
    setInput,
    handleSend,
    sqlMode,
    setSqlMode,
    agentState
}: ChatPageProps) {
    const scrollRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (scrollRef.current) {
            // scrollRef.current.scrollIntoView({ behavior: "smooth" }) 
            // ScrollArea component handling might be different, usually we scroll the viewport inside
        }
    }, [messages])

    const exportToCSV = (data: any[], columns: string[], filename: string) => {
        const header = columns.join(',')
        const rows = data.map(row => columns.map((col: any) => JSON.stringify(row[col])).join(','))
        const csvContent = [header, ...rows].join('\n')

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `${filename}.csv`)
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
    }

    return (
        <>
            <header className="h-14 border-b flex items-center px-6 justify-between shrink-0">
                <h2 className="font-semibold">Session active</h2>
                <div className="flex items-center gap-2 bg-muted/50 p-1 rounded-lg">
                    <Button
                        variant={!sqlMode ? "secondary" : "ghost"}
                        size="sm"
                        onClick={() => setSqlMode(false)}
                        className="flex-1"
                    >
                        <MessageSquare className="h-4 w-4 mr-2" />
                        Chat
                    </Button>
                    <Button
                        variant={sqlMode ? "secondary" : "ghost"}
                        size="sm"
                        onClick={() => setSqlMode(true)}
                        className="flex-1"
                    >
                        <Database className="h-4 w-4 mr-2" />
                        SQL
                    </Button>
                </div>
                <Avatar>
                    <AvatarFallback>U</AvatarFallback>
                </Avatar>
            </header>

            {/* Messages Area */}
            <ScrollArea className="flex-1 p-4">
                <div className="max-w-3xl mx-auto space-y-4 pb-4">
                    {messages.map((msg, i) => (
                        <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                            <div className={`max-w-[80%] rounded-lg p-3 ${msg.role === 'user'
                                ? 'bg-primary text-primary-foreground'
                                : 'bg-muted'
                                }`}>
                                {msg.content}
                            </div>

                            {/* Render Table */}
                            {msg.type === 'table' && msg.tableData && (
                                <div className="mt-2 w-full max-w-[90%] border rounded-md overflow-hidden bg-background shadow-sm">
                                    <div className="p-2 bg-muted/50 flex justify-end">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => exportToCSV(msg.tableData.data, msg.tableData.columns, 'export_result')}
                                        >
                                            <Upload className="h-3 w-3 mr-2 rotate-180" /> Export CSV
                                        </Button>
                                    </div>
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-sm text-left">
                                            <thead className="bg-muted text-muted-foreground">
                                                <tr>
                                                    {msg.tableData.columns.map((col: string) => (
                                                        <th key={col} className="px-4 py-2 font-medium whitespace-nowrap">{col}</th>
                                                    ))}
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {msg.tableData.data.map((row: any, idx: number) => (
                                                    <tr key={idx} className="border-b last:border-0 hover:bg-muted/50">
                                                        {msg.tableData.columns.map((col: string) => (
                                                            <td key={col} className="px-4 py-2 whitespace-nowrap">{row[col]}</td>
                                                        ))}
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                    <div className="mt-2 flex justify-end p-2">
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            className="gap-2"
                                            onClick={() => {
                                                setInput("Génère un graphique pour ces données");
                                            }}
                                        >
                                            <Database className="h-3 w-3" />
                                            Visualiser
                                        </Button>
                                    </div>
                                </div>
                            )}

                            {/* Render Chart */}
                            {msg.type === 'chart' && msg.chartConfig && (
                                <div className="mt-2 w-full max-w-[90%] border rounded-md overflow-hidden bg-white p-2">
                                    <PlotlyChart
                                        data={msg.chartConfig.data}
                                        layout={{
                                            ...msg.chartConfig.layout,
                                            autosize: true,
                                            margin: { l: 50, r: 50, b: 150, t: 50, pad: 4 },
                                            xaxis: {
                                                ...msg.chartConfig.layout?.xaxis,
                                                automargin: true,
                                                tickangle: -45
                                            },
                                            yaxis: {
                                                ...msg.chartConfig.layout?.yaxis,
                                                automargin: true
                                            }
                                        }}
                                        style={{ width: "100%", height: "500px" }}
                                        useResizeHandler={true}
                                    />
                                </div>
                            )}

                            {/* Render Chart Suggestions */}
                            {msg.type === 'chart_suggestions' && msg.suggestions && (
                                <div className="mt-2 flex flex-wrap gap-2">
                                    {(typeof msg.suggestions === 'string' ? JSON.parse(msg.suggestions) : msg.suggestions).map((suggestion: any, idx: number) => (
                                        <Button
                                            key={idx}
                                            variant="outline"
                                            size="sm"
                                            onClick={() => setInput(`Génère le graphique : ${suggestion.title}`)}
                                        >
                                            {suggestion.title}
                                        </Button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                    <div ref={scrollRef} />
                </div>
            </ScrollArea>

            {/* Input Area */}
            <div className="p-4 border-t bg-background">
                <div className="max-w-3xl mx-auto relative">
                    {agentState && (
                        <div className="absolute bottom-full left-0 right-0 mb-2 p-2 bg-muted/80 backdrop-blur rounded-lg border text-xs flex items-center animate-in slide-in-from-bottom-2">
                            <div className="animate-spin mr-2">⚡️</div>
                            <span className="font-mono text-primary">{agentState.content}</span>
                        </div>
                    )}

                    <form
                        onSubmit={(e) => {
                            e.preventDefault()
                            handleSend()
                        }}
                        className="flex gap-2"
                    >
                        <Input
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder={sqlMode ? "Entrez votre requête SQL..." : "Posez une question sur vos données..."}
                            className="flex-1"
                        />
                        <Button type="submit">
                            <Send className="h-4 w-4" />
                        </Button>
                    </form>
                </div>
            </div>
        </>
    )
}
