import glob
import os
import shutil
from pathlib import Path
from zenus_core.tools.base import Tool


def _resolve(path: str) -> str:
    """Expand user and resolve the canonical path (follows symlinks).

    Using resolve() instead of expanduser() alone means that traversal
    sequences like ``../../etc/shadow`` and symlinks pointing outside the
    intended directory are normalised before any operation is performed.
    """
    return str(Path(path).expanduser().resolve())


class FileOps(Tool):
    name = "FileOps"

    def scan(self, path: str):
        return os.listdir(_resolve(path))

    def mkdir(self, path: str):
        os.makedirs(_resolve(path), exist_ok=True)
        return f"Directory created: {path}"

    def move(self, source: str, destination: str):
        src_pattern = str(Path(source).expanduser())  # glob before resolve
        dst = _resolve(destination)

        matched = glob.glob(src_pattern)
        for p in matched:
            shutil.move(_resolve(p), dst)
        return f"Moved files matching {source} -> {destination}"
    
    def write_file(self, path: str, content: str):
        """
        Write content to file with support for large files

        Args:
            path: File path
            content: Content to write (supports large strings)

        Returns:
            Success message with file size
        """
        full = _resolve(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        
        # Write in chunks for large content (>10MB)
        chunk_size = 10 * 1024 * 1024  # 10MB chunks
        
        try:
            with open(full, "w", encoding='utf-8') as f:
                if len(content) > chunk_size:
                    # Write in chunks for large files
                    for i in range(0, len(content), chunk_size):
                        f.write(content[i:i + chunk_size])
                else:
                    # Write all at once for small files
                    f.write(content)
            
            # Calculate file size
            size_bytes = len(content.encode('utf-8'))
            if size_bytes < 1024:
                size_str = f"{size_bytes}B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f}KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.1f}MB"
            
            return f"File written: {path} ({size_str})"
        
        except Exception as e:
            return f"Failed to write {path}: {str(e)}"


    def touch(self, path: str):
        full = _resolve(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, "a").close()
        return f"File created: {path}"