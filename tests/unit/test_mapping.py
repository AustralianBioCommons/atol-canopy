from app.utils import mapping


class DummyCol:
    def __init__(self, name: str):
        self.name = name


class DummyTable:
    def __init__(self, cols):
        self.columns = [DummyCol(c) for c in cols]


class DummyModel:
    __table__ = DummyTable(
        [
            "name",
            "age",
            "height_cm",
            "active",
            "created_at",
            "updated_at",
            "bpa_json",
        ]
    )


def test_to_float_coerces_and_handles_invalid():
    assert mapping.to_float("1.5") == 1.5
    assert mapping.to_float(3) == 3.0
    assert mapping.to_float("") is None
    assert mapping.to_float("not-a-number") is None


def test_to_bool_coerces_reasonable_values():
    assert mapping.to_bool(True) is True
    assert mapping.to_bool("yes") is True
    assert mapping.to_bool("1") is True
    assert mapping.to_bool("no") is False
    assert mapping.to_bool("") is None
    assert mapping.to_bool(None) is None


def test_map_to_model_columns_applies_aliases_transforms_defaults_and_filters():
    result = mapping.map_to_model_columns(
        DummyModel,
        {
            "full_name": "Jane",
            "age": "25",
            "height_cm": "",
            "active": "true",
            "extra": "ignored",
        },
        aliases={"full_name": "name"},
        transforms={"age": int, "active": mapping.to_bool},
        defaults={"height_cm": 170},
        inject={"active": False},
    )

    # Aliased and transformed values present
    assert result["name"] == "Jane"
    assert result["age"] == 25
    # Empty string picked up by defaults
    assert result["height_cm"] == 170
    # Inject overrides transform result
    assert result["active"] is False
    # Non-model column filtered out
    assert "extra" not in result
    # Excluded columns are dropped
    assert "created_at" not in result and "updated_at" not in result
