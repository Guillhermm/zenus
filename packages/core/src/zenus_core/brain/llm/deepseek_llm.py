from dotenv import load_dotenv, find_dotenv # type: ignore
import json
import os
from pathlib import Path
from zenus_core.brain.llm.schemas import IntentIR
from zenus_core.brain.llm.system_prompt import build_system_prompt


# Load secrets: ~/.zenus/.env first (system-wide), then project .env (from source)
_user_env = Path.home() / ".zenus" / ".env"
if _user_env.exists():
    load_dotenv(_user_env)
load_dotenv(find_dotenv(usecwd=True))




def extract_json(text: str) -> dict:
    """
    Extract JSON from text that might have markdown or extra content
    
    Handles:
    - Plain JSON
    - JSON wrapped in ```json``` code fences
    - JSON with surrounding text
    """
    # Strip markdown code fences if present
    text = text.strip()
    
    # Remove ```json and ``` markers
    if text.startswith("```json"):
        text = text[7:]  # Remove ```json
    elif text.startswith("```"):
        text = text[3:]  # Remove ```
    
    if text.endswith("```"):
        text = text[:-3]  # Remove trailing ```
    
    text = text.strip()
    
    # Try to find JSON object in the text
    start = text.find("{")
    end = text.rfind("}")
    
    if start == -1 or end == -1:
        raise RuntimeError("No JSON object found in model output")
    
    snippet = text[start:end + 1]
    
    try:
        return json.loads(snippet)
    except json.JSONDecodeError as e:
        # If parsing fails, try to provide more helpful error
        lines = snippet.split('\n')
        error_context = '\n'.join(lines[max(0, e.lineno - 3):e.lineno + 2])
        raise RuntimeError(
            f"JSON parsing failed at line {e.lineno}, column {e.colno}:\n"
            f"{e.msg}\n\n"
            f"Context:\n{error_context}"
        ) from e


class DeepSeekLLM:
    def __init__(self):
        """Initialize DeepSeek client lazily - only when this backend is selected"""
        from openai import OpenAI
        
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com")
        
        if not api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY not set. "
                "Add it to .env or run: ./install.sh"
            )
        
        # Clean the API key: strip whitespace and quotes
        api_key = api_key.strip()
        if (api_key.startswith('"') and api_key.endswith('"')) or \
           (api_key.startswith("'") and api_key.endswith("'")):
            api_key = api_key[1:-1]
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        # Get model from config.yaml (read directly to avoid import issues)
        config_model = None
        config_max_tokens = None
        
        try:
            from pathlib import Path
            import yaml

            config_paths = [
                Path.cwd() / "config.yaml",
                Path.home() / ".zenus" / "config.yaml",
            ]

            for config_path in config_paths:
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config_data = yaml.safe_load(f)
                        if config_data and 'llm' in config_data:
                            config_model = config_data['llm'].get('model')
                            config_max_tokens = config_data['llm'].get('max_tokens')
                            break
        except Exception:
            print(f"[DeepSeekLLM] WARNING: Failed to read config.yaml: {e}")
            import traceback
            traceback.print_exc()

        self.model = config_model or os.getenv("LLM_MODEL", "deepseek-chat")
        self.max_tokens = config_max_tokens or int(os.getenv("LLM_TOKENS", "8192"))

        if not config_model:
            print(f"[DeepSeekLLM] Using fallback model: {self.model}")

    def translate_intent(self, user_input: str, stream: bool = False) -> IntentIR:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": user_input},
            ],
            max_tokens=self.max_tokens
        )

        content = response.choices[0].message.content

        try:
            data = extract_json(content)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"DeepSeek returned invalid JSON:\n{content}"
            ) from e

        return IntentIR.model_validate(data)
    
    def reflect_on_goal(
        self,
        reflection_prompt: str,
        user_goal: str,
        observations: list,
        stream: bool = False
    ) -> str:
        """
        Reflect on whether a goal has been achieved
        
        Returns structured text with ACHIEVED, CONFIDENCE, REASONING, NEXT_STEPS
        """
        if stream:
            # Streaming mode
            from zenus_core.output.streaming import get_stream_handler
            handler = get_stream_handler()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a goal achievement evaluator. Analyze observations and determine if a user's goal has been achieved."
                    },
                    {
                        "role": "user",
                        "content": reflection_prompt
                    }
                ],
                max_tokens=1024,
                temperature=0.3,
                stream=True
            )
            
            return handler.stream_llm_tokens(response, prefix="Reflecting: ")
        else:
            # Non-streaming mode
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a goal achievement evaluator. Analyze observations and determine if a user's goal has been achieved."
                    },
                    {
                        "role": "user",
                        "content": reflection_prompt
                    }
                ],
                max_tokens=1024,
                temperature=0.3
            )
            
            return response.choices[0].message.content
