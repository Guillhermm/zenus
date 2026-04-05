"""
NotebookOps Tool

Read and edit Jupyter Notebook (.ipynb) files with full cell-type awareness.
Operates purely on the JSON structure — no kernel is required.

Actions:
  list_cells(path)                          — list all cells with indices
  read_cell(path, index)                    — read a single cell
  edit_cell(path, index, source)            — replace a cell's source
  add_cell(path, source, cell_type, index)  — insert a new cell
  delete_cell(path, index)                  — remove a cell
  read_output(path, index)                  — read the output of a cell
  clear_outputs(path)                       — clear all cell outputs
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from zenus_core.tools.base import Tool

_CELL_TYPES = ("code", "markdown", "raw")


class NotebookOps(Tool):
    """
    Read and edit Jupyter notebooks (.ipynb) without a running kernel.

    All operations work on the serialised notebook JSON and preserve the
    original file structure including metadata and outputs.
    """

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def list_cells(self, path: str) -> str:
        """
        List all cells in a notebook with their indices and types.

        Args:
            path: Path to the .ipynb file.

        Returns:
            Formatted list: ``[index] (type) first-line-of-source``
        """
        nb = self._load(path)
        cells = nb.get("cells", [])
        if not cells:
            return f"Notebook {path!r} has no cells."
        lines = [f"{len(cells)} cell(s) in {path}:"]
        for i, cell in enumerate(cells):
            ct = cell.get("cell_type", "?")
            src = "".join(cell.get("source", []))
            first_line = src.split("\n")[0][:80] if src else "(empty)"
            lines.append(f"  [{i}] ({ct}) {first_line}")
        return "\n".join(lines)

    def read_cell(self, path: str, index: int) -> str:
        """
        Return the full source of cell at *index*.

        Args:
            path:  Path to the .ipynb file.
            index: Zero-based cell index.
        """
        nb = self._load(path)
        cell = self._get_cell(nb, int(index))
        source = "".join(cell.get("source", []))
        ct = cell.get("cell_type", "?")
        return f"Cell [{index}] ({ct}):\n{source}"

    def read_output(self, path: str, index: int) -> str:
        """
        Return the last execution output of a code cell.

        Args:
            path:  Path to the .ipynb file.
            index: Zero-based cell index.
        """
        nb = self._load(path)
        cell = self._get_cell(nb, int(index))
        if cell.get("cell_type") != "code":
            return f"Cell [{index}] is type '{cell.get('cell_type')}' — only code cells have outputs."
        outputs = cell.get("outputs", [])
        if not outputs:
            return f"Cell [{index}] has no outputs."
        parts = []
        for out in outputs:
            if "text" in out:
                parts.append("".join(out["text"]))
            elif "data" in out:
                data = out["data"]
                if "text/plain" in data:
                    parts.append("".join(data["text/plain"]))
        return f"Output of cell [{index}]:\n" + "\n".join(parts) if parts else "(no text output)"

    # ------------------------------------------------------------------
    # Edit operations
    # ------------------------------------------------------------------

    def edit_cell(self, path: str, index: int, source: str) -> str:
        """
        Replace the source of cell at *index*.

        Args:
            path:   Path to the .ipynb file.
            index:  Zero-based cell index.
            source: New cell source (multi-line string).
        """
        nb = self._load(path)
        cell = self._get_cell(nb, int(index))
        cell["source"] = source.splitlines(keepends=True)
        self._save(path, nb)
        ct = cell.get("cell_type", "?")
        return f"Cell [{index}] ({ct}) updated in {path!r}."

    def add_cell(
        self,
        path: str,
        source: str,
        cell_type: str = "code",
        index: Optional[int] = None,
    ) -> str:
        """
        Insert a new cell into the notebook.

        Args:
            path:      Path to the .ipynb file.
            source:    Cell source content.
            cell_type: 'code', 'markdown', or 'raw' (default: 'code').
            index:     Insertion position (appends to end if omitted).
        """
        if cell_type not in _CELL_TYPES:
            return f"Invalid cell_type '{cell_type}'. Use: {', '.join(_CELL_TYPES)}."
        nb = self._load(path)
        cells = nb.setdefault("cells", [])

        new_cell: Dict[str, Any] = {
            "cell_type": cell_type,
            "source": source.splitlines(keepends=True),
            "metadata": {},
        }
        if cell_type == "code":
            new_cell["execution_count"] = None
            new_cell["outputs"] = []

        pos = int(index) if index is not None else len(cells)
        cells.insert(pos, new_cell)
        self._save(path, nb)
        return f"New {cell_type} cell inserted at [{pos}] in {path!r}."

    def delete_cell(self, path: str, index: int) -> str:
        """
        Remove the cell at *index*.

        Args:
            path:  Path to the .ipynb file.
            index: Zero-based cell index.
        """
        nb = self._load(path)
        cells = nb.get("cells", [])
        idx = int(index)
        if idx < 0 or idx >= len(cells):
            return f"Index {idx} out of range (notebook has {len(cells)} cells)."
        removed = cells.pop(idx)
        self._save(path, nb)
        ct = removed.get("cell_type", "?")
        return f"Cell [{idx}] ({ct}) deleted from {path!r}."

    def clear_outputs(self, path: str) -> str:
        """
        Clear the outputs and execution counts of all code cells.

        Args:
            path: Path to the .ipynb file.
        """
        nb = self._load(path)
        count = 0
        for cell in nb.get("cells", []):
            if cell.get("cell_type") == "code":
                cell["outputs"] = []
                cell["execution_count"] = None
                count += 1
        self._save(path, nb)
        return f"Cleared outputs for {count} code cell(s) in {path!r}."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(path: str) -> Dict[str, Any]:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Notebook not found: {path!r}")
        if p.suffix != ".ipynb":
            raise ValueError(f"Not a .ipynb file: {path!r}")
        data = json.loads(p.read_text(encoding="utf-8"))
        if "cells" not in data:
            data["cells"] = []
        return data

    @staticmethod
    def _save(path: str, nb: Dict[str, Any]) -> None:
        p = Path(path)
        p.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    @staticmethod
    def _get_cell(nb: Dict[str, Any], index: int) -> Dict[str, Any]:
        cells = nb.get("cells", [])
        if index < 0 or index >= len(cells):
            raise IndexError(
                f"Cell index {index} out of range (notebook has {len(cells)} cells)."
            )
        return cells[index]
