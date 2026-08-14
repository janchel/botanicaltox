"""
ai_explainer.py
---------------
Optional AI-powered explanation of prediction results.

Configuration in .env file:
    AI_API_KEY=sk-your-key-here
    AI_BASE_URL=https://ai.rebelstack.fun
    AI_MODEL=jandel/free

If no key is set, the explainer gracefully shows a setup message.
"""

import os
import json
from pathlib import Path
from typing import Generator


def _load_dotenv():
    """Load environment variables from a .env file in the drug_ai/ directory."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


# Load .env on import so keys are available immediately
_load_dotenv()

# Defaults — override via .env or environment variables
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://ai.rebelstack.fun")
AI_MODEL = os.environ.get("AI_MODEL", "jandel/free")

_openai_client = None


def _get_client():
    """Lazily create the OpenAI-compatible client."""
    global _openai_client
    if _openai_client is not None:
        return _openai_client

    if not AI_API_KEY:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    _openai_client = OpenAI(
        base_url=AI_BASE_URL + "/v1",
        api_key=AI_API_KEY,
    )
    return _openai_client


def is_available() -> bool:
    """Check if the AI explainer is configured and ready."""
    return _get_client() is not None


def build_explanation_prompt(prediction_summary: dict) -> str:
    """Build a structured prompt for the AI to explain prediction results."""
    task_type = prediction_summary.get("task", "activity and toxicity")
    total = prediction_summary.get("total_compounds", 0)

    act_counts = prediction_summary.get("activity_counts", {})
    tox_counts = prediction_summary.get("toxicity_counts", {})
    top_features = prediction_summary.get("top_features", [])

    prompt = f"""You are a medicinal chemistry and machine learning tutor helping students understand drug discovery predictions.

A Random Forest model was used to predict the {task_type} of {total} chemical compounds.

Here are the prediction results:

ACTIVITY (OXA-23 inhibition):
- Predicted Active: {act_counts.get('active', 'N/A')}
- Predicted Inactive: {act_counts.get('inactive', 'N/A')}

TOXICITY (Human):
- Predicted Toxic: {tox_counts.get('toxic', 'N/A')}
- Predicted Safe: {tox_counts.get('safe', 'N/A')}

The most important molecular features driving these predictions were:
{json.dumps(top_features, indent=2) if top_features else 'Not available'}

Please explain these results to a student in a clear, educational way. Structure your response with these sections:

1. **Summary** — A 2-3 sentence plain-language summary of what the model found.

2. **What These Predictions Mean** — Explain in simple terms what "active against OXA-23" and "toxic to humans" mean biologically, and what the prediction counts suggest about this compound library.

3. **Key Molecular Features** — Briefly explain 2-3 of the most important features (e.g., what MolLogP, TPSA, or NumHDonors tell us about a molecule's drug-likeness).

4. **Limitations & Next Steps** — Remind the student that these are computational predictions (not experimental results), suggest experimental validation, and mention that a larger training set would improve reliability.

Keep the tone encouraging and educational. Use markdown formatting. Keep it under 500 words."""
    return prompt


def explain_stream(prediction_summary: dict) -> Generator[str, None, None]:
    """
    Stream an AI-generated explanation of prediction results.
    Yields Server-Sent Event formatted strings.
    """
    client = _get_client()

    if client is None:
        msg = "data: " + json.dumps({
            "error": "AI explainer not configured. Set AI_API_KEY in the .env file."
        }) + "\n\n"
        yield msg
        return

    prompt = build_explanation_prompt(prediction_summary)

    try:
        completion = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=1,
            top_p=0.95,
            max_tokens=4096,
            stream=True,
        )

        for chunk in completion:
            if not chunk.choices:
                continue
            if chunk.choices[0].delta.content is not None:
                yield "data: " + json.dumps({"content": chunk.choices[0].delta.content}) + "\n\n"

        yield "data: " + json.dumps({"done": True}) + "\n\n"

    except Exception as e:
        yield "data: " + json.dumps({"error": str(e)}) + "\n\n"


def explain_sync(prediction_summary: dict) -> str:
    """
    Non-streaming version — returns the full explanation as a string.
    """
    client = _get_client()

    if client is None:
        return "⚠️ AI explainer not configured. Set `AI_API_KEY` in the .env file."

    prompt = build_explanation_prompt(prediction_summary)

    try:
        completion = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=1,
            top_p=0.95,
            max_tokens=4096,
            stream=False,
        )
        return completion.choices[0].message.content

    except Exception as e:
        return f"❌ Error generating explanation: {e}"
