from dataclasses import dataclass
from typing import Final

from app.models.template_field import TemplateField
from app.repositories.template_field_repository import TemplateFieldRepository
from app.repositories.template_repository import TemplateRepository

SUPPORTED_FIELD_TYPES: Final[set[str]] = {"text", "select", "number", "boolean"}


@dataclass(frozen=True)
class DesignValidationError(ValueError):
    """Raised when submitted Design customization data violates the MVP contract.

    Attributes:
        code: Stable rejection reason for service and test assertions.
        message: Human-readable explanation of the validation failure.
    """

    code: str
    message: str

    def __str__(self) -> str:
        """Return the human-readable validation failure message.

        Returns:
            The message attached to this validation failure.
        """
        return self.message


class DesignValidationService:
    """Validate submitted Design customization values before persistence.

    The service loads backend Template and TemplateField definitions, validates
    submitted customization values against the MVP contract, and returns only
    accepted values. It does not persist Designs, calculate pricing, or expose
    endpoint behavior.
    """

    def __init__(
        self,
        template_repository: TemplateRepository,
        template_field_repository: TemplateFieldRepository,
    ) -> None:
        """Store repositories used to read backend validation rules.

        Args:
            template_repository: Repository used to load Templates, including
                inactive Templates for rejection.
            template_field_repository: Repository used to load active
                TemplateFields for an active Template.
        """
        self.template_repository = template_repository
        self.template_field_repository = template_field_repository

    def validate_customization(
        self,
        template_id: int,
        customization_values: dict[str, object],
    ) -> dict[str, object]:
        """Validate one submitted customization payload for a Template.

        Args:
            template_id: Identifier of the Template selected by the user.
            customization_values: Submitted customization object keyed by
                TemplateField field_name.

        Returns:
            A deterministic copy of accepted customization values keyed by
            TemplateField field_name.

        Raises:
            DesignValidationError: If the Template is missing or inactive, the
                submitted object does not match active TemplateFields, or any
                value violates the MVP customization contract.
        """
        if not isinstance(customization_values, dict):
            raise DesignValidationError(
                code="invalid_customization_shape",
                message="Customization values must be an object.",
            )

        template = self.template_repository.get_template_by_id(template_id)
        if template is None:
            raise DesignValidationError(
                code="template_not_found",
                message="Template does not exist.",
            )
        if not template.is_active:
            raise DesignValidationError(
                code="template_inactive",
                message="Template is inactive.",
            )

        template_fields = self.template_field_repository.get_active_fields_for_template(template_id)
        fields_by_name = self._index_template_fields(template_fields)
        submitted_names = set(customization_values)
        field_names = set(fields_by_name)

        unknown_field_names = submitted_names - field_names
        if unknown_field_names:
            raise DesignValidationError(
                code="unknown_template_field",
                message="Customization includes fields not defined for the Template.",
            )

        missing_required_fields = [
            field.field_name
            for field in template_fields
            if field.is_required and field.field_name not in customization_values
        ]
        if missing_required_fields:
            raise DesignValidationError(
                code="missing_required_field",
                message="Customization is missing required TemplateFields.",
            )

        accepted_values: dict[str, object] = {}
        for field in template_fields:
            if field.field_name not in customization_values:
                continue
            submitted_value = customization_values[field.field_name]
            accepted_values[field.field_name] = self._validate_field_value(
                field,
                submitted_value,
            )

        return accepted_values

    def _index_template_fields(
        self,
        template_fields: list[TemplateField],
    ) -> dict[str, TemplateField]:
        """Index active TemplateFields by field_name and reject ambiguity.

        Args:
            template_fields: Active TemplateFields loaded for one Template.

        Returns:
            Mapping from TemplateField field_name to TemplateField.

        Raises:
            DesignValidationError: If a field has an unsupported field_type or
                duplicate field_name.
        """
        fields_by_name: dict[str, TemplateField] = {}
        for field in template_fields:
            if field.field_type not in SUPPORTED_FIELD_TYPES:
                raise DesignValidationError(
                    code="unsupported_field_type",
                    message="TemplateField uses an unsupported field type.",
                )
            if field.field_name in fields_by_name:
                raise DesignValidationError(
                    code="ambiguous_template_field",
                    message="TemplateField names must be unique for a Template.",
                )
            fields_by_name[field.field_name] = field
        return fields_by_name

    def _validate_field_value(
        self,
        field: TemplateField,
        submitted_value: object,
    ) -> object:
        """Validate one submitted value against one TemplateField.

        Args:
            field: TemplateField definition loaded from the backend.
            submitted_value: Submitted value for the TemplateField.

        Returns:
            The accepted submitted value.

        Raises:
            DesignValidationError: If the value or allowed_values metadata does
                not match the TemplateField field_type contract.
        """
        if submitted_value is None or isinstance(submitted_value, (list, dict)):
            raise DesignValidationError(
                code="invalid_value_type",
                message="Customization value type is invalid.",
            )

        if field.field_type == "text":
            self._ensure_allowed_values_is_null(field)
            if not isinstance(submitted_value, str):
                raise DesignValidationError(
                    code="invalid_value_type",
                    message="Text fields require string values.",
                )
            if field.is_required and submitted_value.strip() == "":
                raise DesignValidationError(
                    code="missing_required_field",
                    message="Required text fields cannot be empty.",
                )
            return submitted_value

        if field.field_type == "select":
            if not isinstance(field.allowed_values, list) or not field.allowed_values:
                raise DesignValidationError(
                    code="invalid_allowed_values",
                    message="Select fields require non-empty allowed_values.",
                )
            if not isinstance(submitted_value, str):
                raise DesignValidationError(
                    code="invalid_value_type",
                    message="Select fields require string values.",
                )
            if field.is_required and submitted_value.strip() == "":
                raise DesignValidationError(
                    code="missing_required_field",
                    message="Required select fields cannot be empty.",
                )
            if submitted_value not in field.allowed_values:
                raise DesignValidationError(
                    code="invalid_select_value",
                    message="Select value is not allowed.",
                )
            return submitted_value

        if field.field_type == "number":
            self._ensure_allowed_values_is_null(field)
            if isinstance(submitted_value, bool) or not isinstance(
                submitted_value,
                (int, float),
            ):
                raise DesignValidationError(
                    code="invalid_value_type",
                    message="Number fields require numeric values.",
                )
            return submitted_value

        if field.field_type == "boolean":
            self._ensure_allowed_values_is_null(field)
            if not isinstance(submitted_value, bool):
                raise DesignValidationError(
                    code="invalid_value_type",
                    message="Boolean fields require boolean values.",
                )
            return submitted_value

        raise DesignValidationError(
            code="unsupported_field_type",
            message="TemplateField uses an unsupported field type.",
        )

    def _ensure_allowed_values_is_null(self, field: TemplateField) -> None:
        """Reject TemplateField metadata that conflicts with MVP field semantics.

        Args:
            field: TemplateField whose allowed_values shape should be checked.

        Raises:
            DesignValidationError: If allowed_values is not null for a field
                type that does not support it in MVP.
        """
        if field.allowed_values is not None:
            raise DesignValidationError(
                code="invalid_allowed_values",
                message="This field type does not support allowed_values.",
            )
