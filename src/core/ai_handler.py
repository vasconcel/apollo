"""
AIMS AI Handler
Manages LLM integration (Groq/Llama-3) for screening suggestions.
"""
import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

def get_ai_suggestion(title: str, abstract: str, criteria_dict: dict) -> dict:
    """
    Get AI screening suggestion using Llama-3 via Groq.
    
    Args:
        title: Paper title
        abstract: Paper abstract
        criteria_dict: Dict containing inclusion/exclusion criteria
        
    Returns:
        Dict with suggestion keys or error key
    """
    try:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return {"error": "GROQ_API_KEY not found in .env file"}
        
        client = Groq(api_key=api_key)
        
        # Format criteria for prompt
        criteria_str = json.dumps(criteria_dict, indent=2)
        
        prompt = f"""You are a Research Assistant. Evaluate this paper against the following criteria:
{criteria_str}

Paper Title: {title}
Paper Abstract: {abstract}

Return ONLY a valid JSON object with no markdown, no extra text. The JSON must contain:
- "decision": either "include" or "exclude"
- "reason": one sentence explanation for the decision
- "matched_criteria": ID of the criteria that was matched or violated"""
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200
        )
        
        content = response.choices[0].message.content.strip()
        # Clean potential markdown formatting
        if content.startswith("```json"):
            content = content[7:].strip()
        if content.endswith("```"):
            content = content[:-3].strip()
        
        return json.loads(content)
        
    except json.JSONDecodeError:
        return {"error": f"Failed to parse AI response: {content}"}
    except Exception as e:
        return {"error": f"AI request failed: {str(e)}"}
