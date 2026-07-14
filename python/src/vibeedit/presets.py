from __future__ import annotations

from copy import deepcopy

from vibeedit.spec import JSONObject


def list_media_presets(kind: str | None = None) -> list[JSONObject]:
    """List deterministic frame presets using stable VibeEdit identifiers.

    ``kind`` accepts ``filter``, ``effect``, or ``transition`` (and their
    plural forms). NumPy is loaded only when a preset is executed.
    """

    from vibeedit_media.preset_catalog import list_presets

    normalized = _kind(kind)
    return [_public_preset(preset) for preset in list_presets(normalized)]


def get_media_preset(identifier: str) -> JSONObject:
    from vibeedit_media.preset_catalog import get_preset

    return _public_preset(get_preset(_identifier(identifier)))


def build_media_preset_plan(identifier: str, *, parameter_overrides: dict[str, float | int] | None = None) -> JSONObject:
    from vibeedit_media.preset_catalog import build_agent_plan

    plan = deepcopy(build_agent_plan(_identifier(identifier), parameter_overrides=parameter_overrides))
    plan["presetId"] = identifier
    plan["deterministicFlow"] = _public_flow(plan["kind"], plan["deterministicFlow"])
    plan["agentFlow"] = _public_agent_flow(plan["kind"], identifier, plan["agentFlow"])
    return plan


def apply_media_preset(
    image,
    identifier: str,
    *,
    parameter_overrides: dict[str, float | int] | None = None,
    progress: float = 0.5,
):
    """Apply a catalog effect/filter to an RGBA-compatible image value."""

    from vibeedit_media.preset_catalog import apply_preset_to_image

    return apply_preset_to_image(
        image,
        _identifier(identifier),
        parameter_overrides=parameter_overrides,
        progress=progress,
    )


def render_transition_preset(
    from_image,
    to_image,
    identifier: str,
    *,
    parameter_overrides: dict[str, float | int] | None = None,
    progress: float,
):
    """Render one deterministic transition frame between two images."""

    from vibeedit_media.preset_catalog import render_transition_frame

    return render_transition_frame(
        from_image,
        to_image,
        _identifier(identifier),
        parameter_overrides=parameter_overrides,
        progress=progress,
    )


def _kind(kind: str | None) -> str | None:
    if kind is None:
        return None
    normalized = {"filter": "filters", "filters": "filters", "effect": "effects", "effects": "effects", "transition": "transitions", "transitions": "transitions"}.get(kind)
    if normalized:
        return normalized
    raise ValueError("kind must be one of: filter, effect, transition")


def _identifier(identifier: str) -> str:
    for prefix in ("vibeedit://effect/", "vibeedit://transition/"):
        if identifier.startswith(prefix) and identifier.removeprefix(prefix):
            return identifier.removeprefix(prefix)
    raise ValueError("preset identifier must use vibeedit://effect/ or vibeedit://transition/")


def _public_preset(source: JSONObject) -> JSONObject:
    preset = deepcopy(source)
    preset["sourceId"] = source["id"]
    preset["id"] = _public_id(source)
    preset["deterministicFlow"] = _public_flow(source["kind"], source["deterministicFlow"])
    preset["agentFlow"] = _public_agent_flow(source["kind"], preset["id"], source["agentFlow"])
    return preset


def _public_id(preset: JSONObject) -> str:
    category = "transition" if preset["kind"] == "transitions" else "effect"
    return f"vibeedit://{category}/{preset['id']}"


def _public_flow(kind: object, source: object) -> JSONObject:
    flow = deepcopy(source)
    if not isinstance(flow, dict):
        raise ValueError("canonical preset deterministicFlow must be an object")
    flow["entrypoint"] = (
        "vibeedit.presets.render_transition_preset"
        if kind == "transitions"
        else "vibeedit.presets.apply_media_preset"
    )
    return flow


def _public_agent_flow(kind: object, identifier: str, source: object) -> JSONObject:
    flow = deepcopy(source)
    if not isinstance(flow, dict):
        raise ValueError("canonical preset agentFlow must be an object")
    flow["applyExample"] = (
        f"render_transition_preset(previous_frame, next_frame, {identifier!r}, progress=t)"
        if kind == "transitions"
        else f"apply_media_preset(frame, {identifier!r}, progress=t)"
    )
    return flow
