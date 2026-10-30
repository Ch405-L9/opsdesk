"""Project-specific exception types."""


class WebAgentResumeBuilderError(Exception):
    """Base exception for the application."""


class ConfigurationError(WebAgentResumeBuilderError):
    """Raised when configuration is missing, invalid, or unsafe."""


class SafetyViolationError(WebAgentResumeBuilderError):
    """Raised when an operation would cross a safety boundary."""


class EvidenceValidationError(WebAgentResumeBuilderError):
    """Raised when candidate evidence is missing or invalid."""


class ArtifactError(WebAgentResumeBuilderError):
    """Raised when an artifact cannot be safely created or verified."""


class OllamaConnectionError(WebAgentResumeBuilderError):
    """Raised when the local Ollama service cannot be reached."""

