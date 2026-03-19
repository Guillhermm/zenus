from dotenv import load_dotenv, find_dotenv # type: ignore
import json
import os
from pathlib import Path
from typing import List
from anthropic import Anthropic, AsyncAnthropic
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


class AnthropicLLM:
    def __init__(self):
        """Initialize Anthropic client lazily - only when this backend is selected"""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. "
                "Add it to .env or run: ./install.sh"
            )
        
        # Clean the API key: strip whitespace and quotes
        api_key = api_key.strip()
        # Remove quotes if present (common mistake in .env files)
        if (api_key.startswith('"') and api_key.endswith('"')) or \
           (api_key.startswith("'") and api_key.endswith("'")):
            api_key = api_key[1:-1]
        
        self.client = Anthropic(api_key=api_key)
        self.async_client = AsyncAnthropic(api_key=api_key)
        
        # Get model from config.yaml (read directly to avoid import issues)
        config_model = None
        config_max_tokens = None
        
        # Try to read config.yaml directly
        try:
            from pathlib import Path
            import yaml
            
            # Search for config.yaml in standard locations
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
            pass  # Silently fall back to env vars / defaults

        # Use config.yaml model if found, otherwise env var, otherwise default
        self.model = config_model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self.max_tokens = config_max_tokens or int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096"))
    
    def translate_intent(self, user_input: str, stream: bool = False) -> IntentIR:
        """
        Translate user intent to IntentIR using Claude
        
        Args:
            user_input: Natural language command
            stream: Enable streaming (avoids timeouts on long responses)
        
        Returns:
            IntentIR object
        """
        if stream:
            # Use streaming to avoid timeouts on long responses
            full_text = ""
            with self.client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=build_system_prompt(),
                messages=[
                    {"role": "user", "content": user_input}
                ]
            ) as stream:
                for text in stream.text_stream:
                    full_text += text
            
            content = full_text
        else:
            # Non-streaming mode
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=build_system_prompt(),
                messages=[
                    {"role": "user", "content": user_input}
                ]
            )
            content = response.content[0].text
        
        try:
            data = extract_json(content)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Claude returned invalid JSON:\n{content}"
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
            # Streaming mode - manually handle tokens (Anthropic format differs from OpenAI)
            from rich.console import Console
            import sys
            
            console = Console()
            console.print("[cyan]Reflecting: [/cyan]", end="")
            sys.stdout.flush()
            
            full_text = ""
            try:
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=1024,
                    system="You are a goal achievement evaluator. Analyze observations and determine if a user's goal has been achieved.",
                    messages=[
                        {"role": "user", "content": reflection_prompt}
                    ]
                ) as stream:
                    for text in stream.text_stream:
                        console.print(text, end="")
                        sys.stdout.flush()
                        full_text += text
                
                console.print()  # New line after streaming
            except Exception as e:
                console.print(f"\n[yellow]Reflection streaming error: {str(e)}[/yellow]")
                # Fall back to non-streaming on error
                return self.reflect_on_goal(reflection_prompt, user_goal, observations, stream=False)
            
            return full_text
        else:
            # Non-streaming mode
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system="You are a goal achievement evaluator. Analyze observations and determine if a user's goal has been achieved.",
                messages=[
                    {"role": "user", "content": reflection_prompt}
                ]
            )
            
            return response.content[0].text

    def ask(self, question: str, context: str = "") -> str:
        """Answer a direct question without JSON schema enforcement."""
        system = "You are a knowledgeable assistant. Answer concisely and accurately."
        if context:
            system += f"\n\nContext about the user's environment:\n{context}"
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": question}],
        )
        return response.content[0].text

    def generate(self, prompt: str) -> str:
        """Generate a free-form text response for a given prompt."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def analyze_image(self, image_base64: str, prompt: str) -> str:
        """
        Analyze image using Claude Vision
        
        Args:
            image_base64: Base64 encoded image
            prompt: Analysis prompt
        
        Returns:
            Analysis result
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
            
            return response.content[0].text
        
        except Exception as e:
            return f"Vision analysis failed: {str(e)}"

    # ------------------------------------------------------------------
    # Native async methods using AsyncAnthropic
    # ------------------------------------------------------------------

    async def atranslate_intent(self, user_input: str, stream: bool = False) -> IntentIR:
        """Native async translate_intent using AsyncAnthropic."""
        response = await self.async_client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=build_system_prompt(),
            messages=[{"role": "user", "content": user_input}],
        )
        content = response.content[0].text
        try:
            data = extract_json(content)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Claude returned invalid JSON:\n{content}") from e
        return IntentIR.model_validate(data)

    async def areflect_on_goal(
        self,
        reflection_prompt: str,
        user_goal: str,
        observations: List[str],
    ) -> str:
        """Native async reflect_on_goal using AsyncAnthropic."""
        response = await self.async_client.messages.create(
            model=self.model,
            max_tokens=1024,
            system="You are a goal achievement evaluator. Analyze observations and determine if a user's goal has been achieved.",
            messages=[{"role": "user", "content": reflection_prompt}],
        )
        return response.content[0].text

    async def agenerate(self, prompt: str) -> str:
        """Native async generate using AsyncAnthropic."""
        response = await self.async_client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
