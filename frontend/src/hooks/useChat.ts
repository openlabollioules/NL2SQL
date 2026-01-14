/**
 * useChat Hook
 * Manages WebSocket connection and chat state
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import type { Message } from '../types';

// WebSocket URL from environment or default
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/api/v1/ws/chat';

// Reconnection settings
const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

interface AgentState {
    node: string;
    content: string;
}

export function useChat(sqlMode: boolean, currentSessionId: string) {
    const [messages, setMessages] = useState<Message[]>([
        { role: 'assistant', content: 'Bonjour ! Je suis votre assistant Data Intelligence. Chargez un fichier CSV pour commencer.' }
    ]);
    const [agentState, setAgentState] = useState<AgentState | null>(null);
    const [isConnected, setIsConnected] = useState(false);

    // Use refs to avoid stale closures
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const reconnectAttemptsRef = useRef(0);

    /**
     * Parse incoming WebSocket message
     */
    const handleMessage = useCallback((event: MessageEvent) => {
        try {
            const payload = JSON.parse(event.data);

            // Handle thought/status messages
            if (payload.type === 'thought') {
                setAgentState({ node: payload.node, content: payload.content });
                return;
            }

            if (payload.type === 'status') {
                let nodeName = payload.content.replace('Next step: ', '');
                if (nodeName === 'FINISH') {
                    setAgentState(null);
                    return;
                }
                // Friendly node name mappings
                const nodeNameMap: Record<string, string> = {
                    'sql_planner': '🧠 Analyse de la demande & Planification SQL...',
                    'sql_executor': '⚡️ Exécution de la requête sur la base...',
                    'data_analyst': '📊 Analyse des résultats & Mise en forme...',
                    'csv_loader': '📂 Préparation du chargement de fichier...',
                    'supervisor': '🤖 Supervision & Routage...',
                    'chart_generator': '📈 Génération du graphique...'
                };
                nodeName = nodeNameMap[nodeName] || nodeName;
                setAgentState({ node: 'System', content: nodeName });
                return;
            }

            // Handle content messages
            let content = payload.content;

            if (typeof content === 'string') {
                // Try to parse embedded JSON
                try {
                    const jsonMatch = content.match(/\{[\s\S]*\}/);
                    if (jsonMatch) {
                        const parsedContent = JSON.parse(jsonMatch[0]);

                        if (parsedContent?.type === 'data_result') {
                            setMessages(prev => [...prev, {
                                role: 'assistant',
                                content: parsedContent.summary,
                                type: 'table',
                                tableData: {
                                    columns: parsedContent.columns,
                                    data: parsedContent.data
                                }
                            }]);
                            return;
                        }

                        if (parsedContent?.type === 'chart_result') {
                            setMessages(prev => [...prev, {
                                role: 'assistant',
                                content: "Voici le graphique demandé :",
                                type: 'chart',
                                chartConfig: parsedContent.config
                            }]);
                            return;
                        }

                        if (parsedContent?.type === 'chart_suggestions') {
                            setMessages(prev => [...prev, {
                                role: 'assistant',
                                content: "Voici quelques suggestions de graphiques :",
                                type: 'chart_suggestions',
                                suggestions: parsedContent.suggestions
                            }]);
                            return;
                        }
                    }
                } catch {
                    // Not valid JSON, treat as regular message
                }
            }

            // Regular text message
            setMessages(prev => [...prev, { role: 'assistant', content }]);

            // Clear agent state on error
            if (payload.node === 'sql_executor' && content.includes("Error")) {
                setAgentState(null);
            }

        } catch {
            // Raw non-JSON message
            console.log("Raw message:", event.data);
            setMessages(prev => [...prev, { role: 'assistant', content: event.data }]);
        }
    }, []);

    /**
     * Connect to WebSocket server
     */
    const connect = useCallback(() => {
        // Don't connect if we already have an open connection
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            return;
        }

        // Clean up any existing connection
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }

        const websocket = new WebSocket(WS_URL);
        wsRef.current = websocket;

        websocket.onopen = () => {
            console.log('Connected to WebSocket');
            setIsConnected(true);
            reconnectAttemptsRef.current = 0;
        };

        websocket.onmessage = handleMessage;

        websocket.onclose = (event) => {
            console.log('WebSocket disconnected:', event.code, event.reason);
            setIsConnected(false);
            wsRef.current = null;

            // Only reconnect if not a clean close and under max attempts
            if (!event.wasClean && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttemptsRef.current += 1;
                console.log(`Reconnecting... attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS}`);
                reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
            }
        };

        websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            websocket.close();
        };
    }, [handleMessage]);

    /**
     * Initialize WebSocket connection on mount
     */
    useEffect(() => {
        connect();

        // Cleanup on unmount - use refs to avoid stale closures
        return () => {
            if (reconnectTimerRef.current) {
                clearTimeout(reconnectTimerRef.current);
                reconnectTimerRef.current = null;
            }
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [connect]);

    /**
     * Send a message through WebSocket
     */
    const sendMessage = useCallback((text: string) => {
        if (!text.trim()) return;

        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: "Erreur: Non connecté au serveur. Veuillez rafraîchir la page."
            }]);
            return;
        }

        // Add user message to UI
        setMessages(prev => [...prev, { role: 'user', content: text }]);

        // Send to server
        wsRef.current.send(JSON.stringify({
            content: text,
            mode: sqlMode ? 'sql' : 'chat',
            session_id: currentSessionId
        }));
    }, [sqlMode, currentSessionId]);

    /**
     * Manually reconnect to WebSocket
     */
    const reconnect = useCallback(() => {
        reconnectAttemptsRef.current = 0;
        connect();
    }, [connect]);

    return {
        messages,
        setMessages,
        sendMessage,
        agentState,
        setAgentState,
        isConnected,
        reconnect
    };
}
