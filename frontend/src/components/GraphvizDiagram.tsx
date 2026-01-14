import React, { useEffect, useRef, useState, useCallback } from 'react';
import { instance, type Viz } from '@viz-js/viz';
import { ZoomIn, ZoomOut, RotateCcw, Download } from 'lucide-react';
import { Button } from "@/components/ui/button";

interface GraphvizDiagramProps {
    dot: string;
}

export const GraphvizDiagram: React.FC<GraphvizDiagramProps> = ({ dot }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const vizRef = useRef<Viz | null>(null);
    const [scale, setScale] = useState(1);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    // Initialize Viz.js instance once
    useEffect(() => {
        let mounted = true;
        
        instance().then(viz => {
            if (mounted) {
                vizRef.current = viz;
                setIsLoading(false);
            }
        }).catch(err => {
            if (mounted) {
                setError(`Erreur d'initialisation Graphviz: ${err.message}`);
                setIsLoading(false);
            }
        });

        return () => { mounted = false; };
    }, []);

    // Render the diagram when DOT string changes
    useEffect(() => {
        if (!vizRef.current || !containerRef.current || !dot) return;

        try {
            setError(null);
            const svg = vizRef.current.renderSVGElement(dot);
            
            // Apply styles to the SVG
            svg.style.width = '100%';
            svg.style.height = 'auto';
            svg.style.maxWidth = 'none';
            
            // Clear and append
            containerRef.current.innerHTML = '';
            containerRef.current.appendChild(svg);
        } catch (err) {
            console.error("Graphviz render error:", err);
            setError(`Erreur de rendu du diagramme: ${err instanceof Error ? err.message : String(err)}`);
        }
    }, [dot, isLoading]);

    const handleZoomIn = useCallback(() => setScale(prev => Math.min(prev + 0.1, 3)), []);
    const handleZoomOut = useCallback(() => setScale(prev => Math.max(prev - 0.1, 0.3)), []);
    const handleReset = useCallback(() => setScale(1), []);

    const handleDownload = useCallback(() => {
        if (!containerRef.current) return;
        
        const svg = containerRef.current.querySelector('svg');
        if (!svg) return;

        const serializer = new XMLSerializer();
        const svgString = serializer.serializeToString(svg);
        const blob = new Blob([svgString], { type: 'image/svg+xml' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = 'schema-diagram.svg';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, []);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-full text-muted-foreground">
                <div className="flex flex-col items-center gap-2">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                    <span>Chargement de Graphviz...</span>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-red-500 p-4 border border-red-200 rounded-lg bg-red-50">
                    {error}
                </div>
            </div>
        );
    }

    return (
        <div className="relative w-full h-full flex flex-col">
            {/* Controls */}
            <div className="absolute top-2 right-2 flex gap-1 z-10 bg-background/80 backdrop-blur-sm p-1 rounded-md border shadow-sm">
                <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-8 w-8" 
                    onClick={handleZoomIn} 
                    title="Zoom avant"
                >
                    <ZoomIn className="h-4 w-4" />
                </Button>
                <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-8 w-8" 
                    onClick={handleZoomOut} 
                    title="Zoom arrière"
                >
                    <ZoomOut className="h-4 w-4" />
                </Button>
                <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-8 w-8" 
                    onClick={handleReset} 
                    title="Réinitialiser zoom"
                >
                    <RotateCcw className="h-4 w-4" />
                </Button>
                <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-8 w-8" 
                    onClick={handleDownload} 
                    title="Télécharger SVG"
                >
                    <Download className="h-4 w-4" />
                </Button>
            </div>

            {/* Diagram container */}
            <div className="flex-1 overflow-auto p-4 bg-white/50">
                <div
                    ref={containerRef}
                    className="origin-top-left transition-transform duration-200 ease-in-out"
                    style={{ transform: `scale(${scale})` }}
                />
            </div>
        </div>
    );
};
