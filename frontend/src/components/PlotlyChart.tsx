import { useEffect, useRef, useCallback } from 'react';
import Plotly from 'plotly.js-basic-dist-min';

interface PlotlyChartProps {
    data: Plotly.Data[];
    layout?: Partial<Plotly.Layout>;
    style?: React.CSSProperties;
    useResizeHandler?: boolean;
}

export function PlotlyChart({ data, layout = {}, style, useResizeHandler = true }: PlotlyChartProps) {
    const containerRef = useRef<HTMLDivElement>(null);

    const handleResize = useCallback(() => {
        if (containerRef.current) {
            Plotly.Plots.resize(containerRef.current);
        }
    }, []);

    useEffect(() => {
        if (!containerRef.current) return;

        const finalLayout: Partial<Plotly.Layout> = {
            ...layout,
            autosize: true,
        };

        Plotly.newPlot(containerRef.current, data, finalLayout, {
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
        });

        // Cleanup
        return () => {
            if (containerRef.current) {
                Plotly.purge(containerRef.current);
            }
        };
    }, [data, layout]);

    useEffect(() => {
        if (!useResizeHandler) return;

        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [useResizeHandler, handleResize]);

    return <div ref={containerRef} style={style} />;
}
