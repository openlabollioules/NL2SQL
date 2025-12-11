from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
import operator

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_step: str
    sql_query: str
    mode: str
    pending_chart_request: Union[str, None]  # Stores the chart request if we need to fetch data first

class AgentService:
    def __init__(self):
        self.workflow = StateGraph(AgentState)
        self._setup_graph()
        self.app = self.workflow.compile()

    def _setup_graph(self):
        # Define nodes
        self.workflow.add_node("supervisor", self.supervisor_node)
        self.workflow.add_node("csv_loader", self.csv_loader_node)
        self.workflow.add_node("sql_planner", self.sql_planner_node)
        self.workflow.add_node("sql_executor", self.sql_executor_node)
        self.workflow.add_node("data_analyst", self.data_analyst_node)
        self.workflow.add_node("chart_generator", self.chart_generator_node)

        # Define edges
        self.workflow.set_entry_point("supervisor")
        self.workflow.add_conditional_edges(
            "supervisor",
            lambda x: x["next_step"],
            {
                "csv_loader": "csv_loader",
                "sql_planner": "sql_planner",
                "data_analyst": "data_analyst",
                "chart_generator": "chart_generator",
                "FINISH": END
            }
        )
        self.workflow.add_edge("csv_loader", "supervisor")
        self.workflow.add_edge("sql_planner", "sql_executor")
        self.workflow.add_edge("sql_executor", "data_analyst")
        
        # Data Analyst can route back to chart_generator if a chart was pending
        self.workflow.add_conditional_edges(
            "data_analyst",
            lambda x: "chart_generator" if x.get("pending_chart_request") else "supervisor",
            {
                "chart_generator": "chart_generator",
                "supervisor": "supervisor"
            }
        )
        
        self.workflow.add_conditional_edges(
            "chart_generator",
            lambda x: x.get("next_step", "supervisor"),
            {
                "sql_planner": "sql_planner",
                "supervisor": "supervisor",
                "chart_generator": "supervisor" # Safety net: if it loops onto itself, break to supervisor
            }
        )

    # ... supervisor_node and csv_loader_node remain unchanged ...

    def sql_planner_node(self, state: AgentState):
        from app.services.ollama_service import ollama_service
        from app.services.duckdb_service import get_duckdb_service
        from app.services.vector_store import vector_store
        from langchain_core.prompts import ChatPromptTemplate

        schema = get_duckdb_service().get_all_schemas()
        messages = state["messages"]
        
        # If we are here because of a pending chart request, use that as the user message
        pending_request = state.get("pending_chart_request")
        last_user_message = pending_request if pending_request else messages[-1].content
        
        # Retrieve relevant context from Vector Store
        context_results = vector_store.query(last_user_message, n_results=3)
        context_str = "\n".join(context_results['documents'][0]) if context_results['documents'] else ""

        from app.services.relationship_service import relationship_service
        
        manual_relationships = relationship_service.get_formatted_relationships()
        
        print(f"DEBUG: Schema passed to SQL Agent: {schema}")
        
        system_message = f"""You are a DuckDB SQL expert. 
        
        Schema:
        {schema}
        
        Defined Relationships (High Priority):
        {manual_relationships}
        
        Task: Generate a valid DuckDB SQL query to answer the user's question.
        
        CRITICAL RULES:
        1. Return ONLY the SQL query. NO explanations, NO markdown.
        2. DO NOT output Python, Pandas, or any other code. ONLY SQL.
        3. Use the provided Schema and Defined Relationships to construct the query.
        4. If the user asks about multiple entities, use JOINs based on the Defined Relationships.
        5. If the question is "biggest" or "largest", usually order by a relevant numeric column DESC LIMIT 1.
        6. START DIRECTLY with "SELECT" or "WITH".
        """
        
        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=last_user_message)
        ]
        
        # Use chat_llm (Qwen) as it follows instructions better than the current sqlcoder for this context
        # sqlcoder was hallucinating external schemas
        
        response = ollama_service.chat_llm.invoke(messages)
        sql_query = response.content.strip()
        
        # Clean up markdown code blocks if present
        if sql_query.startswith("```"):
            sql_query = sql_query.split("\n", 1)[1]
            if sql_query.endswith("```"):
                sql_query = sql_query.rsplit("\n", 1)[0]
        
        return {"messages": [AIMessage(content=f"Planning SQL: {sql_query}")], "sql_query": sql_query}

    # ... sql_executor_node remains unchanged ...

    def chart_generator_node(self, state: AgentState):
        import json
        from app.services.ollama_service import ollama_service
        
        print("DEBUG: Entering chart_generator_node")
        
        # We need the last data result to generate a chart
        # Iterate backwards to find the last data_result
        messages = state["messages"]
        last_data = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content.startswith('{'):
                try:
                    data = json.loads(msg.content)
                    if data.get("type") == "data_result":
                        last_data = data
                        break
                except:
                    continue
        
        # If no data found, we need to fetch it first!
        if not last_data:
            print("DEBUG: No data found, routing to sql_planner")
            # Check if we already tried to fetch data (avoid infinite loop)
            # We can check if the last message was from us saying we need data, but state is cleaner.
            # If pending_chart_request is ALREADY set, it means we looped back but still no data?
            # Or maybe we just arrived here.
            
            # Let's set the pending request and route to sql_planner
            user_request = messages[-1].content
            return {
                "messages": [AIMessage(content="Je n'ai pas de données pour ce graphique. Je vais d'abord exécuter une requête SQL pour les récupérer.")],
                "pending_chart_request": user_request,
                "next_step": "sql_planner"
            }
            
        print("DEBUG: Data found, generating chart")
        # Generate Plotly JSON configuration using LLM
        # Use pending_chart_request if available, otherwise last message
        user_request = state.get("pending_chart_request") or messages[-1].content
        
        system_prompt = f"""You are a Data Visualization Expert using Plotly.js.
        
        Data Columns: {last_data['columns']}
        Data Sample (first 3 rows): {last_data['data'][:3]}
        User Request: "{user_request}"
        
        Task: Generate a valid Plotly JSON configuration (data and layout) to visualize this data.
        
        CRITICAL RULES:
        1. Return ONLY the JSON object. NO markdown, NO explanations.
        2. The JSON must have "data" (array) and "layout" (object) keys.
        3. Use "x" and "y" keys in "data" mapped to the correct column names from the data.
        4. Since you don't have the full data arrays, use placeholders like "__COLUMN_NAME__" for the x and y arrays. 
           The backend will replace these placeholders with the actual data arrays.
           Example: "x": "__Date__", "y": "__Sales__"
        5. Make the chart interactive and beautiful (dark mode compatible if possible).
        """
        
        try:
            response = ollama_service.generate_response([SystemMessage(content=system_prompt)])
            plotly_config_str = response.content.strip()
            
            # Clean markdown
            if plotly_config_str.startswith("```"):
                plotly_config_str = plotly_config_str.split("\n", 1)[1]
                if plotly_config_str.endswith("```"):
                    plotly_config_str = plotly_config_str.rsplit("\n", 1)[0]
            
            plotly_config = json.loads(plotly_config_str)
            
            # Inject actual data
            # We need to pivot the row-based data to column-based arrays
            columns = last_data['columns']
            rows = last_data['data']
            
            # Create a dict of arrays: { "col1": [1, 2], "col2": [3, 4] }
            col_data = {col: [row[col] for row in rows] for col in columns}
            
            # Recursively replace placeholders in the plotly config
            def inject_data(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if isinstance(v, str) and v.startswith("__") and v.endswith("__"):
                            col_name = v[2:-2]
                            if col_name in col_data:
                                obj[k] = col_data[col_name]
                        else:
                            inject_data(v)
                elif isinstance(obj, list):
                    for item in obj:
                        inject_data(item)
            
            inject_data(plotly_config)
            
            response_data = {
                "type": "chart_result",
                "config": plotly_config
            }
            
            print("DEBUG: Chart generated, routing to supervisor")
            # Clear pending request after success
            return {
                "messages": [AIMessage(content=json.dumps(response_data))],
                "pending_chart_request": None, # Reset
                "next_step": "supervisor"
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"DEBUG: Chart generation error: {e}")
            return {
                "messages": [AIMessage(content=f"Erreur lors de la génération du graphique : {str(e)}")],
                "next_step": "supervisor"
            }

    def data_analyst_node(self, state: AgentState):
        # If in SQL mode, do not generate conversational analysis
        if state.get("mode") == "sql":
            return {}
            
        pending_request = state.get("pending_chart_request")
        print(f"DEBUG: Data Analyst - Pending Chart Request: {pending_request}")

        # If we have a pending chart request, skip analysis and go back to chart generator
        # The SQL Executor has just finished providing data.
        if pending_request:
            print("DEBUG: Data Analyst - Skipping analysis due to pending chart request")
            return {} # Pass through to edge logic

        from app.services.ollama_service import ollama_service
        from app.services.duckdb_service import duckdb_service
        
        # Provide schema context to the analyst
        schema = duckdb_service.get_all_schemas()
        
        messages = state["messages"]
        last_message = messages[-1]
        
        # If the last message is a data_result (from sql_executor), we need to interpret it
        # If it's a human message, we answer it directly (e.g. metadata question)
        
        system_prompt = f"""You are a helpful Data Analyst.
        You have access to the following database schema:
        {schema}
        
        If the user asks about the data structure, describe the tables and columns available.
        If the user provides data results, interpret them concisely.
        
        CRITICAL INSTRUCTION:
        1. YOU MUST ANSWER IN FRENCH ONLY. (RÉPONDRE UNIQUEMENT EN FRANÇAIS).
        2. DO NOT output English text.
        3. DO NOT output internal artifacts like '__{{...}}__'.
        4. Be concise and professional.
        """
        
        # Construct a new message list with system prompt
        full_messages = [SystemMessage(content=system_prompt)] + messages
        
        response = ollama_service.generate_response(full_messages)
        return {"messages": [response]}

    def supervisor_node(self, state: AgentState):
        from app.services.ollama_service import ollama_service
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = state["messages"]
        last_message = messages[-1]
        
        if isinstance(last_message, HumanMessage):
            content = last_message.content.lower()
            
            # Direct keyword overrides for speed/reliability
            if "load" in content or "charge" in content or "upload" in content:
                return {"next_step": "csv_loader"}
            if "finish" in content or "stop" in content:
                return {"next_step": "FINISH"}
            if "finish" in content or "stop" in content:
                return {"next_step": "FINISH"}
            
            # Check if it's already a chart result (avoid loop)
            if "type" in content and "chart_result" in content:
                return {"next_step": "FINISH"}

            if "chart" in content or "graph" in content or "plot" in content or "trace" in content or "dessine" in content:
                return {"next_step": "chart_generator"}
                
            # LLM Classification for ambiguous cases
            prompt = f"""You are a supervisor routing a user request to the correct worker.
            Available workers:
            - 'csv_loader': If the user wants to load, upload, or charge a file.
            - 'sql_planner': If the user explicitly asks to QUERY the data, calculate statistics, or asks "how many", "sum of", "average", "show me".
            - 'data_analyst': If the user asks general questions about the data structure (e.g. "what is in the data", "describe the tables"), or just wants to chat/say hello.
            - 'chart_generator': If the user asks to visualize data, draw a chart, plot a graph, or "show me the distribution".
            
            User Request: "{last_message.content}"
            
            Return ONLY the worker name (csv_loader, sql_planner, data_analyst, or chart_generator). Do not add any punctuation or explanation."""
            
            try:
                response = ollama_service.generate_response([HumanMessage(content=prompt)])
                decision = response.content.strip().lower()
                
                # Fallback if LLM is chatty
                if "sql" in decision or "planner" in decision:
                    return {"next_step": "sql_planner"}
                if "loader" in decision:
                    return {"next_step": "csv_loader"}
                if "analyst" in decision:
                    return {"next_step": "data_analyst"}
                if "chart" in decision or "graph" in decision:
                    return {"next_step": "chart_generator"}
                    
                # Default to analyst if unclear
                return {"next_step": "data_analyst"}
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Routing error: {e}")
                return {"next_step": "data_analyst"}
                
        print(f"DEBUG: Supervisor decision: {last_message.content} -> FINISH")
        return {"next_step": "FINISH"}

    def csv_loader_node(self, state: AgentState):
        return {"messages": [AIMessage(content="CSV Loader: I can help you load data. Please upload a file.")]}

    def sql_planner_node(self, state: AgentState):
        from app.services.ollama_service import ollama_service
        from app.services.duckdb_service import get_duckdb_service
        from app.services.vector_store import vector_store
        from langchain_core.prompts import ChatPromptTemplate

        schema = get_duckdb_service().get_all_schemas()
        messages = state["messages"]
        last_user_message = messages[-1].content
        
        # Retrieve relevant context from Vector Store
        context_results = vector_store.query(last_user_message, n_results=3)
        context_str = "\n".join(context_results['documents'][0]) if context_results['documents'] else ""

        from app.services.relationship_service import relationship_service
        
        manual_relationships = relationship_service.get_formatted_relationships()
        
        print(f"DEBUG: Schema passed to SQL Agent: {schema}")
        
        system_message = f"""You are a DuckDB SQL expert. 
        
        Schema:
        {schema}
        
        Defined Relationships (High Priority):
        {manual_relationships}
        
        Task: Generate a valid DuckDB SQL query to answer the user's question.
        
        CRITICAL RULES:
        1. Return ONLY the SQL query. NO explanations, NO markdown.
        2. DO NOT output Python, Pandas, or any other code. ONLY SQL.
        3. Use the provided Schema and Defined Relationships to construct the query.
        4. If the user asks about multiple entities, use JOINs based on the Defined Relationships.
        5. If the question is "biggest" or "largest", usually order by a relevant numeric column DESC LIMIT 1.
        6. START DIRECTLY with "SELECT" or "WITH".
        """
        
        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=last_user_message)
        ]
        
        # Use chat_llm (Qwen) as it follows instructions better than the current sqlcoder for this context
        # sqlcoder was hallucinating external schemas
        
        response = ollama_service.chat_llm.invoke(messages)
        sql_query = response.content.strip()
        
        # Clean up markdown code blocks if present
        if sql_query.startswith("```"):
            sql_query = sql_query.split("\n", 1)[1]
            if sql_query.endswith("```"):
                sql_query = sql_query.rsplit("\n", 1)[0]
        
        return {"messages": [AIMessage(content=f"Planning SQL: {sql_query}")], "sql_query": sql_query}

    def sql_executor_node(self, state: AgentState):
        from app.services.duckdb_service import get_duckdb_service
        import json
        
        sql_query = state.get("sql_query")
        if not sql_query:
            return {"messages": [AIMessage(content="Error: No SQL query generated.")]}
        
        try:
            results = get_duckdb_service().execute_query(sql_query)
            # results is now {"columns": [...], "data": [...]}
            
            # Create a structured message
            response_data = {
                "type": "data_result",
                "summary": f"Executed query: {sql_query}",
                "columns": results["columns"],
                "data": results["data"]
            }
            
            return {"messages": [AIMessage(content=json.dumps(response_data))]}
        except Exception as e:
            return {"messages": [AIMessage(content=f"SQL Execution Error: {str(e)}")]}

    def chart_generator_node(self, state: AgentState):
        from app.services.ollama_service import ollama_service
        import json
        
        # We need the last data result to generate a chart
        # Iterate backwards to find the last data_result
        messages = state["messages"]
        last_data = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content.startswith('{'):
                try:
                    data = json.loads(msg.content)
                    if data.get("type") == "data_result":
                        last_data = data
                        break
                except:
                    continue
        
        # If no data found, we need to fetch it first!
        if not last_data:
            print("DEBUG: No data found, routing to sql_planner")
            
            # Let's set the pending request and route to sql_planner
            user_request = messages[-1].content
            return {
                "messages": [AIMessage(content="Je n'ai pas de données pour ce graphique. Je vais d'abord exécuter une requête SQL pour les récupérer.")],
                "pending_chart_request": user_request,
                "next_step": "sql_planner"
            }
            
        user_request = messages[-1].content
        
        # Check if request is generic (asking for suggestions)
        # Or if it comes from the "Generate Graph" button which is "Génère un graphique pour ces données"
        is_generic = False
        lower_request = user_request.lower()
        if "génère un graphique" in lower_request or "standard" in lower_request or len(lower_request) < 50:
             # Basic heuristic: short request or specific keywords = suggestion needed
             # Unless it contains specific types like "camembert", "barres", "ligne", "pie", "bar", "line"
             if not any(t in lower_request for t in ["camembert", "barres", "ligne", "pie", "bar", "line", "scatter", "nuage"]):
                 is_generic = True
        
        if is_generic:
            print("DEBUG: Generic request detected, generating suggestions")
            suggestion_prompt = f"""You are a Data Visualization Expert.
            Data Columns: {last_data['columns']}
            Data Sample: {last_data['data'][:3]}
            
            Task: Suggest 3 to 4 varied and relevant charts to visualize this data.
            
            Return a JSON array of objects with keys:
            - "title": Short descriptive title (e.g. "Distribution des ventes par pays")
            - "type": Chart type (bar, line, pie, scatter, etc.)
            - "description": Why this chart is useful (1 sentence)
            - "intent": A specific user query that would generate this chart (e.g. "Trace un camembert des ventes par pays")
            
            IMPORTANT: Return ONLY the JSON array. Output in FRENCH.
            """
            try:
                response = ollama_service.generate_response([SystemMessage(content=suggestion_prompt)])
                suggestions_str = response.content.strip()
                
                # Check for markdown code blocks
                if suggestions_str.startswith("```"):
                    suggestions_str = suggestions_str.split("\n", 1)[1]
                    if suggestions_str.endswith("```"):
                        suggestions_str = suggestions_str.rsplit("\n", 1)[0]
                
                suggestions = json.loads(suggestions_str)
                return {
                    "messages": [AIMessage(content=json.dumps({
                        "type": "chart_suggestions",
                        "suggestions": suggestions
                    }))],
                    "pending_chart_request": None,
                    "next_step": "supervisor"
                }
            except Exception as e:
                print(f"DEBUG: Suggestion generation failed: {e}")
                # Fallback to standard generation
        
        # Standard Generation (Specific Request)
        print("DEBUG: Specific request detected, generating chart")
        system_prompt = f"""You are a Data Visualization Expert using Plotly.js.
        
        Data Columns: {last_data['columns']}
        Data Sample (first 3 rows): {last_data['data'][:3]}
        User Request: "{user_request}"
        
        Task: Generate a valid Plotly JSON configuration (data and layout) to visualize this data.
        
        CRITICAL RULES:
        1. Return ONLY the JSON object. NO markdown, NO explanations.
        2. The JSON must have "data" (array) and "layout" (object) keys.
        3. Use "x" and "y" keys in "data" mapped to the correct column names from the data.
        4. Since you don't have the full data arrays, use placeholders like "__COLUMN_NAME__" for the x and y arrays. 
           The backend will replace these placeholders with the actual data arrays.
           Example: "x": "__Date__", "y": "__Sales__"
        5. Make the chart interactive and beautiful (dark mode compatible if possible).
        """
        
        try:
            response = ollama_service.generate_response([SystemMessage(content=system_prompt)])
            plotly_config_str = response.content.strip()
            
            # Clean markdown
            if plotly_config_str.startswith("```"):
                plotly_config_str = plotly_config_str.split("\n", 1)[1]
                if plotly_config_str.endswith("```"):
                    plotly_config_str = plotly_config_str.rsplit("\n", 1)[0]
            
            plotly_config = json.loads(plotly_config_str)
            
            # Inject actual data
            # We need to pivot the row-based data to column-based arrays
            columns = last_data['columns']
            rows = last_data['data']
            
            # Create a dict of arrays: { "col1": [1, 2], "col2": [3, 4] }
            col_data = {col: [row[col] for row in rows] for col in columns}
            
            # Recursively replace placeholders in the plotly config
            def inject_data(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if isinstance(v, str) and v.startswith("__") and v.endswith("__"):
                            col_name = v[2:-2]
                            if col_name in col_data:
                                obj[k] = col_data[col_name]
                        else:
                            inject_data(v)
                elif isinstance(obj, list):
                    for item in obj:
                        inject_data(item)
            
            inject_data(plotly_config)
            
            response_data = {
                "type": "chart_result",
                "config": plotly_config
            }
            
            return {"messages": [AIMessage(content=json.dumps(response_data))], "pending_chart_request": None, "next_step": "supervisor"}
            
        except Exception as e:
            return {"messages": [AIMessage(content=f"Erreur lors de la génération du graphique : {str(e)}")]}

    def data_analyst_node(self, state: AgentState):
        # If in SQL mode, do not generate conversational analysis
        if state.get("mode") == "sql":
            return {}
            
        pending_request = state.get("pending_chart_request")
        print(f"DEBUG: Data Analyst - Pending Chart Request: {pending_request}")

        # If we have a pending chart request, skip analysis and go back to chart generator
        # The SQL Executor has just finished providing data.
        if pending_request:
            print("DEBUG: Data Analyst - Skipping analysis due to pending chart request")
            return {} # Pass through to edge logic

        from app.services.ollama_service import ollama_service
        from app.services.duckdb_service import get_duckdb_service
        
        # Provide schema context to the analyst
        schema = get_duckdb_service().get_all_schemas()
        
        messages = state["messages"]
        last_message = messages[-1]
        
        # If the last message is a data_result (from sql_executor), we need to interpret it
        # If it's a human message, we answer it directly (e.g. metadata question)
        
        system_prompt = f"""You are a helpful Data Analyst.
        You have access to the following database schema:
        {schema}
        
        If the user asks about the data structure, describe the tables and columns available.
        If the user provides data results, interpret them concisely.
        
        CRITICAL INSTRUCTION:
        1. YOU MUST ANSWER IN FRENCH ONLY. (RÉPONDRE UNIQUEMENT EN FRANÇAIS).
        2. DO NOT output English text.
        3. DO NOT output internal artifacts like '__{{...}}__'.
        4. Be concise and professional.
        """
        
        # Construct a new message list with system prompt
        full_messages = [SystemMessage(content=system_prompt)] + messages
        
        response = ollama_service.generate_response(full_messages)
        return {"messages": [response]}

    async def process_message(self, message: str, session_id: str = "default", mode: str = "chat"):
        # Save user message
        from app.services.history_service import history_service
        history_service.add_message(session_id, "user", message)
        
        # Load history to provide context (e.g. for charts)
        history = history_service.get_messages(session_id)
        
        # Convert to LangChain messages
        langchain_messages = []
        for msg in history:
            if msg['role'] == 'user':
                langchain_messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                langchain_messages.append(AIMessage(content=msg['content']))
            elif msg['role'] == 'system':
                langchain_messages.append(SystemMessage(content=msg['content']))
        
        # We don't need to append the current message again if it was just added to history?
        # history_service.add_message appended it to DB. get_messages retrieves it.
        # So langchain_messages ALREADY includes the current message at the end.
        
        inputs = {"messages": langchain_messages, "mode": mode}
        
        async for output in self.app.astream(inputs):
            for key, value in output.items():
                if value:
                    import json
                    # Check for next_step (from supervisor)
                    if "next_step" in value:
                        yield json.dumps({
                            "type": "status",
                            "node": key,
                            "content": f"Next step: {value['next_step']}"
                        })
                    
                    # Check for messages
                    if "messages" in value:
                        content = value["messages"][-1].content
                        
                        # Determine event type based on node
                        event_type = "message"
                        if key in ["supervisor", "sql_planner", "csv_loader"]:
                            event_type = "thought"
                        elif key == "sql_executor":
                            event_type = "message"
                        elif key == "chart_generator":
                            event_type = "message"
                        
                        # Save to history if it's a final message or important step
                        # We save everything for now, but frontend might filter
                        # Ideally we save:
                        # 1. User message (already handled at start of process_message?) No, we need to handle it.
                        # 2. Final answer (data_analyst)
                        # 3. Intermediate thoughts (as metadata or separate messages?)
                        
                        # Let's save the final answer from data_analyst as the assistant response
                        if key == "data_analyst":
                             from app.services.history_service import history_service
                             history_service.add_message(session_id, "assistant", content)

                        # Also save the SQL execution result (table data)
                        if key == "sql_executor":
                             from app.services.history_service import history_service
                             history_service.add_message(session_id, "assistant", content)

                        # Save chart result
                        if key == "chart_generator":
                             from app.services.history_service import history_service
                             history_service.add_message(session_id, "assistant", content)

                        yield json.dumps({
                            "type": event_type,
                            "node": key,
                            "content": content
                        })

agent_service = AgentService()
