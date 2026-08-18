from copy import deepcopy
from django.core.exceptions import ValidationError

ACTIONS = {"navigate", "click", "fill", "select", "assert_text", "assert_url", "wait_for"}
LOCATOR_STRATEGIES = {"role", "label", "placeholder", "test_id", "css"}
LOCATOR_ACTIONS = {"click", "fill", "select", "assert_text", "wait_for"}
ALLOWED_STEP_KEYS = {"id", "action", "url", "value", "locator", "postcondition", "timeout_ms"}
ALLOWED_LOCATOR_KEYS = {"strategy", "role", "name", "value", "exact"}


def validate_locator(locator):
    if not isinstance(locator, dict):
        raise ValidationError("locator must be an object")
    unknown = set(locator) - ALLOWED_LOCATOR_KEYS
    if unknown:
        raise ValidationError(f"Unsupported locator fields: {sorted(unknown)}")
    strategy = locator.get("strategy")
    if strategy not in LOCATOR_STRATEGIES:
        raise ValidationError(f"Unsupported locator strategy: {strategy}")
    if strategy == "role":
        if not locator.get("role") or not locator.get("name"):
            raise ValidationError("role locators require role and name")
    elif not locator.get("value"):
        raise ValidationError(f"{strategy} locators require value")


def validate_workflow_spec(spec):
    if not isinstance(spec, dict) or not isinstance(spec.get("steps"), list) or not spec["steps"]:
        raise ValidationError("workflow spec requires a non-empty steps array")
    if set(spec) - {"name", "version", "steps"}:
        raise ValidationError("workflow spec contains unsupported top-level fields")
    seen = set()
    for index, step in enumerate(spec["steps"]):
        if not isinstance(step, dict):
            raise ValidationError(f"step {index} must be an object")
        unknown = set(step) - ALLOWED_STEP_KEYS
        if unknown:
            raise ValidationError(f"step {index} has unsupported fields: {sorted(unknown)}")
        step_id = step.get("id")
        if not step_id or step_id in seen:
            raise ValidationError("step ids must be present and unique")
        seen.add(step_id)
        action = step.get("action")
        if action not in ACTIONS:
            raise ValidationError(f"Unsupported action: {action}")
        if action in LOCATOR_ACTIONS:
            validate_locator(step.get("locator"))
        if action == "navigate" and not step.get("url"):
            raise ValidationError("navigate requires url")
        if action in {"fill", "select"} and "value" not in step:
            raise ValidationError(f"{action} requires value")
        timeout = step.get("timeout_ms", 10000)
        if not isinstance(timeout, int) or timeout < 100 or timeout > 60000:
            raise ValidationError("timeout_ms must be between 100 and 60000")
    return spec


def apply_locator_patch(spec, step_id, replacement_locator):
    validate_locator(replacement_locator)
    patched = deepcopy(spec)
    matches = [step for step in patched["steps"] if step["id"] == step_id]
    if len(matches) != 1 or "locator" not in matches[0]:
        raise ValidationError("patch must target exactly one existing locator")
    matches[0]["locator"] = deepcopy(replacement_locator)
    validate_workflow_spec(patched)
    return patched

