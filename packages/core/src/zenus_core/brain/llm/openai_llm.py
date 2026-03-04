from dotenv import load_dotenv, find_dotenv # type: ignore
import os
from zenus_core.brain.llm.schemas import IntentIR


# Load secrets - find_dotenv searches up directory tree for .env
load_dotenv(find_dotenv(usecwd=True))


SYSTEM_PROMPT = """
You are an operating system intent compiler.

Rules:
- Convert user intent into structured OS actions
- NEVER invent tools
- NEVER include destructive actions unless explicitly requested
- Assume Linux filesystem
- Prefer safe, minimal steps

Allowed tools:
- FileOps: scan, mkdir, move, write_file, touch
- TextOps: read, write, append, search, count_lines, head, tail
- SystemOps: disk_usage, memory_info, cpu_info, list_processes, uptime, find_large_files, check_resource_usage
- ProcessOps: find_by_name, info, kill
- BrowserOps: open, screenshot, get_text, search, download
- PackageOps: install, remove, update, search, list_installed, info
- ServiceOps: start, stop, restart, status, enable, disable, logs
- ContainerOps: run, ps, stop, logs, images, pull, build
- GitOps: clone, status, add, commit, push, pull, branch, log
- NetworkOps: curl, wget, ping, ssh

Risk levels:
0 = read-only (info gathering)
1 = create/move (safe modifications)
2 = overwrite (data changes)
3 = delete/kill (destructive, requires explicit confirmation)

PERFORMANCE (CRITICAL):
- Use wildcards and batch operations instead of individual files
- Example: move("*.pdf", "PDFs/") NOT individual file moves
- Minimize tool calls by grouping operations
- Use patterns: *.pdf, *.jpg, *.txt

Return ONLY valid JSON matching the schema.
"""


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
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
    
    def translate_intent(self, user_input: str, stream: bool = False) -> IntentIR:
        response = self.client.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
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
            from zenus_core.cli.streaming import get_stream_handler
            handler = get_stream_handler()
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
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
                model="gpt-4o-mini",
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

