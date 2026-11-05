import pytest
from app.core.errors import AppError


@pytest.mark.parametrize("target", ["https://evil.test", "//evil.test", "javascript:alert(1)", "/\\evil.test"])
def test_external_launch_target_rejected(target):
    from app.core.bridge_auth import safe_launch_target
    with pytest.raises(AppError):
        safe_launch_target(target)
