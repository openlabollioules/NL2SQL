from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except RuntimeError:
            # Connection already closed
            pass
        except Exception as e:
            print(f"Error sending message: {e}")

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

from app.services.agent_service import agent_service

@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            
            # Try to parse as JSON, fallback to string for backward compatibility
            import json
            try:
                payload = json.loads(data)
                content = payload.get("content", "")
                mode = payload.get("mode", "chat")
                session_id = payload.get("session_id", "default")
            except json.JSONDecodeError:
                content = data
                mode = "chat"
                session_id = "default"
            
            try:
                async for response in agent_service.process_message(content, session_id, mode):
                     await manager.send_personal_message(response, websocket)
            except RuntimeError:
                # Stop processing if connection closes during streaming
                break
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Error in agent processing: {e}")
                await manager.send_personal_message(json.dumps({"type": "error", "content": str(e)}), websocket)
                 
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        try:
            await manager.broadcast("Client #left")
        except Exception:
            pass
    except Exception as e:
        print(f"WebSocket Error: {e}")
        manager.disconnect(websocket)
