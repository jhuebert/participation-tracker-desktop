from participation_tracker.monitors import get_display_target


def test_fake_secondary_hook(monkeypatch):
    monkeypatch.setenv("DUAL_DISPLAY_FAKE_SECONDARY", "-1920,0,1920,1080")
    monitor, extended = get_display_target(1000, 700)
    assert extended is True
    assert monitor.rect == (-1920, 0, 0, 1080)
    assert monitor.work == monitor.rect
