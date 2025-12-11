# Cashout IA - Frontend

Modern React frontend for the Cashout IA data analysis platform.

## Features

- **Chat Interface**: Interact with your data using natural language.
- **SQL Mode**: Execute SQL queries directly.
- **Visualizations**: Auto-generated Plotly charts and improvements.
- **Data Explorer**: View and manage uploaded tables and their schemas.
- **Modeling Tool**: Visual relationship builder (Entity-Relationship Diagram).
- **Architecture**: Modular design with Custom Hooks (`useChat`, `useData`) and `react-router-dom`.

## Tech Stack

- **React** 18
- **TypeScript**
- **Vite**
- **Tailwind CSS**
- **Radix UI** / **Lucide React**

## Setup

1. **Install Dependencies**:
   ```bash
   npm install
   ```

2. **Run Development Server**:
   ```bash
   npm run dev
   ```

The app will be available at `http://localhost:5173`.

## Architecture

- `src/components`: UI components (Sidebar, Layouts, Chat).
- `src/hooks`: Application logic (WebSocket, Data fetching).
- `src/pages`: Page views (Chat, Data, Modeling).
- `src/services`: API client.
