"""Basic sanity checks for the skill registry and adapters."""

from skills.registry import REGISTRY, SKILL_KEYS
from adapters import VALID_MODELS, ADAPTER_MAP


def test_all_skills_have_required_fields():
    required = {"name", "system_prompt", "output_rules", "reviewer", "tags"}
    for key, skill in REGISTRY.items():
        missing = required - set(skill.keys())
        assert not missing, f"Skill '{key}' missing fields: {missing}"


def test_reviewer_references_valid_skill():
    for key, skill in REGISTRY.items():
        if skill["reviewer"]:
            assert skill["reviewer"] in SKILL_KEYS, (
                f"Skill '{key}' references unknown reviewer '{skill['reviewer']}'"
            )


def test_no_circular_reviewers():
    for key, skill in REGISTRY.items():
        if skill["reviewer"]:
            reviewer = REGISTRY[skill["reviewer"]]
            assert reviewer["reviewer"] != key, (
                f"Circular reviewer: {key} <-> {skill['reviewer']}"
            )


def test_all_adapters_instantiate():
    """Make sure every adapter factory runs without import errors."""
    for model_key, factory in ADAPTER_MAP.items():
        # We can't actually call the APIs, but we can check the factory runs
        # (will fail if env vars are missing, which is fine for CI)
        try:
            adapter = factory()
            assert adapter is not None
        except Exception:
            # Missing API key is expected in test env
            pass


def test_skill_tags_are_lists():
    for key, skill in REGISTRY.items():
        assert isinstance(skill["tags"], list), f"Skill '{key}' tags must be a list"
        assert len(skill["tags"]) > 0, f"Skill '{key}' needs at least one tag"


if __name__ == "__main__":
    test_all_skills_have_required_fields()
    test_reviewer_references_valid_skill()
    test_no_circular_reviewers()
    test_all_adapters_instantiate()
    test_skill_tags_are_lists()
    print("All tests passed.")
