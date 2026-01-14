declare module 'plotly.js-basic-dist-min' {
    import type { Data, Layout, Config, PlotlyHTMLElement } from 'plotly.js';
    
    export type { Data, Layout, Config, PlotlyHTMLElement };
    
    export function newPlot(
        root: HTMLElement | string,
        data: Data[],
        layout?: Partial<Layout>,
        config?: Partial<Config>
    ): Promise<PlotlyHTMLElement>;
    
    export function purge(root: HTMLElement | string): void;
    
    export const Plots: {
        resize(root: HTMLElement | string): void;
    };
}
