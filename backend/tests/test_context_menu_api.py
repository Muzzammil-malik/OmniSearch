"""Unit and integration tests for Windows Explorer context menu endpoint and registry synchronization."""

import platform
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.mark.skipif(platform.system().lower() != "windows", reason="Windows context menu only supported on Windows")
def test_context_menu_lifecycle(client):
    """Test enabling, inspecting, and disabling Windows Explorer context menu."""
    import winreg

    # 1. Enable context menu
    res_enable = client.post("/api/v1/system/context-menu", json={"enabled": True})
    assert res_enable.status_code == 200
    data_enable = res_enable.json()
    assert data_enable["success"] is True

    # 2. Verify status endpoint reports enabled
    res_status = client.get("/api/v1/system/context-menu")
    assert res_status.status_code == 200
    assert res_status.json()["enabled"] is True

    # 3. Verify exact registry keys and values in Windows Registry
    keys = [
        r"Software\Classes\Directory\shell\OmniSearch",
        r"Software\Classes\Directory\Background\shell\OmniSearch",
        r"Software\Classes\Folder\shell\OmniSearch",
    ]

    for k in keys:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, k, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, "")
            assert val == "Search with OmniSearch"

            icon, _ = winreg.QueryValueEx(key, "Icon")
            assert icon.lower().endswith(".exe"), f"Icon must be an executable, got {icon}"
            assert Path(icon).exists(), f"Icon target must exist on disk: {icon}"

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{k}\\command", 0, winreg.KEY_READ) as cmd_key:
            cmd, _ = winreg.QueryValueEx(cmd_key, "")
            assert "--open-folder" in cmd
            assert '"%V"' in cmd

    # 4. Disable context menu
    res_disable = client.post("/api/v1/system/context-menu", json={"enabled": False})
    assert res_disable.status_code == 200
    assert res_disable.json()["success"] is True

    # 5. Verify status endpoint reports disabled
    res_status2 = client.get("/api/v1/system/context-menu")
    assert res_status2.status_code == 200
    assert res_status2.json()["enabled"] is False

    # 6. Verify keys are removed from registry
    for k in keys:
        with pytest.raises(OSError):
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, k, 0, winreg.KEY_READ)

