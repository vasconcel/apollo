import os
import json
import logging
import time
from typing import Dict, Any, Optional
from groq import Groq
from groq import RateLimitError, APIConnectionError, APITimeoutError

# Configuração de Logging para Auditoria da IA
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_ai_suggestion(title: str, abstract: str, settings: Dict[str, Any], max_retries: int = 2, retry_delay: float = 1.0) -> Dict[str, Any]:
    """
    Analisa um artigo com base no protocolo de pesquisa (RQs, ICs, ECs).
    Retorna um veredito estruturado para apoiar a decisão do pesquisador.
    
    Includes resilient retry logic for rate limits and transient errors.
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

    last_error = None
    
    for attempt in range(max_retries):
        try:
            # 3. Chamada à LLM com Temperatura Baixa (Rigor Científico)
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                model="llama3-70b-8192",
                temperature=0.1,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            ai_response = json.loads(response.choices[0].message.content)
            
            # Log da decisão para rastreabilidade
            logger.info(f"AI Decision for '{title[:30]}...': {ai_response['decision']} ({ai_response['confidence']}%)")
            
            return ai_response

        except RateLimitError as e:
            last_error = f"Rate limit: {str(e)}"
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Rate limit hit, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Rate limit exceeded after {max_retries} attempts")
                
        except APITimeoutError as e:
            last_error = f"Timeout: {str(e)}"
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logger.warning(f"API timeout, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"API timeout after {max_retries} attempts")
                
        except APIConnectionError as e:
            last_error = f"Connection error: {str(e)}"
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logger.warning(f"API connection error, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"API connection failed after {max_retries} attempts")
                
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar resposta da IA (Formato inválido): {str(e)}")
            return {"decision": "error", "reasons": ["Erro na formatação da resposta da IA."], "confidence": 0}
            
        except Exception as e:
            last_error = str(e)
            logger.error(f"Erro inesperado na chamada da API Groq: {last_error}")
            break
    
    # Return error response after all retries exhausted
    return {
        "decision": "error",
        "reasons": [f"API error (após {max_retries} tentativas): {last_error}"],
        "confidence": 0
    }


def generate_theme_synthesis(theme_label: str, wl_fragments: list, gl_fragments: list) -> Dict[str, Any]:
    """
    Generates an AI-powered synthesis for a theme by comparing White Literature (WL)
    and Grey Literature (GL) fragments.
    
    Args:
        theme_label: The name/label of the theme being synthesized
        wl_fragments: List of tuples (text, authors, year) for White Literature (academic) fragments
        gl_fragments: List of tuples (text, authors, year) for Grey Literature (practitioner) fragments
        
    Returns:
        Dict with synthesis text and metadata
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY não encontrada nas variáveis de ambiente.")
        return {
            "synthesis": None,
            "error": "API key not configured"
        }

    client = Groq(api_key=api_key)
    
    # Format fragments for the prompt (fragments are preformatted as "[Author, Year]: text")
    wl_text = "\n".join([f"- [{i+1}] {f}" for i, f in enumerate(wl_fragments)]) if wl_fragments else "No academic fragments available."
    gl_text = "\n".join([f"- [{i+1}] {f}" for i, f in enumerate(gl_fragments)]) if gl_fragments else "No practitioner fragments available."
    
    # Prompt Engineering for Theme Synthesis with Citation Tracking
    system_prompt = f"""
You are a Senior Research Assistant specialized in Multivocal Literature Reviews (MLR) in Software Engineering.
Your task is to synthesize evidence fragments into a coherent research findings report.

### THEME: {theme_label}

### DATA FORMAT:
Each fragment is prefixed with its source metadata in [Author, Year] format.
Example: "[Smith et al., 2023]: Finding about hiring pipelines..."

### INSTRUCTIONS:
Analyze the extracted evidence fragments below and synthesize them into a professional research report.
Focus on comparing academic (White Literature - WL) and practitioner (Grey Literature - GL) perspectives.

### REQUIRED OUTPUT STRUCTURE:
Please structure your response with these exact sections:

**Core Findings**: 
A summary (3-5 sentences) of what the evidence collectively says about this theme.

**WL vs GL Divergence**: 
Identify where academia and industry perspectives agree, disagree, or reveal a theory-practice gap.
Use specific fragment references to support your analysis (e.g., "Smith et al. (2023) found...").

**Actionable Practices**: 
List 3-5 concrete mechanisms, design principles, or practices found in the evidence.
Be specific and actionable for practitioners.

**Research Gaps**: 
What is missing from the current evidence base? What questions remain unanswered?

### CITATION TRACKING:
When referring to specific findings, cite using the Author/Year markers provided in the fragments to maintain traceability.
Example citations: "(Author, Year)" or "[Author, Year]"

### IMPORTANT:
- Base all findings on the provided fragments
- Maintain academic rigor and objectivity
- If data is limited, explicitly acknowledge limitations
- Do NOT include preamble or meta-commentary outside the required structure
"""

    user_content = f"""
Academic (WL) Fragments:
{wl_text}

Practitioner (GL) Fragments:
{gl_text}
"""

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            model="llama3-70b-8192",
            temperature=0.2,
            max_tokens=2000
        )
        
        synthesis = response.choices[0].message.content
        
        logger.info(f"AI Synthesis generated for theme: {theme_label}")
        
        return {
            "synthesis": synthesis,
            "wl_count": len(wl_fragments),
            "gl_count": len(gl_fragments),
            "error": None
        }
        
    except Exception as e:
        logger.error(f"Erro na geração de síntese: {str(e)}")
        return {
            "synthesis": None,
            "error": str(e)
        }