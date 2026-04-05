"""
Enhanced Interactive Shell

Features:
- Tab completion for commands and paths
- Syntax highlighting
- Multi-line input support
- Command history with Ctrl+R search
- Vi/Emacs key bindings
"""

from pathlib import Path
from typing import Optional
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings


class ZenusCompleter(Completer):
    """
    Custom completer for Zenus commands
    
    Provides:
    - Special command completion (status, memory, update, etc.)
    - Path completion for file operations
    - Common action verbs
    """
    
    # Special commands
    SPECIAL_COMMANDS = [
        'status', 'memory', 'model', 'history', 'rollback',
        'update', 'explain', 'workflow', 'help', 'exit', 'quit',
        'hooks', 'plan', 'skills', 'compact', 'add-dir', 'session',
        'tasks', 'doctor', 'output-style',
    ]
    
    # Common action verbs for natural language
    ACTION_VERBS = [
        'list', 'find', 'search', 'create', 'delete', 'move', 'copy',
        'rename', 'organize', 'sort', 'filter', 'analyze', 'scan',
        'backup', 'restore', 'compress', 'extract', 'install', 'update'
    ]
    
    # Common targets
    COMMON_TARGETS = [
        'files', 'folders', 'documents', 'images', 'downloads', 
        'desktop', 'home', 'projects', 'code', 'git'
    ]
    
    def __init__(self):
        self.path_completer = PathCompleter(
            expanduser=True,
            only_directories=False
        )
    
    def get_completions(self, document, complete_event):
        """Generate completions based on current input"""
        text = document.text_before_cursor
        word = document.get_word_before_cursor()
        
        # Special commands (at start of line)
        if not text or text.strip() == word:
            for cmd in self.SPECIAL_COMMANDS:
                if cmd.startswith(word.lower()):
                    yield Completion(
                        cmd,
                        start_position=-len(word),
                        display_meta='special command'
                    )
        
        # Path completion (if contains /)
        if '/' in word or word.startswith('~'):
            for completion in self.path_completer.get_completions(document, complete_event):
                yield completion
        
        # Action verbs
        elif len(word) > 1:
            for verb in self.ACTION_VERBS:
                if verb.startswith(word.lower()):
                    yield Completion(
                        verb,
                        start_position=-len(word),
                        display_meta='action'
                    )
            
            # Common targets
            for target in self.COMMON_TARGETS:
                if target.startswith(word.lower()):
                    yield Completion(
                        target,
                        start_position=-len(word),
                        display_meta='target'
                    )


class EnhancedShell:
    """
    Enhanced interactive shell with modern terminal features
    
    Features:
    - Tab completion
    - Syntax highlighting
    - Command history (persistent)
    - Auto-suggestions
    - Multi-line editing
    - Vi/Emacs bindings
    """
    
    def __init__(self, history_file: Optional[str] = None):
        # Setup history
        if history_file is None:
            history_dir = Path.home() / ".zenus"
            history_dir.mkdir(exist_ok=True)
            history_file = str(history_dir / "shell_history")
        
        self.history = FileHistory(history_file)
        
        # Setup completer
        self.completer = ZenusCompleter()
        
        # Setup style (syntax highlighting colors)
        self.style = Style.from_dict({
            'prompt': 'ansigreen bold',
            'command': 'ansiblue',
            'argument': 'ansicyan',
            'path': 'ansimagenta',
            '': '',  # Default
        })
        
        # Setup key bindings
        self.bindings = self._create_key_bindings()
        
        # Create session
        self.session = PromptSession(
            history=self.history,
            completer=self.completer,
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
            multiline=False,
            style=self.style,
            key_bindings=self.bindings
        )
    
    def _create_key_bindings(self) -> KeyBindings:
        """Create custom key bindings"""
        kb = KeyBindings()
        
        # Ctrl+D to exit (like bash)
        @kb.add('c-d')
        def _(event):
            event.app.exit(result='exit')
        
        # Ctrl+C to cancel current input
        @kb.add('c-c')
        def _(event):
            event.app.current_buffer.reset()
        
        return kb
    
    def prompt(self, message: str = None) -> str:
        """
        Show prompt and get user input
        
        Args:
            message: Prompt message (None = use default styled prompt)
        
        Returns:
            User input (stripped)
        """
        # Use styled prompt by default
        if message is None:
            from prompt_toolkit.formatted_text import HTML
            message = HTML('\n<ansigreen><b>zenus ></b></ansigreen> ')
        
        try:
            result = self.session.prompt(
                message,
                style=self.style
            )
            return result.strip()
        
        except KeyboardInterrupt:
            return ""
        
        except EOFError:
            return "exit"
    
    def multiline_prompt(self, message: str = "zenus >>> ") -> str:
        """
        Show multiline prompt
        
        Args:
            message: Prompt message
        
        Returns:
            User input (may contain newlines)
        """
        # Temporarily enable multiline
        original_multiline = self.session.multiline
        self.session.multiline = True
        
        try:
            result = self.session.prompt(
                message,
                style=self.style
            )
            return result.strip()
        
        except KeyboardInterrupt:
            return ""
        
        except EOFError:
            return "exit"
        
        finally:
            self.session.multiline = original_multiline


def create_enhanced_shell(history_file: Optional[str] = None) -> EnhancedShell:
    """
    Factory function to create enhanced shell
    
    Args:
        history_file: Path to history file (None = use default)
    
    Returns:
        EnhancedShell instance
    """
    return EnhancedShell(history_file=history_file)
