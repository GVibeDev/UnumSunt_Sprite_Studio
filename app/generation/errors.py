from __future__ import annotations


class GenerationError(RuntimeError):
    """Base error for normalized generation failures."""

    code = 'GENERATION_ERROR'


class ProviderUnavailableError(GenerationError):
    code = 'PROVIDER_UNAVAILABLE'


class InvalidGenerationRequestError(GenerationError):
    code = 'INVALID_REQUEST'


class GenerationCancelledError(GenerationError):
    code = 'USER_CANCELLED'


class OutputNotFoundError(GenerationError):
    code = 'OUTPUT_NOT_FOUND'


class LocalRuntimeNotInstalledError(GenerationError):
    code = 'LOCAL_RUNTIME_NOT_INSTALLED'


class PythonEnvironmentBrokenError(GenerationError):
    code = 'PYTHON_ENVIRONMENT_BROKEN'


class ProcessCrashError(GenerationError):
    code = 'PROCESS_CRASH'


class ModelNotInstalledError(GenerationError):
    code = 'MODEL_NOT_INSTALLED'


class DependencyError(GenerationError):
    code = 'DEPENDENCY_ERROR'
