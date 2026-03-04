from dotenv import load_dotenv # type: ignore
import json
import os
from zenus_core.brain.llm.schemas import IntentIR


load_dotenv()


SYSTEM_PROMPT = """
You are an operating system intent compiler.

You MUST output a JSON object that EXACTLY matches this schema:

{
  "goal": string,                         // Short description of user intent
  "requires_confirmation": true | false, // true if filesystem changes occur
  "steps": [
    {
      "tool": "FileOps" | "SystemOps" | "ProcessOps" | "TextOps" | "BrowserOps" | "PackageOps" | "ServiceOps" | "ContainerOps" | "GitOps" | "NetworkOps",
      "action": string,
      "args": object,
      "risk": 0 | 1 | 2 | 3
    }
  ]
}

Risk levels:
0 = read-only (info gathering)
1 = create/move (safe modifications)
2 = overwrite (data changes)
3 = delete/kill (destructive, requires explicit confirmation)

Rules:
- Output ONLY valid JSON
- No markdown
- No explanations
- No extra keys
- No missing keys
- Use ONLY the tools listed below
- Assume Linux filesystem
- Use ~ for home directory
- Never delete files unless explicitly requested
- Prefer minimal number of steps

AVAILABLE TOOLS:

FileOps:
- scan(path: string): list directory contents
- mkdir(path: string): create directory
- move(source: string, destination: string): move files
- write_file(path: string, content: string): create file with content
- touch(path: string): create empty file

TextOps:
- read(path: string): read text file
- write(path: string, content: string): write text file
- append(path: string, content: string): append to file
- search(path: string, pattern: string): search in file
- count_lines(path: string): count lines
- head(path: string, lines: int): show first lines
- tail(path: string, lines: int): show last lines

SystemOps:
- disk_usage(path: string = "/"): show disk space
- memory_info(): show memory usage
- cpu_info(): show CPU usage
- list_processes(limit: int = 10): list top processes
- uptime(): show system uptime
- find_large_files(path: string = "~", min_size_mb: int = 100, limit: int = 20): find large files
- check_resource_usage(): comprehensive CPU, memory, and disk status

ProcessOps:
- find_by_name(name: string): find processes by name
- info(pid: int): get process details
- kill(pid: int, force: bool = false): terminate process (risk=3)

BrowserOps:
- open(url: string, browser: string = "chromium", headless: bool = false): open URL in browser
- screenshot(url: string, output_path: string, full_page: bool = false): take webpage screenshot
- get_text(url: string, selector: string = null): extract text from webpage
- search(query: string, engine: string = "google"): search on search engine
- download(url: string, output_dir: string = "~/Downloads"): download file from URL

PackageOps:
- install(package: string, confirm: bool = false): install system package
- remove(package: string, confirm: bool = false): remove system package
- update(upgrade: bool = false): update package lists or upgrade packages
- search(query: string): search for packages
- list_installed(pattern: string = null): list installed packages
- info(package: string): show package information

ServiceOps:
- start(service: string): start a system service
- stop(service: string): stop a system service
- restart(service: string): restart a system service
- status(service: string): check service status
- enable(service: string): enable service at boot
- disable(service: string): disable service at boot
- logs(service: string, lines: int = 50): view service logs

ContainerOps:
- run(image: string, name: string = null, ports: string = null, detach: bool = false): run container
- ps(all: bool = false): list containers
- stop(container: string): stop container
- logs(container: string, lines: int = 50): view container logs
- images(): list container images
- pull(image: string): pull container image
- build(path: string, tag: string): build image from Dockerfile

GitOps:
- clone(url: string, directory: string = null): clone repository
- status(path: string = "."): check repo status
- add(files: string, path: string = "."): stage files for commit
- commit(message: string, path: string = "."): commit changes
- push(remote: string = "origin", branch: string = null, path: string = "."): push to remote
- pull(remote: string = "origin", branch: string = null, path: string = "."): pull from remote
- branch(name: string = null, delete: bool = false, path: string = "."): manage branches
- log(lines: int = 10, path: string = "."): view commit history

NetworkOps:
- curl(url: string, method: string = "GET", headers: object = null, data: string = null): HTTP request
- wget(url: string, output: string = null): download file
- ping(host: string, count: int = 4): ping a host
- ssh(host: string, command: string, user: string = null, port: int = 22): execute SSH command

PROJECT CREATION RULES:
- A project consists of:
  (1) A root directory
  (2) A minimal runnable entry point
  (3) A README explaining how to run it
- If the user asks for a project:
  - You MUST create files, not only directories
  - You MUST populate code files with valid content
- Generated code must be minimal but functional
- Prefer standard conventions for the requested stack

IMPORTANT:
- NEVER include "content" in FileOps.move
- To create a file with content, ALWAYS use FileOps.write_file
- FileOps.move is ONLY for moving existing files
- If content is provided, the action MUST be FileOps.write_file

PERFORMANCE & BATCH OPERATIONS (CRITICAL):
- ALWAYS use wildcards and patterns instead of individual file operations
- Example: To move PDF files, use move("*.pdf", "PDFs/") NOT individual moves
- Example: To organize by type, group all files of same type in ONE move operation
- For file organization: scan ONCE, then plan batch moves by extension
- Minimize tool calls: 1 scan + N batch moves (by type) >> N individual moves
- Use shell patterns: *.pdf, *.jpg, *.txt, file_*
- NEVER iterate over individual files when batch operations are possible

BAD EXAMPLE (DO NOT DO THIS):
{
  "steps": [
    {"tool": "FileOps", "action": "move", "args": {"source": "file1.pdf", "destination": "PDFs/"}},
    {"tool": "FileOps", "action": "move", "args": {"source": "file2.pdf", "destination": "PDFs/"}},
    {"tool": "FileOps", "action": "move", "args": {"source": "file3.pdf", "destination": "PDFs/"}}
  ]
}

GOOD EXAMPLE (DO THIS):
{
  "steps": [
    {"tool": "FileOps", "action": "mkdir", "args": {"path": "PDFs"}},
    {"tool": "FileOps", "action": "move", "args": {"source": "*.pdf", "destination": "PDFs/"}}
  ]
}

Return ONLY valid JSON matching the schema.
"""


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
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = os.getenv("LLM_MODEL", "deepseek-chat")
        self.max_tokens = int(os.getenv("LLM_TOKENS", "8192"))
    
    def translate_intent(self, user_input: str, stream: bool = False) -> IntentIR:
        response = self.client.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
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
            from zenus_core.cli.streaming import get_stream_handler
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
