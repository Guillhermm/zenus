from dotenv import load_dotenv, find_dotenv # type: ignore
import os
from pathlib import Path
from zenus_core.brain.llm.schemas import IntentIR
from zenus_core.brain.llm.system_prompt import build_system_prompt


# Load secrets: ~/.zenus/.env first (system-wide), then project .env (from source)
_user_env = Path.home() / ".zenus" / ".env"
if _user_env.exists():
    load_dotenv(_user_env)
load_dotenv(find_dotenv(usecwd=True))


class OpenAILLM:
    def __init__(self):
        """Initialize OpenAI client lazily - only when this backend is selected"""
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_API_BASE_URL")
        
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not set. "
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
        except Exception as e:
            print(f"[OpenAILLM] WARNING: Failed to read config.yaml: {e}")
            import traceback
            traceback.print_exc()
        
        self.model = config_model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.max_tokens = config_max_tokens or int(os.getenv("OPENAI_MAX_TOKENS", "4096"))
        
        if not config_model:
            print(f"[OpenAILLM] Using fallback model: {self.model}")
    
    def translate_intent(self, user_input: str, stream: bool = False) -> IntentIR:
        response = self.client.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": user_input},
            ],
            response_format=IntentIR,
        )

        return response.choices[0].message.parsed
    
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


    def analyze_image(self, image_base64: str, prompt: str) -> str:
        """
        Analyze image using GPT-4 Vision
        
        Args:
            image_base64: Base64 encoded image
            prompt: Analysis prompt
        
        Returns:
            Analysis result
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-vision-preview",  # or gpt-4o which has vision
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            return f"Vision analysis failed: {str(e)}"

