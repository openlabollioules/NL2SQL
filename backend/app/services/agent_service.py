"""
Agent Service - LangGraph-based NL2SQL Agent
Orchestrates the workflow between different specialized nodes.
"""
import logging
import json
import re
from typing import TypedDict, Annotated, List, Union

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
import operator

# Configure logging
logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State schema for the agent workflow."""
    messages: Annotated[List[BaseMessage], operator.add]
    next_step: str
    sql_query: str
    mode: str
    pending_chart_request: Union[str, None]  # Stores the chart request if we need to fetch data first
    sql_error: Union[str, None]  # Stores SQL error for retry
    sql_retry_count: int  # Track retry attempts
    # New: Schema analysis results
    resolved_concepts: Union[dict, None]  # Semantic column mappings
    query_structure: Union[dict, None]  # Suggested query structure
    original_user_query: Union[str, None]  # Keep original query for corrections


class AgentService:
    """Main agent service orchestrating the NL2SQL workflow."""
    
    def __init__(self):
        self.workflow = StateGraph(AgentState)
        self._setup_graph()
        self.app = self.workflow.compile()

    def _setup_graph(self):
        """Configure the LangGraph workflow nodes and edges."""
        # Define nodes
        self.workflow.add_node("supervisor", self.supervisor_node)
        self.workflow.add_node("csv_loader", self.csv_loader_node)
        self.workflow.add_node("schema_analyzer", self.schema_analyzer_node)  # NEW
        self.workflow.add_node("sql_planner", self.sql_planner_node)
        self.workflow.add_node("sql_validator", self.sql_validator_node)  # NEW
        self.workflow.add_node("sql_executor", self.sql_executor_node)
        self.workflow.add_node("sql_corrector", self.sql_corrector_node)  # NEW
        self.workflow.add_node("data_analyst", self.data_analyst_node)
        self.workflow.add_node("chart_generator", self.chart_generator_node)

        # Define edges
        self.workflow.set_entry_point("supervisor")
        self.workflow.add_conditional_edges(
            "supervisor",
            lambda x: x["next_step"],
            {
                "csv_loader": "csv_loader",
                "sql_planner": "schema_analyzer",  # Route to schema_analyzer first
                "data_analyst": "data_analyst",
                "chart_generator": "chart_generator",
                "FINISH": END
            }
        )
        self.workflow.add_edge("csv_loader", "supervisor")
        
        # Schema analyzer -> SQL planner
        self.workflow.add_edge("schema_analyzer", "sql_planner")
        
        # SQL planner -> SQL validator
        self.workflow.add_edge("sql_planner", "sql_validator")
        
        # SQL validator routes to executor if valid, corrector if not
        self.workflow.add_conditional_edges(
            "sql_validator",
            lambda x: "sql_executor" if x.get("next_step") == "execute" else "sql_corrector",
            {
                "sql_executor": "sql_executor",
                "sql_corrector": "sql_corrector"
            }
        )
        
        # SQL corrector routes back to validator or gives up
        self.workflow.add_conditional_edges(
            "sql_corrector",
            lambda x: x.get("next_step", "data_analyst"),
            {
                "sql_validator": "sql_validator",
                "data_analyst": "data_analyst"
            }
        )
        
        # SQL executor can retry on error or proceed to analyst
        self.workflow.add_conditional_edges(
            "sql_executor",
            lambda x: x.get("next_step") if x.get("next_step") == "sql_corrector" else "data_analyst",
            {
                "sql_corrector": "sql_corrector",
                "data_analyst": "data_analyst"
            }
        )
        
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
                "chart_generator": "supervisor"  # Safety net: if it loops onto itself, break to supervisor
            }
        )

    # ==================== NODE IMPLEMENTATIONS ====================

    def supervisor_node(self, state: AgentState):
        """Route user requests to the appropriate worker node."""
        from app.services.ollama_service import ollama_service

        messages = state["messages"]
        last_message = messages[-1]
        
        if isinstance(last_message, HumanMessage):
            content = last_message.content.lower()
            
            # Direct keyword overrides for speed/reliability
            if any(kw in content for kw in ["load", "charge", "upload"]):
                return {"next_step": "csv_loader"}
            if any(kw in content for kw in ["finish", "stop"]):
                return {"next_step": "FINISH"}
            
            # Check if it's already a chart result (avoid loop)
            if "type" in content and "chart_result" in content:
                return {"next_step": "FINISH"}

            if any(kw in content for kw in ["chart", "graph", "plot", "trace", "dessine", "graphique"]):
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
                logger.exception(f"Routing error: {e}")
                return {"next_step": "data_analyst"}
                
        logger.debug(f"Supervisor decision: {last_message.content} -> FINISH")
        return {"next_step": "FINISH"}

    def csv_loader_node(self, state: AgentState):
        """Handle CSV file loading requests."""
        return {"messages": [AIMessage(content="CSV Loader: I can help you load data. Please upload a file.")]}

    def schema_analyzer_node(self, state: AgentState):
        """
        NEW: Analyze user query and resolve concepts to actual schema elements.
        Uses semantic search with BGE-M3 embeddings.
        """
        from app.services.schema_tools import schema_tools
        
        messages = state["messages"]
        
        # Find the user query
        user_query = None
        pending_request = state.get("pending_chart_request")
        if pending_request:
            user_query = pending_request
        else:
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    user_query = msg.content
                    break
        
        if not user_query:
            return {"messages": [AIMessage(content="Schema Analyzer: No query to analyze.")]}
        
        logger.info(f"Schema Analyzer: Analyzing query '{user_query[:50]}...'")
        
        try:
            # Use semantic tools to understand the query
            query_structure = schema_tools.suggest_query_structure(user_query)
            
            if "error" in query_structure:
                logger.warning(f"Schema analysis failed: {query_structure['error']}")
                return {
                    "messages": [AIMessage(content=f"Schema Analyzer: {query_structure['error']}")],
                    "original_user_query": user_query,
                    "query_structure": None,
                    "resolved_concepts": None
                }
            
            # Format resolved concepts for logging
            mappings = query_structure.get('mappings', [])
            concept_info = []
            for m in mappings:
                concept_info.append(f"  - {m.user_term} → {m.table}.{m.column} (confidence: {m.confidence:.2f})")
            
            logger.info(f"Schema Analyzer resolved concepts:\n" + "\n".join(concept_info))
            
            return {
                "messages": [AIMessage(content=f"Schema Analyzer: Resolved {len(mappings)} concepts from query.")],
                "original_user_query": user_query,
                "query_structure": {
                    "primary_table": query_structure.get('primary_table'),
                    "suggested_tables": query_structure.get('suggested_tables', []),
                    "aggregations": query_structure.get('aggregations', {}),
                    "group_by": [{"table": m.table, "column": m.column, "expr": m.cast_expression} 
                                 for m in query_structure.get('group_by', [])]
                },
                "resolved_concepts": {
                    m.user_term: {
                        "table": m.table,
                        "column": m.column,
                        "data_type": m.data_type,
                        "expression": m.cast_expression,
                        "confidence": m.confidence
                    } for m in mappings
                }
            }
        except Exception as e:
            logger.exception(f"Schema Analyzer error: {e}")
            return {
                "messages": [AIMessage(content=f"Schema Analyzer error: {str(e)}")],
                "original_user_query": user_query,
                "query_structure": None,
                "resolved_concepts": None
            }

    def sql_planner_node(self, state: AgentState):
        """
        Generate SQL queries using semantic understanding from schema_analyzer.
        Uses resolved concepts to build accurate SQL.
        """
        from app.services.ollama_service import ollama_service
        from app.services.duckdb_service import get_duckdb_service
        from app.services.relationship_service import relationship_service

        # Get resolved concepts from schema_analyzer
        resolved_concepts = state.get("resolved_concepts") or {}
        query_structure = state.get("query_structure") or {}
        user_query = state.get("original_user_query") or ""
        sql_error = state.get("sql_error")
        
        schema = get_duckdb_service().get_all_schemas()
        manual_relationships = relationship_service.get_formatted_relationships()
        
        logger.info(f"SQL Planner: Resolved concepts = {list(resolved_concepts.keys())}")
        
        # Build semantic context from resolved concepts
        semantic_context = ""
        if resolved_concepts:
            semantic_context = "RESOLVED COLUMNS (use these exact expressions):\n"
            for concept, info in resolved_concepts.items():
                semantic_context += f"- '{concept}' → {info['table']}.{info['column']}"
                if info.get('expression') and info['expression'] != info['column']:
                    semantic_context += f" (USE: {info['expression']})"
                semantic_context += f"\n"
        
        # Build JOIN hint
        join_hint = ""
        if query_structure.get('required_joins'):
            joins = query_structure['required_joins']
            join_hint = f"\nREQUIRED JOINS:\n" + "\n".join(joins)
        
        # Build primary table hint
        primary_table = query_structure.get('primary_table', '')
        table_hint = f"\nPRIMARY TABLE: {primary_table}" if primary_table else ""
        
        # Build grouping hint
        group_hint = ""
        if query_structure.get('group_by'):
            group_cols = [g['expr'] for g in query_structure['group_by']]
            group_hint = f"\nGROUP BY: {', '.join(group_cols)}"
        
        # Build aggregation hint  
        agg_hint = ""
        if query_structure.get('aggregations'):
            agg_hint = f"\nAGGREGATION: {query_structure['aggregations']}"
        
        # Build error feedback if retry
        error_section = ""
        if sql_error:
            truncated_error = sql_error[:300] if len(sql_error) > 300 else sql_error
            error_section = f"""
