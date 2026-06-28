# VENDORED VERBATIM from base/sdna/sdna/config.py (HermesConfigInput + DovetailModel — the GENERAL
# Dovetail core: dot-extraction, file_inputs with the >10k-char pointer rule (never-truncate),
# expected_outputs validation, prepare_next_inputs). The only heaven-scoped dovetail (history_id) is
# NOT here — these two classes are pure pydantic + stdlib. Copied (not reimplemented) so cave-teams has
# the typed data-flow joint while staying standalone. Keep in sync with SDNA's if it changes.
"""
Dovetail — the typed joint between two Links in a chain.

Declares the expected outputs of the previous step and how to map them into the named inputs of the
next step, with file loading (JSON→dict; plain→str; >10k chars → a "read {path}" pointer) and output
validation. This is the DATA plane that complements chain_ontology's CONTROL plane.
"""

from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HermesConfigInput(BaseModel):
    """
    Defines how to extract and transform a single input
    from a previous step's output.
    """
    source_key: str  # Dot-notation path (e.g., "result.files.0")
    transform: Optional[Callable[[Any], Any]] = None
    required: bool = True
    default: Any = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def extract(self, data: Dict[str, Any]) -> Any:
        """Extract value from data using source_key path."""
        value = data
        for part in self.source_key.split('.'):
            if value is None:
                break
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, (list, tuple)) and part.isdigit():
                idx = int(part)
                value = value[idx] if idx < len(value) else None
            else:
                value = None

        if value is None:
            if self.required:
                raise ValueError(f"Required input '{self.source_key}' not found")
            return self.default

        if self.transform:
            value = self.transform(value)

        return value


class DovetailModel(BaseModel):
    """
    The joint between two configs in a chain.

    Declares expected outputs from previous step and
    how to map them to inputs for the next step.

    file_inputs: Load files into context before extraction.
        Maps context key to file path. Files are loaded as:
        - dict if valid JSON
        - str (full contents) if not JSON and <= 10k chars
        - str "You must read {path} before continuing" if > 10k chars
    """
    name: str = ""
    expected_outputs: List[str] = Field(default_factory=list)
    input_map: Dict[str, HermesConfigInput] = Field(default_factory=dict)
    file_inputs: Dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    FILE_INLINE_LIMIT: int = 10_000

    def _load_file_inputs(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Load file_inputs into context. JSON parsed to dict, else str or read pointer."""
        import json as _json
        from pathlib import Path as _Path

        ctx = dict(context)
        for key, file_path in self.file_inputs.items():
            p = _Path(file_path)
            if not p.exists():
                ctx[key] = None
                continue
            raw = p.read_text()
            try:
                ctx[key] = _json.loads(raw)
                continue
            except (_json.JSONDecodeError, ValueError):
                pass
            if len(raw) <= self.FILE_INLINE_LIMIT:
                ctx[key] = raw
            else:
                ctx[key] = f"You must read {file_path} before continuing"
        return ctx

    def validate_outputs(self, result: Dict[str, Any]) -> List[str]:
        """Check expected outputs are present. Returns missing keys."""
        missing = []
        for key in self.expected_outputs:
            value = result
            for part in key.split('.'):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = None
                    break
            if value is None:
                missing.append(key)
        return missing

    def prepare_next_inputs(self, previous_result: Dict[str, Any]) -> Dict[str, Any]:
        """Load file_inputs into context, then extract via input_map."""
        enriched = self._load_file_inputs(previous_result)

        missing = self.validate_outputs(enriched)
        if missing:
            raise ValueError(f"Dovetail '{self.name}' missing outputs: {missing}")

        next_inputs = {}
        for input_name, input_spec in self.input_map.items():
            next_inputs[input_name] = input_spec.extract(enriched)

        return next_inputs
