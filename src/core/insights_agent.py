import os
import sqlite3
import pandas as pd
from groq import Groq
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
DB_PATH = "data/aims_project.db"

def execute_sql(query):
    """Executa uma query SQL no banco de dados e retorna um DataFrame."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        return str(e)

def ask_data_agent(user_query):
    """
    Agente que traduz linguagem natural para SQL, consulta o banco AIMS 
    e sintetiza uma resposta analítica.
    """
    
    # 1. Definição do Esquema para a IA
    # Isso ajuda a IA a saber quais colunas existem e o que significam
    db_schema = """
    Table: articles
    Columns:
    - id (INTEGER): Unique ID
    - title (TEXT): Title of the paper
    - authors (TEXT): List of authors
    - year (INTEGER): Year of publication
    - abstract (TEXT): Summary of the study
    - doi (TEXT): Digital Object Identifier
    - source (TEXT): Database source (e.g., Scopus, IEEE, snowballing)
    - literature_type (TEXT): 'WL' for White Literature, 'GL' for Grey Literature
    - status (TEXT): 'imported', 'excluded', 'included_screening', 'included_final'
    - quality_score (REAL): Score from 0.0 to 4.0
    - ic_results (TEXT): JSON string containing extracted evidence/findings
    """

    # 2. Passo 1: Tradução de Linguagem Natural para SQL
    system_prompt_sql = f"""
    You are a Senior SQL Expert and Data Scientist. 
    Your goal is to translate user questions into valid SQLite queries based on the schema provided below.
    
    SCHEMA:
    {db_schema}
    
    RULES:
    - Return ONLY the SQL query. No explanations.
    - Use LIKE for keyword searches in title or abstract.
    - If the user asks for 'trends', group by 'year'.
    - If the user asks for 'evidence', look into the 'ic_results' or 'abstract' columns.
    - Always limit results to 10 unless specified otherwise.
    """

    try:
        # Gera a Query SQL
        sql_response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt_sql},
                {"role": "user", "content": user_query}
            ],
            model="llama3-8b-8192", # Modelo rápido para geração de código
            temperature=0,
        )
        
        generated_sql = sql_response.choices[0].message.content.strip()
        # Limpeza básica de markdown caso a IA retorne blocos de código
        generated_sql = generated_sql.replace("```sql", "").replace("```", "").strip()

        # 3. Executa a Query no Banco
        df_results = execute_sql(generated_sql)

        if isinstance(df_results, str): # Se houve erro no SQL
            return f"I had trouble querying the database. Error: {df_results}"
        
        if df_results.empty:
            return "I searched the database but found no records matching your request."

        # 4. Passo 2: Sintetizar Resposta Final (Data Storytelling)
        system_prompt_narrative = """
        You are a Research Data Scientist. You have been provided with raw data results from an SQL query.
        Synthesize these results into a professional, clear, and insightful answer for the researcher.
        
        - Highlight patterns or interesting findings.
        - If listing articles, provide titles and years.
        - Be concise but descriptive.
        - Mention that the results are based on the current AIMS database.
        """

        narrative_response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt_narrative},
                {"role": "user", "content": f"User Question: {user_query}\n\nSQL Results:\n{df_results.to_string()}"}
            ],
            model="llama-3.3-70b-versatile", # Modelo mais robusto para análise
            temperature=0.3,
        )

        return narrative_response.choices[0].message.content

    except Exception as e:
        return f"Sorry, I encountered an error while processing your request: {str(e)}"