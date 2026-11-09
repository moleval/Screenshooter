"""Tests for consent-based startup integration auditing."""

import json

from screenshooter import integration_startup


def _powershell_result(payload, returncode=0, stderr=""):
    class Result:
        pass
    result = Result()
    result.returncode = returncode
    result.stdout = json.dumps(payload)
    result.stderr = stderr
    return result


def test_modern_menu_status_reports_installed(monkeypatch):
    monkeypatch.setattr(integration_startup.os, "name", "nt")
    monkeypatch.setattr(
        integration_startup.subprocess, "run",
        lambda *a, **k: _powershell_result({"status": "INSTALLED", "issues": [], "package_count": 1}),
    )
    report = integration_startup.get_modern_menu_status()
    assert report["status"] == "INSTALLED"
    assert report["package_count"] == 1


def test_modern_menu_status_reports_unavailable_on_command_error(monkeypatch):
    class Result:
        returncode = 1
        stdout = ""
        stderr = "access denied"

    monkeypatch.setattr(integration_startup.os, "name", "nt")
    monkeypatch.setattr(integration_startup.subprocess, "run", lambda *a, **k: Result())
    report = integration_startup.get_modern_menu_status()
    assert report["status"] == "UNAVAILABLE"
    assert "access denied" in report["issues"][0]


def test_modern_menu_status_reports_broken_registration(monkeypatch):
    monkeypatch.setattr(integration_startup.os, "name", "nt")
    monkeypatch.setattr(
        integration_startup.subprocess, "run",
        lambda *a, **k: _powershell_result({
            "status": "BROKEN",
            "issues": ["Не найдена DLL."],
            "package_count": 1,
        }),
    )
    report = integration_startup.get_modern_menu_status()
    assert report["status"] == "BROKEN"
    assert "Не найдена DLL." in report["issues"]


def test_modern_menu_status_rejects_invalid_json(monkeypatch):
    class Result:
        returncode = 0
        stdout = "not-json"
        stderr = ""

    monkeypatch.setattr(integration_startup.os, "name", "nt")
    monkeypatch.setattr(integration_startup.subprocess, "run", lambda *a, **k: Result())
    assert integration_startup.get_modern_menu_status()["status"] == "UNAVAILABLE"


def test_startup_audit_skips_integrations_not_enabled(monkeypatch):
    class Settings:
        classic_menu_enabled = False
        modern_menu_enabled = False

    audit = integration_startup.IntegrationStartupAudit(Settings())
    monkeypatch.setattr(audit, "_audit_classic", lambda: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(audit, "_audit_modern", lambda: (_ for _ in ()).throw(AssertionError()))
    audit.run()


def test_startup_audit_does_not_repair_when_user_declines(monkeypatch):
    class Settings:
        classic_menu_enabled = True
        modern_menu_enabled = False

    monkeypatch.setattr(
        integration_startup, "get_classic_menu_status",
        lambda: {"status": "BROKEN", "issues": ["test issue"]},
    )
    monkeypatch.setattr(
        integration_startup.QMessageBox, "question",
        lambda *args, **kwargs: integration_startup.QMessageBox.No,
    )
    monkeypatch.setattr(
        integration_startup, "set_context_menu_enabled",
        lambda enabled: (_ for _ in ()).throw(AssertionError("must not write")),
    )
    integration_startup.IntegrationStartupAudit(Settings()).run()