⚠️ PREVIOUS QUERY FAILED:
{truncated_error}
Use ONLY the columns from RESOLVED COLUMNS above.
"""
        
        system_message = f"""You are a DuckDB SQL expert. Generate ONLY valid SQL.

{semantic_context}
{table_hint}
{join_hint}
{group_hint}
{agg_hint}

Available Relationships:
{manual_relationships}
{error_section}

CRITICAL RULES:
1. OUTPUT ONLY SQL - Start with SELECT or WITH
2. Use EXACT expressions from RESOLVED COLUMNS
3. Use the REQUIRED JOINS if multiple tables are needed
4. Use PRIMARY TABLE as the FROM table
5. NO explanations, NO markdown, NO French text

User Query: {user_query}

SQL:"""
        
        llm_messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_query)
        ]
        
        try:
            response = ollama_service.chat_llm.invoke(llm_messages)
            sql_query = response.content.strip()
            
            # Extract and clean SQL
            sql_query = self._extract_sql(sql_query)
            
            # Apply table/column name fixes
            sql_query = self._fix_table_names(sql_query)
            
            logger.info(f"SQL Planner generated: {sql_query[:100]}...")
            
            return {
                "messages": [AIMessage(content=f"Planning SQL: {sql_query}")],
                "sql_query": sql_query,
                "sql_error": None  # Clear previous error
            }
        except Exception as e:
            logger.exception(f"SQL Planner error: {e}")
            return {
                "messages": [AIMessage(content=f"SQL Planner error: {str(e)}")],
                "sql_query": "",
                "sql_error": str(e)
            }

    def sql_validator_node(self, state: AgentState):
        """
        NEW: Validate SQL against schema before execution.
        Uses schema_tools to check tables and columns exist.
        """
        from app.services.schema_tools import schema_tools
        
        sql_query = state.get("sql_query", "")
        
        if not sql_query or "ERROR" in sql_query:
            return {
                "messages": [AIMessage(content="SQL Validator: No valid SQL to validate.")],
                "next_step": "sql_corrector"
            }
        
        logger.info(f"SQL Validator: Validating '{sql_query[:80]}...'")
        
        validation = schema_tools.validate_sql(sql_query)
        
        if validation.is_valid:
            logger.info("SQL Validator: Query is valid")
            return {
                "messages": [AIMessage(content="SQL Validator: Query validated successfully.")],
                "next_step": "execute"
            }
        else:
            error_msg = "; ".join(validation.errors)
            suggestions = "; ".join(validation.suggestions)
            logger.warning(f"SQL Validator: Invalid - {error_msg}")
            
            return {
                "messages": [AIMessage(content=f"SQL Validator: {error_msg}")],
                "sql_error": error_msg,
                "next_step": "sql_corrector"
            }

    def sql_corrector_node(self, state: AgentState):
        """
        NEW: Attempt to correct SQL errors using semantic understanding.
        """
        from app.services.schema_tools import schema_tools
        
        sql_query = state.get("sql_query", "")
        sql_error = state.get("sql_error", "")
        retry_count = state.get("sql_retry_count", 0)
        max_retries = 3
        
        if retry_count >= max_retries:
            logger.error(f"SQL Corrector: Max retries ({max_retries}) reached")
            return {
                "messages": [AIMessage(content=f"SQL Corrector: Unable to fix query after {max_retries} attempts. Error: {sql_error}")],
                "next_step": "data_analyst",
                "sql_retry_count": 0
            }
        
        logger.info(f"SQL Corrector: Attempting correction (attempt {retry_count + 1}/{max_retries})")
        
        if not sql_error:
            # No error to correct, try to validate
            return {
                "messages": [AIMessage(content="SQL Corrector: No error to correct.")],
                "next_step": "sql_validator",
                "sql_retry_count": retry_count + 1
            }
        
        # Try to correct the SQL
        corrected_sql, changes = schema_tools.correct_sql(sql_query, sql_error)
        
        if changes:
            logger.info(f"SQL Corrector: Made changes: {changes}")
            return {
                "messages": [AIMessage(content=f"SQL Corrector: {'; '.join(changes)}")],
                "sql_query": corrected_sql,
                "sql_error": None,
                "sql_retry_count": retry_count + 1,
                "next_step": "sql_validator"
            }
        else:
            # Couldn't correct automatically, return error
            logger.warning("SQL Corrector: Unable to auto-correct")
            return {
                "messages": [AIMessage(content=f"SQL Corrector: Unable to auto-correct. Error: {sql_error}")],
                "next_step": "data_analyst",
                "sql_retry_count": retry_count + 1
            }

    def _extract_sql(self, raw_output: str) -> str:
        """
        Extract and validate SQL from LLM output.
        Uses sqlparse if available for better parsing.
        Aggressively filters out non-SQL content.
        """
        logger.debug(f"Raw LLM output for SQL extraction: {raw_output[:500]}...")
        
        raw_lower = raw_output.strip().lower()
        
        # 0. Early rejection of non-SQL code (Python, Excel, etc.)
        non_sql_indicators = [
            'import ', 'def ', 'print(', 'pandas', 'pd.', 'df.', 'python',
            '```python', 'excel', '.xlsx', '.csv', 'read_csv', 'dataframe',
            'for ', 'while ', 'if __name__', 'class ', 'return ', 'lambda'
        ]
        if any(indicator in raw_lower for indicator in non_sql_indicators):
            logger.warning(f"LLM generated non-SQL code (Python/Excel), rejecting...")
            return "SELECT 'ERROR: No valid SQL generated' AS error"
        
        # 1. Early rejection of obviously non-SQL responses (French text)
        french_starters = ['le ', 'la ', 'les ', 'voici ', 'cette ', 'ce ', 'pour ', 'il ', "l'", "d'"]
        starts_with_french = any(raw_lower.startswith(f) for f in french_starters)
        
        if starts_with_french:
            logger.warning("LLM response starts with French text, attempting to extract SQL...")
        
        # 1. Try to find markdown code blocks first (most reliable)
        code_block_match = re.search(r'```(?:sql)?\s*(.*?)```', raw_output, re.DOTALL | re.IGNORECASE)
        if code_block_match:
            sql = code_block_match.group(1).strip()
        else:
            # 2. Fallback: Find the first SELECT or WITH and take everything
            match = re.search(r'(?i)\b(SELECT|WITH)\s', raw_output)
            if match:
                sql = raw_output[match.start():]
                # Strip trailing backticks if present
                if sql.endswith("```"):
                    sql = sql[:-3]
                sql = sql.strip()
            else:
                # 3. If no SQL found at all, log error and return empty
                logger.error(f"No SQL found in LLM response: {raw_output[:200]}...")
                # Return a safe error query that will fail gracefully
                return "SELECT 'ERROR: No valid SQL generated' AS error"
        
        # 4. Clean up text before/after SQL
        # Remove any text before SELECT/WITH
        match = re.search(r'(?i)\b(SELECT|WITH)\s', sql)
        if match and match.start() > 0:
            sql = sql[match.start():]
        
        # 5. Try to use sqlparse if available for better parsing
        try:
            import sqlparse
            parsed = sqlparse.parse(sql)
            if parsed and len(parsed) > 0:
                # Get only the first valid statement
                first_stmt = parsed[0]
                sql = str(first_stmt).strip()
                
                # Format for cleaner output
                sql = sqlparse.format(
                    sql,
                    strip_comments=True,
                    strip_whitespace=True,
                    keyword_case='upper'
                )
        except ImportError:
            logger.debug("sqlparse not available, using basic extraction")
        except Exception as e:
            logger.warning(f"sqlparse processing failed: {e}")
        
        # 6. Final cleanup
        # Remove trailing semicolons (DuckDB doesn't like them)
        sql = sql.rstrip(';').strip()
        
        # Remove any trailing explanatory text (French or English)
        lines = sql.split('\n')
        clean_lines = []
        stop_patterns = [
            'this query', 'note:', 'the above', 'this will',
            'cette requête', 'voici', 'cela', 'remarque:', 'le résultat'
        ]
        for line in lines:
            stripped = line.strip()
            # Stop at explanatory comments or text
            if stripped.startswith('--') and any(kw in stripped.lower() for kw in ['explanation', 'note:', 'returns', 'résultat']):
                break
            if any(stripped.lower().startswith(p) for p in stop_patterns):
                break
            # Skip empty lines at the end
            clean_lines.append(line)
        
        result = '\n'.join(clean_lines).strip().rstrip(';').strip()
        
        # 7. Fix table names - LLM often uses simplified names
        result = self._fix_table_names(result)
        
        logger.debug(f"Extracted SQL: {result}")
        return result

    def _fix_table_names(self, sql: str) -> str:
        """
        Fix common table and column name errors from LLM output.
        Maps simplified names to actual names.
        """
        # Table name mappings
        table_mappings = {
            # Common simplified versions
            r'\bfactures\b': 'IA_Factures',
            r'\bcommandes\b': 'IA_Commandes',
            r'\boperations\b': 'IA_Operations',
            r'\breglements\b': 'IA_Reglements',
            r'\bdepenses\b': 'IA_Depenses',
            r'\blien_operation_tg\b': 'IA_Lien_Operation_TG',
            # With IA_ prefix but wrong case
            r'\bia_factures\b': 'IA_Factures',
            r'\bia_commandes\b': 'IA_Commandes',
            r'\bia_operations\b': 'IA_Operations',
            r'\bia_reglements\b': 'IA_Reglements',
            r'\bia_depenses\b': 'IA_Depenses',
            r'\bia_lien_operation_tg\b': 'IA_Lien_Operation_TG',
            # Singular forms
            r'\bfacture\b': 'IA_Factures',
            r'\bcommande\b': 'IA_Commandes',
            r'\boperation\b': 'IA_Operations',
            r'\breglement\b': 'IA_Reglements',
            r'\bdepense\b': 'IA_Depenses',
        }
        
        # Column name mappings (common LLM mistakes)
        column_mappings = {
            # Task/Project codes
            r'\bcode_tache\b': 'CDE_ID_TACHE',
            r'\btache\b': 'CDE_ID_TACHE',
            r'\bcode_projet\b': 'CDE_ID_PROJET',
            r'\bprojet\b': 'CDE_ID_PROJET',
            r'\btrigramme\b': 'CDE_TG',
            # Date columns
            r'\bdate_facture\b': 'FACF_D_DATE_FACTURE',
            r'\bdate_commande\b': 'CDE_DATE_COMMANDE',
            r'\bannee\b(?!\s+AS)': 'annee',  # Keep alias
            # Amount columns (be careful with these)
            r'\bmontant\b(?!\s+AS)(?!\s+FROM)': 'CAST(REPLACE(CDE_LIGNE_IMPUTATION_MONTANT_COMMANDEE_NETTE, \',\', \'.\') AS DOUBLE)',
            r'\bchiffre_affaires\b': 'CAST(REPLACE(CDE_LIGNE_IMPUTATION_MONTANT_COMMANDEE_NETTE, \',\', \'.\') AS DOUBLE)',
            r'\bchiffre_daffaires\b': 'CAST(REPLACE(CDE_LIGNE_IMPUTATION_MONTANT_COMMANDEE_NETTE, \',\', \'.\') AS DOUBLE)',
        }
        
        fixed_sql = sql
        
        # Fix table names first
        for pattern, replacement in table_mappings.items():
            fixed_sql = re.sub(pattern, replacement, fixed_sql, flags=re.IGNORECASE)
        
        # Fix column names
        for pattern, replacement in column_mappings.items():
            fixed_sql = re.sub(pattern, replacement, fixed_sql, flags=re.IGNORECASE)
        
        if fixed_sql != sql:
            logger.info(f"Fixed SQL: {sql[:100]}... -> {fixed_sql[:100]}...")
        
        return fixed_sql

    def _validate_sql_syntax(self, sql: str) -> tuple[bool, str]:
        """
        Validate SQL syntax using DuckDB's EXPLAIN.
        Returns (is_valid, error_message).
        """
        from app.services.duckdb_service import get_duckdb_service
        return get_duckdb_service().validate_query(sql)

    def sql_executor_node(self, state: AgentState):
        """Execute SQL queries against DuckDB. Routes to corrector on error."""
        from app.services.duckdb_service import get_duckdb_service
        
        sql_query = state.get("sql_query")
        
        if not sql_query or "ERROR" in sql_query:
            return {
                "messages": [AIMessage(content="SQL Executor: No valid SQL to execute.")],
                "sql_error": "No valid SQL query",
                "next_step": "sql_corrector"
            }
        
        logger.info(f"SQL Executor: Executing '{sql_query[:80]}...'")
        
        try:
            results = get_duckdb_service().execute_query(sql_query)
            
            response_data = {
                "type": "data_result",
                "summary": f"Executed query: {sql_query}",
                "columns": results["columns"],
                "data": results["data"]
            }
            
            logger.info(f"SQL Executor: Success - {len(results['data'])} rows returned")
            
            # Success - clear error state
            return {
                "messages": [AIMessage(content=json.dumps(response_data))],
                "sql_error": None,
                "sql_retry_count": 0,
                "next_step": "data_analyst"
            }
        except Exception as e:
            logger.exception(f"SQL Execution Error: {e}")
            error_msg = str(e)
            
            # Route to corrector
            return {
                "messages": [AIMessage(content=f"SQL Execution Error: {error_msg}")],
                "sql_error": error_msg,
                "next_step": "sql_corrector"
            }

    def data_analyst_node(self, state: AgentState):
        """Analyze and interpret data results."""
        # If in SQL mode, do not generate conversational analysis
        if state.get("mode") == "sql":
            return {}
            
        pending_request = state.get("pending_chart_request")
        logger.debug(f"Data Analyst - Pending Chart Request: {pending_request}")

        # If we have a pending chart request, skip analysis and go back to chart generator
        if pending_request:
            logger.debug("Data Analyst - Skipping analysis due to pending chart request")
            return {}

        from app.services.ollama_service import ollama_service
        from app.services.duckdb_service import get_duckdb_service
        
        schema = get_duckdb_service().get_all_schemas()
        messages = state["messages"]
        
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
        
        full_messages = [SystemMessage(content=system_prompt)] + messages
        
        response = ollama_service.generate_response(full_messages)
        return {"messages": [response]}

    def chart_generator_node(self, state: AgentState):
        """Generate Plotly chart configurations from data."""
        from app.services.ollama_service import ollama_service
        
        logger.debug("Entering chart_generator_node")
        
        messages = state["messages"]
        last_data = self._find_last_data_result(messages)
        
        # If no data found, we need to fetch it first
        if not last_data:
            logger.debug("No data found, routing to sql_planner")
            user_request = messages[-1].content
            return {
                "messages": [AIMessage(content="Je n'ai pas de données pour ce graphique. Je vais d'abord exécuter une requête SQL pour les récupérer.")],
                "pending_chart_request": user_request,
                "next_step": "sql_planner"
            }
            
        logger.debug("Data found, generating chart")
        user_request = state.get("pending_chart_request") or messages[-1].content
        
        # Check if request is generic (asking for suggestions)
        if self._is_generic_chart_request(user_request):
            return self._generate_chart_suggestions(last_data, ollama_service)
        
        # Standard chart generation
        return self._generate_chart(last_data, user_request, ollama_service)

    def _find_last_data_result(self, messages: List[BaseMessage]) -> dict:
        """Find the most recent data_result message."""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content.startswith('{'):
                try:
                    data = json.loads(msg.content)
                    if data.get("type") == "data_result":
                        return data
                except json.JSONDecodeError:
                    continue
        return None

    def _is_generic_chart_request(self, request: str) -> bool:
        """Check if the chart request is generic and needs suggestions."""
        lower_request = request.lower()
        if "génère un graphique" in lower_request or "standard" in lower_request or len(lower_request) < 50:
            if not any(t in lower_request for t in ["camembert", "barres", "ligne", "pie", "bar", "line", "scatter", "nuage"]):
                return True
        return False

    def _generate_chart_suggestions(self, data: dict, ollama_service) -> dict:
        """Generate chart suggestions for generic requests."""
        logger.debug("Generic request detected, generating suggestions")
        
        suggestion_prompt = f"""You are a Data Visualization Expert.
        Data Columns: {data['columns']}
        Data Sample: {data['data'][:3]}
        
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
            suggestions_str = self._clean_json_response(response.content)
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
            logger.exception(f"Suggestion generation failed: {e}")
            # Fallback to empty suggestions
            return {
                "messages": [AIMessage(content=json.dumps({
                    "type": "chart_suggestions",
                    "suggestions": []
                }))],
                "next_step": "supervisor"
            }

    def _generate_chart(self, data: dict, user_request: str, ollama_service) -> dict:
        """Generate a specific Plotly chart configuration."""
        logger.debug("Specific request detected, generating chart")
        
        system_prompt = f"""You are a Data Visualization Expert using Plotly.js.
        
        Data Columns: {data['columns']}
        Data Sample (first 3 rows): {data['data'][:3]}
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
            plotly_config_str = self._clean_json_response(response.content)
            plotly_config = json.loads(plotly_config_str)
            
            # Inject actual data
            self._inject_data_into_config(plotly_config, data)
            
            response_data = {
                "type": "chart_result",
                "config": plotly_config
            }
            
            logger.debug("Chart generated successfully")
            return {
                "messages": [AIMessage(content=json.dumps(response_data))],
                "pending_chart_request": None,
                "next_step": "supervisor"
            }
            
        except Exception as e:
            logger.exception(f"Chart generation error: {e}")
            return {
                "messages": [AIMessage(content=f"Erreur lors de la génération du graphique : {str(e)}")],
                "next_step": "supervisor"
            }

    def _clean_json_response(self, content: str) -> str:
        """Clean markdown formatting from JSON response."""
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content.rsplit("\n", 1)[0] if "\n" in content else content[:-3]
        return content.strip()

    def _inject_data_into_config(self, config: dict, data: dict):
        """Recursively replace __COLUMN__ placeholders with actual data arrays."""
        columns = data['columns']
        rows = data['data']
        col_data = {col: [row[col] for row in rows] for col in columns}
        
        def inject(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, str) and v.startswith("__") and v.endswith("__"):
                        col_name = v[2:-2]
                        if col_name in col_data:
                            obj[k] = col_data[col_name]
                    else:
                        inject(v)
            elif isinstance(obj, list):
                for item in obj:
                    inject(item)
        
        inject(config)

    # ==================== MAIN PROCESSING ====================

    async def process_message(self, message: str, session_id: str = "default", mode: str = "chat"):
        """Process a user message through the agent workflow."""
        from app.services.history_service import history_service
        
        # Save user message
        history_service.add_message(session_id, "user", message)
        
        # Load history to provide context
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
        
        inputs = {"messages": langchain_messages, "mode": mode}
        
        async for output in self.app.astream(inputs):
            for key, value in output.items():
                if value:
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
                        
                        # Save to history for specific nodes
                        if key in ["data_analyst", "sql_executor", "chart_generator"]:
                            history_service.add_message(session_id, "assistant", content)

                        yield json.dumps({
                            "type": event_type,
                            "node": key,
                            "content": content
                        })


agent_service = AgentService()
