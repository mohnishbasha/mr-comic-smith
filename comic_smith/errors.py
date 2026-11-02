"""Typed errors (ARCHITECTURE section 10). Every failure carries a code, stage, hint, and retry flag.

Front doors map these to exit codes (CLI) or RFC 9457 problem+json (server). Messages and hints
are plain words for the user; technical detail goes in `detail` and never contains secrets.
"""

from typing import Any, ClassVar

PROBLEM_TYPE_BASE = "https://getcomicsmith.com/problems/"


class ComicSmithError(Exception):
    """Base error; unexpected failures are wrapped in this at the front door."""

    code: ClassVar[str] = "internal_error"
    default_stage: ClassVar[str] = "any"
    title: ClassVar[str] = "Something went wrong"
    exit_code: ClassVar[int] = 1
    http_status: ClassVar[int] = 500
    default_retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        detail: str | None = None,
        stage: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.detail = detail
        self.stage = stage or self.default_stage
        self.retryable = self.default_retryable if retryable is None else retryable

    def to_problem(self, instance: str | None = None) -> dict[str, Any]:
        """Render as an RFC 9457 problem document with extension members."""
        problem: dict[str, Any] = {
            "type": PROBLEM_TYPE_BASE + self.code,
            "title": self.title,
            "status": self.http_status,
            "detail": self.message,
            "code": self.code,
            "stage": self.stage,
            "hint": self.hint,
            "retryable": self.retryable,
        }
        if instance is not None:
            problem["instance"] = instance
        return problem


class UsageError(ComicSmithError):
    code = "usage_invalid"
    default_stage = "cli"
    title = "The request was not valid"
    exit_code = 2
    http_status = 400


class ConfigError(UsageError):
    code = "config_invalid"
    default_stage = "config"
    title = "Configuration is not valid"


class ProviderStringError(ConfigError):
    code = "provider_string_invalid"
    title = "Provider string is not valid"


class PreflightError(ComicSmithError):
    code = "preflight_failed"
    default_stage = "preflight"
    title = "A required piece is missing"
    exit_code = 3
    http_status = 503
    default_retryable = True


class BackendUnavailableError(PreflightError):
    code = "backend_unavailable"
    title = "The backend is not reachable"


class ModelMissingError(PreflightError):
    code = "model_missing"
    title = "A model is not installed"


class ChromiumUnavailableError(PreflightError):
    code = "chromium_unavailable"
    title = "Chromium is not installed"


class NoncommercialGateError(PreflightError):
    code = "noncommercial_not_allowed"
    title = "Non-commercial model weights need opt-in"
    http_status = 403
    default_retryable = False


class CapabilityMissingError(PreflightError):
    code = "capability_missing"
    title = "The backend cannot do this"
    http_status = 422
    default_retryable = False


class SafetyError(ComicSmithError):
    code = "safety_blocked"
    default_stage = "story"
    title = "Blocked by a safety rule"
    exit_code = 4
    http_status = 422


class OriginalityBlockedError(SafetyError):
    code = "originality_blocked"
    default_stage = "cast"
    title = "Originality check blocked this request"


class PersonAttestationRequiredError(SafetyError):
    code = "person_attestation_required"
    default_stage = "cast"
    title = "Confirm you may use this person's likeness"


class AudienceBlockedError(SafetyError):
    code = "audience_blocked"
    title = "Not suitable for this audience"


class UploadRejectedError(SafetyError):
    code = "upload_rejected"
    default_stage = "ingest"
    title = "This file cannot be used"
    http_status = 415


class GenerationInvalidError(ComicSmithError):
    code = "generation_invalid"
    default_stage = "story"
    title = "The model returned something unusable"
    exit_code = 5
    http_status = 502
    default_retryable = True


class SchemaValidationError(GenerationInvalidError):
    code = "schema_invalid"
    title = "Output did not match the schema"


class LLMOutputInvalidError(GenerationInvalidError):
    code = "llm_output_invalid"
    title = "The language model reply was not valid"


class PrerequisiteError(GenerationInvalidError):
    code = "prerequisite_unmet"
    title = "A previous step is not done yet"
    http_status = 409
    default_retryable = False


class RenderError(ComicSmithError):
    code = "render_failed"
    default_stage = "render"
    title = "Drawing failed"
    exit_code = 6
    http_status = 502
    default_retryable = True


class ImageGenerationError(RenderError):
    code = "image_generation_failed"
    title = "The image backend failed"


class QaBlockedError(RenderError):
    code = "qa_blocked"
    default_stage = "qa"
    title = "The panel did not pass the consistency check"
    http_status = 422
    default_retryable = False


class LetteringError(RenderError):
    code = "lettering_failed"
    default_stage = "letter"
    title = "Lettering could not be placed"
    http_status = 422
    default_retryable = False


class JobCancelledError(RenderError):
    code = "job_cancelled"
    default_stage = "job"
    title = "The job was cancelled"
    http_status = 409
    default_retryable = False


class ExportError(ComicSmithError):
    code = "export_failed"
    default_stage = "export"
    title = "Export failed"
    exit_code = 7
    http_status = 500
    default_retryable = True


class PdfPostprocessError(ExportError):
    code = "pdf_postprocess_failed"
    title = "PDF post-processing failed"


class PackagingError(ExportError):
    code = "packaging_failed"
    title = "Packaging the export failed"


class ProjectError(ComicSmithError):
    code = "project_error"
    default_stage = "cli"
    title = "Project problem"
    exit_code = 8
    http_status = 409


class ProjectNotFoundError(ProjectError):
    code = "project_not_found"
    title = "Project not found"
    http_status = 404


class ProjectLockedError(ProjectError):
    code = "project_locked"
    title = "Project is locked"
    http_status = 423
    default_retryable = True


class ProjectMigrationError(ProjectError):
    code = "project_migration_failed"
    title = "Project could not be upgraded"
    http_status = 500


class ImmutableEntityError(ProjectError):
    code = "entity_immutable"
    default_stage = "story"
    title = "This item is locked"


class AuthError(ComicSmithError):
    code = "unauthorized"
    default_stage = "server"
    title = "Not authorized"
    exit_code = 3
    http_status = 401


class RateLimitError(ComicSmithError):
    code = "rate_limited"
    default_stage = "server"
    title = "Too many requests"
    exit_code = 3
    http_status = 429
    default_retryable = True
