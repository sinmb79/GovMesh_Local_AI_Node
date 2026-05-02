"""Runtime provider interfaces and safe mock implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import subprocess
from typing import Any

from packages.govmesh_common import PolicyDecision


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, *, contexts: list[dict[str, Any]] | None = None) -> dict:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.called_count = 0

    def generate(self, prompt: str, *, contexts: list[dict[str, Any]] | None = None) -> dict:
        self.called_count += 1
        contexts = contexts or []
        evidence_ids = [context.get("chunk_id") for context in contexts if context.get("chunk_id")]
        if evidence_ids:
            text = f"근거 {', '.join(evidence_ids)}를 바탕으로 작성한 초안입니다."
        else:
            text = "근거가 부족하여 최종 판단을 내릴 수 없습니다."
        return {
            "provider": "mock",
            "text": text,
            "evidence_ids": evidence_ids,
            "is_draft": True,
        }


class LocalLlamaCppProvider(LLMProvider):
    def __init__(
        self,
        *,
        executable_path: str | Path,
        model_path: str | Path,
        approved: bool = False,
        pre_args: list[str] | None = None,
        timeout_seconds: int = 60,
        max_tokens: int = 128,
    ) -> None:
        self.executable_path = Path(executable_path)
        self.model_path = Path(model_path)
        self.approved = approved
        self.pre_args = pre_args or []
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    def generate(self, prompt: str, *, contexts: list[dict[str, Any]] | None = None) -> dict:
        if not self.approved:
            raise PermissionError("llama.cpp runtime must be explicitly approved before use")
        if not self.executable_path.exists():
            raise FileNotFoundError(f"llama.cpp executable not found: {self.executable_path}")
        if not self.model_path.exists():
            raise FileNotFoundError(f"llama.cpp model not found: {self.model_path}")

        context_text = "\n".join(context.get("snippet", "") for context in contexts or [])
        full_prompt = f"{context_text}\n\n{prompt}".strip()
        command = [
            str(self.executable_path),
            *self.pre_args,
            "-m",
            str(self.model_path),
            "-p",
            full_prompt,
            "-n",
            str(self.max_tokens),
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "llama.cpp runtime failed")
        return {
            "provider": "llama.cpp",
            "text": completed.stdout.strip(),
            "evidence_ids": [context.get("chunk_id") for context in contexts or [] if context.get("chunk_id")],
            "is_draft": True,
        }


class OllamaProvider(LLMProvider):
    def generate(self, prompt: str, *, contexts: list[dict[str, Any]] | None = None) -> dict:
        raise NotImplementedError("Ollama provider is a placeholder and must stay behind gateway policy.")


def generate_with_policy(
    provider: LLMProvider,
    prompt: str,
    decision: PolicyDecision,
    *,
    contexts: list[dict[str, Any]] | None = None,
) -> dict:
    """Call a provider only when policy allows the request."""

    if not decision.allow:
        return {
            "blocked": True,
            "text": decision.user_message,
            "block_reason": decision.block_reason,
            "evidence_ids": [],
            "is_draft": True,
        }
    result = provider.generate(decision.masked_text or prompt, contexts=contexts)
    result["blocked"] = False
    return result
