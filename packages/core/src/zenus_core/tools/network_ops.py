"""
Network Operations

Network utilities: curl, wget, ping, ssh, etc.
"""

import subprocess
import os
from pathlib import Path
from typing import Optional, Dict
from zenus_core.tools.base import Tool

_ALLOWED_URL_SCHEMES = ("http://", "https://", "ftp://", "ftps://")


def _validate_url(url: str) -> None:
    """Reject non-HTTP(S)/FTP URLs to prevent unexpected protocol abuse."""
    if not any(url.lower().startswith(s) for s in _ALLOWED_URL_SCHEMES):
        raise ValueError(
            f"Unsupported URL scheme. Allowed: {', '.join(_ALLOWED_URL_SCHEMES)}"
        )


def _safe_output_path(output: str) -> str:
    """Resolve an output file path to its canonical form."""
    return str(Path(output).expanduser().resolve())


class NetworkOps(Tool):
    """
    Network operations and utilities
    
    Capabilities:
    - HTTP requests (curl, wget)
    - Network diagnostics (ping, traceroute)
    - SSH operations
    - Port scanning
    """
    
    def curl(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[str] = None,
        output: Optional[str] = None
    ) -> str:
        """
        Make HTTP request with curl
        
        Args:
            url: URL to request
            method: HTTP method (GET, POST, PUT, DELETE)
            headers: HTTP headers
            data: Request body (for POST/PUT)
            output: Save to file
        """
        try:
            _validate_url(url)
        except ValueError as exc:
            return f"Error: {exc}"

        cmd = ["curl", "-X", method]

        if headers:
            for key, value in headers.items():
                cmd.extend(["-H", f"{key}: {value}"])

        if data:
            cmd.extend(["-d", data])

        if output:
            cmd.extend(["-o", _safe_output_path(output)])
        else:
            cmd.append("-s")  # Silent mode if not saving

        cmd.append(url)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if output:
                return f"Saved to {output}"
            
            return result.stdout
        except Exception as e:
            return f"Error: {str(e)}"
    
    def wget(self, url: str, output: Optional[str] = None) -> str:
        """
        Download file with wget

        Args:
            url: URL to download
            output: Output filename
        """
        try:
            _validate_url(url)
        except ValueError as exc:
            return f"Error: {exc}"

        cmd = ["wget"]

        if output:
            cmd.extend(["-O", _safe_output_path(output)])
        
        cmd.append(url)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 min
            )
            
            return result.stdout + result.stderr
        except Exception as e:
            return f"Error: {str(e)}"
    
    def ping(self, host: str, count: int = 4) -> str:
        """
        Ping a host
        
        Args:
            host: Hostname or IP
            count: Number of pings
        """
        try:
            result = subprocess.run(
                ["ping", "-c", str(count), host],
                capture_output=True,
                text=True,
                timeout=count + 5
            )
            return result.stdout
        except Exception as e:
            return f"Error: {str(e)}"
    
    def traceroute(self, host: str) -> str:
        """Trace route to host"""
        try:
            # Try traceroute, fall back to tracepath
            cmd = ["traceroute", host]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                # Try tracepath
                result = subprocess.run(
                    ["tracepath", host],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
            
            return result.stdout
        except Exception as e:
            return f"Error: {str(e)}"
    
    def ssh(
        self,
        host: str,
        command: Optional[str] = None,
        user: Optional[str] = None,
        port: int = 22
    ) -> str:
        """
        SSH to remote host
        
        Args:
            host: Hostname or IP
            command: Command to execute (None for interactive)
            user: Username
            port: SSH port
        """
        cmd = ["ssh", "-p", str(port)]
        
        if user:
            cmd.append(f"{user}@{host}")
        else:
            cmd.append(host)
        
        if command:
            cmd.append(command)
        else:
            return "Error: Interactive SSH not supported (provide command)"
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.stdout
        except Exception as e:
            return f"Error: {str(e)}"
    
    def netstat(self, listening: bool = False) -> str:
        """
        Show network connections
        
        Args:
            listening: Show only listening ports
        """
        try:
            # Try ss (modern) first
            cmd = ["ss", "-tuln"] if listening else ["ss", "-tun"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                # Fall back to netstat
                cmd = ["netstat", "-tuln"] if listening else ["netstat", "-tun"]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            return result.stdout
        except Exception as e:
            return f"Error: {str(e)}"
    
    def nslookup(self, domain: str) -> str:
        """DNS lookup"""
        try:
            result = subprocess.run(
                ["nslookup", domain],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout
        except Exception as e:
            return f"Error: {str(e)}"
