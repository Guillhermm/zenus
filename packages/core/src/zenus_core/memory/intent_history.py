"""
Intent History

Persistent storage of past intents and their outcomes.
Used for learning patterns and improving future execution.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from zenus_core.audit.logger import _mask_secrets, _mask_dict


class IntentHistory:
    """
    Persistent intent history storage
    
    Stores all intents, plans, and outcomes for:
    - Learning from past executions
    - Understanding usage patterns
    - Debugging and auditing
    """
    
    def __init__(self, history_dir: Optional[str] = None):
        if history_dir is None:
            history_dir = os.path.expanduser("~/.zenus/history")
        
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        # Restrict history directory to owner only
        self.history_dir.chmod(0o700)

        # Current history file (daily)
        today = datetime.now().strftime("%Y-%m-%d")
        self.current_file = self.history_dir / f"intents_{today}.jsonl"
    
    def record(
        self, 
        user_input: str, 
        intent, 
        results: List[str],
        success: bool = True
    ):
        """
        Record an intent execution
        
        Args:
            user_input: Original user command
            intent: The IntentIR object
            results: List of step results
            success: Whether execution succeeded
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_input": _mask_secrets(user_input),
            "goal": intent.goal if hasattr(intent, 'goal') else str(intent),
            "steps_count": len(intent.steps) if hasattr(intent, 'steps') else 0,
            "success": success,
            "duration_seconds": 0,
            "results": [_mask_secrets(r) if isinstance(r, str) else r for r in results],
        }

        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        fd = os.open(self.current_file, flags, mode=0o600)
        try:
            with os.fdopen(fd, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            raise
    
    def get_recent(self, limit: int = 10) -> List[Dict]:
        """Get recent intent executions"""
        if not self.current_file.exists():
            return []
        
        entries = []
        with open(self.current_file, "r") as f:
            for line in f:
                entries.append(json.loads(line))
        
        return entries[-limit:]
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search intent history by query
        
        Searches in:
        - user_input
        - goal
        - result
        """
        query_lower = query.lower()
        matches = []
        
        # Search all history files
        for history_file in sorted(self.history_dir.glob("intents_*.jsonl"), reverse=True):
            with open(history_file, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    
                    # Search in relevant fields
                    searchable = " ".join([
                        entry.get("user_input", ""),
                        entry.get("goal", ""),
                        entry.get("result", "")
                    ]).lower()
                    
                    if query_lower in searchable:
                        matches.append(entry)
                        
                        if len(matches) >= limit:
                            return matches
        
        return matches
    
    def get_success_rate(self, days: int = 7) -> float:
        """Calculate success rate over last N days"""
        total = 0
        successes = 0
        
        # Get files from last N days
        cutoff = datetime.now().timestamp() - (days * 86400)
        
        for history_file in self.history_dir.glob("intents_*.jsonl"):
            if history_file.stat().st_mtime < cutoff:
                continue
            
            with open(history_file, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    total += 1
                    if entry.get("success"):
                        successes += 1
        
        return successes / total if total > 0 else 0.0
    
    def get_popular_goals(self, limit: int = 10) -> List[Dict]:
        """Get most frequently executed goal types"""
        goal_counts = {}
        
        for history_file in self.history_dir.glob("intents_*.jsonl"):
            with open(history_file, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    goal = entry.get("goal", "unknown")
                    
                    if goal not in goal_counts:
                        goal_counts[goal] = 0
                    goal_counts[goal] += 1
        
        # Sort by frequency
        popular = [
            {"goal": goal, "count": count}
            for goal, count in goal_counts.items()
        ]
        popular.sort(key=lambda x: x["count"], reverse=True)
        
        return popular[:limit]
    
    def analyze_failures(self, limit: int = 10) -> List[Dict]:
        """Get recent failures for analysis"""
        failures = []
        
        for history_file in sorted(self.history_dir.glob("intents_*.jsonl"), reverse=True):
            with open(history_file, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    if not entry.get("success"):
                        failures.append(entry)
                        
                        if len(failures) >= limit:
                            return failures
        
        return failures
