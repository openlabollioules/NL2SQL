import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';
import { Button } from "@/components/ui/button";

mermaid.initialize({
    startOnLoad: true,
    theme: 'default',
    securityLevel: 'loose',
});

interface MermaidDiagramProps {
    chart: string;
}

export const MermaidDiagram: React.FC<MermaidDiagramProps> = ({ chart }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [scale, setScale] = useState(1);

    useEffect(() => {
        if (containerRef.current && chart) {
            try {
                mermaid.render(`mermaid-${Date.now()}`, chart).then(({ svg }) => {
                    if (containerRef.current) {
                        containerRef.current.innerHTML = svg;
                    }
                }).catch(error => {
                    console.error("Mermaid render error:", error);
                    if (containerRef.current) {
                        containerRef.current.innerHTML = `<div class="text-red-500 p-4">Erreur d'affichage du diagramme: ${error.message}</div>`;
                    }
                });
            } catch (e) {
                console.error("Mermaid sync error:", e);
            }
        }
    }, [chart]);

    const handleZoomIn = () => setScale(prev => Math.min(prev + 0.1, 3));
    const handleZoomOut = () => setScale(prev => Math.max(prev - 0.1, 0.5));
    const handleReset = () => setScale(1);

    return (
        <div className="relative w-full h-full flex flex-col">
            <div className="absolute top-2 right-2 flex gap-1 z-10 bg-background/80 backdrop-blur-sm p-1 rounded-md border shadow-sm">
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleZoomIn} title="Zoom In">
                    <ZoomIn className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleZoomOut} title="Zoom Out">
                    <ZoomOut className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleReset} title="Reset Zoom">
                    <RotateCcw className="h-4 w-4" />
                </Button>
            </div>
            <div className="flex-1 overflow-auto p-4 bg-white/50">
                <div
                    ref={containerRef}
                    className="mermaid origin-top-left transition-transform duration-200 ease-in-out"
                    style={{ transform: `scale(${scale})` }}
                />
            </div>
        </div>
    );
};
