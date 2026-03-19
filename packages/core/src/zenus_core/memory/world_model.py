"""
World Model

Long-term memory about the system and user environment.
Persists across sessions.
"""

import os
import json
from typing import Optional, Dict, List
from datetime import datetime


class WorldModel:
    """
    Persistent world model for system and user knowledge
    
    Stores:
    - Frequently accessed paths
    - User preferences
    - Application locations
    - Recurring patterns
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            storage_path = os.path.expanduser("~/.zenus/world_model.json")
        
        self.storage_path = storage_path
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Load world model from disk"""
        
        if not os.path.exists(self.storage_path):
            return self._default_model()
        
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load world model: {e}")
            return self._default_model()
    
    def _default_model(self) -> Dict:
        """Create default world model structure"""
        
        return {
            "paths": {},  # Changed from frequent_paths for consistency
            "frequent_paths": {},
            "preferences": {},
            "applications": {},
            "patterns": [],
            "last_updated": datetime.now().isoformat()
        }
    
    def save(self):
        """Persist world model to disk"""
        
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
        self.data["last_updated"] = datetime.now().isoformat()
        
        with open(self.storage_path, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def add_frequent_path(self, path: str, access_count: int = 1):
        """Track frequently accessed paths"""
        
        path = os.path.expanduser(path)
        
        if path in self.data["frequent_paths"]:
            self.data["frequent_paths"][path] += access_count
        else:
            self.data["frequent_paths"][path] = access_count
        
        self.save()
    
    def update_path_frequency(self, path: str):
        """Alias for add_frequent_path (for backward compatibility)"""
        self.add_frequent_path(path, access_count=1)
    
    def get_frequent_paths(self, limit: int = 10) -> List[str]:
        """Get most frequently accessed paths"""
        
        sorted_paths = sorted(
            self.data["frequent_paths"].items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [path for path, _ in sorted_paths[:limit]]
    
    def set_preference(self, key: str, value: str):
        """Store a user preference"""
        
        self.data["preferences"][key] = value
        self.save()
    
    def get_preference(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a user preference"""
        
        return self.data["preferences"].get(key, default)
    
    def add_pattern(self, pattern_description: str):
        """
        Record a recurring pattern
        
        Examples:
        - "User organizes Downloads every Monday"
        - "Backups go to ~/Backups/<date>"
        - "Projects stored in ~/projects/"
        """
        
        pattern = {
            "description": pattern_description,
            "first_seen": datetime.now().isoformat(),
            "occurrences": 1
        }
        
        # Check if pattern already exists
        for p in self.data["patterns"]:
            if p["description"] == pattern_description:
                p["occurrences"] += 1
                self.save()
                return
        
        self.data["patterns"].append(pattern)
        self.save()
    
    def get_patterns(self) -> List[Dict]:
        """Get all recorded patterns"""
        
        return self.data["patterns"]
    
    def register_application(self, name: str, path: str, category: Optional[str] = None):
        """Register an application location"""
        
        self.data["applications"][name] = {
            "path": path,
            "category": category,
            "registered": datetime.now().isoformat()
        }
        
        self.save()
    
    def find_application(self, name: str) -> Optional[str]:
        """Find application path by name"""
        
        app = self.data["applications"].get(name)
        return app["path"] if app else None
    
    def get_summary(self) -> str:
        """Get human-readable summary of world model"""

        lines = [
            f"World Model (updated: {self.data['last_updated']})",
            f"Frequent paths: {len(self.data['frequent_paths'])}",
            f"Preferences: {len(self.data['preferences'])}",
            f"Applications: {len(self.data['applications'])}",
            f"Patterns: {len(self.data['patterns'])}"
        ]

        # Include knowledge graph stats when available
        try:
            from zenus_core.brain.knowledge_graph import get_knowledge_graph
            stats = get_knowledge_graph().get_stats()
            if stats["total_nodes"] > 0:
                lines.append(
                    f"Knowledge graph: {stats['total_nodes']} entities, "
                    f"{stats['total_edges']} relationships"
                )
        except Exception:
            pass

        return "\n".join(lines)
