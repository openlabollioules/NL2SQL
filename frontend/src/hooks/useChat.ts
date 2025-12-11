import { useState, useEffect } from 'react';
import type { Message } from '../types';

export function useChat(sqlMode: boolean, currentSessionId: string) {
    const [messages, setMessages] = useState<Message[]>([
        { role: 'assistant', content: 'Bonjour ! Je suis votre assistant Data Intelligence. Chargez un fichier CSV pour commencer.' }
    ]);
    const [ws, setWs] = useState<WebSocket | null>(null);
    const [agentState, setAgentState] = useState<{ node: string, content: string } | null>(null);

    useEffect(() => {
        let websocket: WebSocket | null = null;
        let reconnectTimer: any;

        const connectWebSocket = () => {
            // Use import.meta.env for configuring URL in real app, hardcode for now to match current behavior but prepared for refactor
            const WS_URL = 'ws://127.0.0.1:8000/api/v1/ws/chat';
            websocket = new WebSocket(WS_URL);

            websocket.onopen = () => {
                console.log('Connected to WebSocket');
                setWs(websocket);
            };

            websocket.onmessage = (event) => {
                try {
                    const payload = JSON.parse(event.data);

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
                        // Mappings
                        if (nodeName === 'sql_planner') nodeName = '🧠 Analyse de la demande & Planification SQL...';
                        else if (nodeName === 'sql_executor') nodeName = '⚡️ Exécution de la requête sur la base...';
                        else if (nodeName === 'data_analyst') nodeName = '📊 Analyse des résultats & Mise en forme...';
                        else if (nodeName === 'csv_loader') nodeName = '📂 Préparation du chargement de fichier...';
                        else if (nodeName === 'supervisor') nodeName = '🤖 Supervision & Routage...';

                        setAgentState({ node: 'System', content: nodeName });
                        return;
                    }

                    let content = payload.content;

                    if (typeof content === 'string') {
                        try {
                            const jsonMatch = content.match(/\{[\s\S]*\}/);
                            if (jsonMatch) {
                                const parsedContent = JSON.parse(jsonMatch[0]);
                                if (parsedContent?.type === 'data_result') {
                                    setMessages(prev => [...prev, {
                                        role: 'assistant',
                                        content: parsedContent.summary,
                                        type: 'table',
                                        tableData: { columns: parsedContent.columns, data: parsedContent.data }
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
                        } catch (e) { }
                    }

                    setMessages(prev => [...prev, { role: 'assistant', content: content }]);

                    if (payload.node === 'sql_executor' && content.includes("Error")) {
                        setAgentState(null);
                    }

                } catch (e) {
                    console.log("Raw message:", event.data);
                    setMessages(prev => [...prev, { role: 'assistant', content: event.data }]);
                }
            };

            websocket.onclose = () => {
                console.log('Disconnected, reconnecting...');
                setWs(null);
                reconnectTimer = setTimeout(connectWebSocket, 3000);
            };

            websocket.onerror = (err) => {
                console.error('WS Error', err);
                websocket?.close();
            }
        };

        connectWebSocket();

        return () => {
            if (ws) ws.close();
            clearTimeout(reconnectTimer);
        };
    }, []); // Run once on mount

    const sendMessage = (text: string) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            setMessages(prev => [...prev, { role: 'assistant', content: "Erreur: Non connecté au serveur." }]);
            return;
        }
        setMessages(prev => [...prev, { role: 'user', content: text }]);

        ws.send(JSON.stringify({
            content: text,
            mode: sqlMode ? 'sql' : 'chat',
            session_id: currentSessionId
        }));
    };

    return { messages, setMessages, sendMessage, agentState, setAgentState, ws };
}
