from pathlib import Path

import pytest
from pydantic import ValidationError

from smarttrading.config import load_settings
from smarttrading.config.settings import AppSettings


def test_default_config_is_paper_and_has_no_live_mode() -> None:
    settings = load_settings(Path("config/default.yaml"))
    assert settings.mode.value == "paper"
    assert set(settings.assets) == {"BTC/USDT", "ETH/USDT"}

    payload = settings.model_dump()
    payload["mode"] = "live"
    with pytest.raises(ValidationError):
        AppSettings(**payload)


def test_environment_can_override_nested_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMARTTRADING__RISK__MAX_ORDER_NOTIONAL", "250")
    settings = load_settings()
    assert str(settings.risk.max_order_notional) == "250"
