"""
Tests for CLI command router
"""

import pytest
from zenus_cli.router import CommandRouter, CLICommand


class TestCommandRouter:
    """Test CLI routing logic"""
    
    def setup_method(self):
        """Set up router for each test"""
        self.router = CommandRouter()
    
    def test_no_args_routes_to_interactive(self):
        """No arguments should start interactive shell"""
        cmd = self.router.parse([])
        assert cmd.mode == "interactive"
        assert cmd.input_text is None
    
    def test_shell_command_routes_to_interactive(self):
        """Explicit 'shell' command should start interactive"""
        cmd = self.router.parse(["shell"])
        assert cmd.mode == "interactive"
    
    def test_help_flag_routes_to_help(self):
        """Help flags should show help"""
        for flag in ["help", "--help", "-h"]:
            cmd = self.router.parse([flag])
            assert cmd.mode == "help"
    
    def test_version_flag_routes_to_version(self):
        """Version flags should show version"""
        for flag in ["version", "--version", "-v"]:
            cmd = self.router.parse([flag])
            assert cmd.mode == "version"
    
    def test_direct_command_single_word(self):
        """Single word commands should be direct execution"""
        cmd = self.router.parse(["test"])
        assert cmd.mode == "direct"
        assert cmd.input_text == "test"
    
    def test_direct_command_multiple_words(self):
        """Multiple words should be joined as direct command"""
        cmd = self.router.parse(["list", "files", "in", "downloads"])
        assert cmd.mode == "direct"
        assert cmd.input_text == "list files in downloads"
    
    def test_dry_run_flag_parsing(self):
        """Dry run flag should be captured"""
        cmd = self.router.parse(["--dry-run", "delete", "files"])
        assert cmd.mode == "direct"
        assert cmd.input_text == "delete files"
        assert cmd.flags["dry_run"] is True
    
    def test_dry_run_flag_defaults_false(self):
        """Dry run should default to False"""
        cmd = self.router.parse(["test"])
        assert cmd.flags.get("dry_run", False) is False
    
    def test_show_help_outputs(self, capsys):
        """Help should print usage information"""
        self.router.show_help()
        captured = capsys.readouterr()
        assert "Zenus" in captured.out
        assert "USAGE:" in captured.out
        assert "EXAMPLES:" in captured.out
    
    def test_show_version_outputs(self, capsys):
        """Version should print version string"""
        self.router.show_version()
        captured = capsys.readouterr()
        assert "Zenus v" in captured.out
