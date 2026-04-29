import os
import json
import logging
from typing import Dict, Any, Optional
from groq import Groq

# Configuração de Logging para Auditoria da IA
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_ai_suggestion(title: str, abstract: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analisa um artigo com base no protocolo de pesquisa (RQs, ICs, ECs).
    Retorna um veredito estruturado para apoiar a decisão do pesquisador.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY não encontrada nas variáveis de ambiente.")
        return {
            "decision": "error",
            "reasons": ["Configuração ausente: Chave de API não configurada."],
            "confidence": 0
        }

    client = Groq(api_key=api_key)

    # 1. Preparação Dinâmica do Contexto (Injeção do Protocolo)
    rqs_context = "\n".join(settings.get("research_questions", []))
    ic_context = "\n".join([f"- {k}: {v}" for k, v in settings.get("inclusion_criteria", {}).items()])
    ec_context = "\n".join([f"- {k}: {v}" for k, v in settings.get("exclusion_criteria", {}).items()])

    # 2. Prompt Engineering de Classe Sistêmica
    system_prompt = f"""
    You are a Senior Research Assistant specialized in Multivocal Literature Reviews (MLR) in Software Engineering.
    Your task is to evaluate a study's Title and Abstract based on a strict Research Protocol.

    ### RESEARCH QUESTIONS (RQs):
    {rqs_context}

    ### ELIGIBILITY CRITERIA:
    INCLUSION (IC):
    {ic_context}

    EXCLUSION (EC):
    {ec_context}

    ### DECISION LOGIC:
    1. Check for EXCLUSION criteria first. If any EC applies, the decision must be 'exclude'.
    2. If no EC applies, check if the study aligns with at least one INCLUSION criterion and addresses any RQ.
    3. Be conservative: if the abstract is vague but mentions Software Engineering Recruitment, suggest 'include' for full-text review.

    ### OUTPUT FORMAT:
    You must return ONLY a valid JSON object. Do not include preamble or explanations outside the JSON.
    Format:
    {{
        "decision": "include" | "exclude",
        "confidence": integer (0-100),
        "matched_criteria": ["ID1", "ID2"],
        "reasons": ["Detailed justification using protocol terms", "Specific link to RQ"]
    }}
    """

    user_content = f"TITLE: {title}\n\nABSTRACT: {abstract}"

    try:
        # 3. Chamada à LLM com Temperatura Baixa (Rigor Científico)
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            model="llama3-70b-8192",
            temperature=0.1, # Minimiza alucinações e variações
            max_tokens=1000,
            response_format={"type": "json_object"} # Garante parse estruturado
        )

        ai_response = json.loads(response.choices[0].message.content)
        
        # Log da decisão para rastreabilidade
        logger.info(f"AI Decision for '{title[:30]}...': {ai_response['decision']} ({ai_response['confidence']}%)")
        
        return ai_response

    except json.JSONDecodeError:
        logger.error("Erro ao decodificar resposta da IA (Formato inválido).")
        return {"decision": "error", "reasons": ["Erro na formatação da resposta da IA."], "confidence": 0}
    except Exception as e:
        logger.error(f"Erro na chamada da API Groq: {str(e)}")
        return {"decision": "error", "reasons": [f"Erro técnico: {str(e)}"], "confidence": 0}