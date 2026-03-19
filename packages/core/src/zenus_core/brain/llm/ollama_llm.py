"""
Ollama LLM Backend

Local LLM support using Ollama.
Optimized for low-resource machines (4-16GB RAM).

Recommended models:
- phi3:mini (3.8GB) - Fast, efficient
- llama3.2:3b (2GB) - Lightweight
- qwen2.5:3b (2.3GB) - Good reasoning
"""

import json
import requests
from zenus_core.brain.llm.schemas import IntentIR
from zenus_core.brain.llm.system_prompt import build_system_prompt


class OllamaLLM:
    """
    Ollama backend for local LLM execution
    
    Requires Ollama installed: https://ollama.ai/
    Install: curl -fsSL https://ollama.com/install.sh | sh
    """
    
    def __init__(
        self, 
        model: str = "phi3:mini",
        base_url: str = "http://localhost:11434"
    ):
        self.model = model
        self.base_url = base_url
        self._check_ollama()
    
    def _check_ollama(self):
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            if response.status_code != 200:
                raise RuntimeError("Ollama is not responding")
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Ollama not running. Start with: ollama serve\n"
                "Install from: https://ollama.com/download"
            )
    
    def translate_intent(self, user_input: str, stream: bool = False) -> IntentIR:
        """Translate user input to Intent IR using Ollama"""
        
        prompt = f"{build_system_prompt()}\n\nUser: {user_input}\n\nJSON:"
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",  # Force JSON output
                    "options": {
                        "temperature": 0.1,      # More deterministic
                        "num_predict": 2048,     # Allow longer responses
                        "num_ctx": 8192,         # Larger context window
                        "top_k": 10,
                        "top_p": 0.9
                    }
                },
                timeout=300  # 5 minutes (was 30s)
            )
            
            if response.status_code != 200:
                raise RuntimeError(f"Ollama error: {response.status_code}")
            
            result = response.json()
            content = result.get("response", "")
            
            # Extract JSON from response
            content = self._extract_json(content)
            
            # Parse and validate
            data = json.loads(content)
            return IntentIR.model_validate(data)
            
        except requests.exceptions.Timeout:
            raise RuntimeError("Ollama request timed out")
        except json.JSONDecodeError:
            raise RuntimeError(f"Invalid JSON from Ollama: {content}")
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON object from text"""
        # Remove markdown code blocks
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        
        # Find JSON object boundaries
        start = text.find("{")
        end = text.rfind("}") + 1
        
        if start == -1 or end == 0:
            return text
        
        return text[start:end]
    
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
        try:
            if stream:
                # Streaming mode
                from zenus_core.output.streaming import get_stream_handler
                from rich.console import Console
                get_stream_handler()
                console = Console()
                
                console.print("[cyan]Reflecting: [/cyan]", end="")
                
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": reflection_prompt,
                        "stream": True,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": 1024,
                            "num_ctx": 8192
                        }
                    },
                    timeout=60,
                    stream=True
                )
                
                complete_text = ""
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            token = chunk["response"]
                            console.print(token, end="")
                            complete_text += token
                        if chunk.get("done", False):
                            break
                
                console.print()  # New line
                return complete_text
            else:
                # Non-streaming mode
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": reflection_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": 1024,
                            "num_ctx": 8192
                        }
                    },
                    timeout=60
                )
                
                if response.status_code != 200:
                    raise RuntimeError(f"Ollama error: {response.status_code}")
                
                result = response.json()
                return result.get("response", "")
            
        except requests.exceptions.Timeout:
            raise RuntimeError("Ollama reflection timed out")
        except Exception as e:
            raise RuntimeError(f"Ollama reflection failed: {e}")

    def ask(self, question: str, context: str = "") -> str:
        """Answer a direct question without JSON schema enforcement."""
        prompt = question
        if context:
            prompt = f"Context:\n{context}\n\nQuestion: {question}"
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "system": "You are a knowledgeable assistant. Answer concisely and accurately.",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 1024, "num_ctx": 8192},
            },
            timeout=60,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Ollama ask error: {response.status_code}")
        return response.json().get("response", "")

    def generate(self, prompt: str) -> str:
        """Generate a free-form text response for a given prompt."""
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 2048,
                    "num_ctx": 8192,
                },
            },
            timeout=60,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Ollama generate error: {response.status_code}")
        return response.json().get("response", "")
