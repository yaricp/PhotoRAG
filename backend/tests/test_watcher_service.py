import sys
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

for _module_name in ["src.watcher_service", "src.observer"]:
    if _module_name in sys.modules and not hasattr(sys.modules[_module_name], "__file__"):
        sys.modules.pop(_module_name, None)


from src.watcher_service import WatcherService


def make_watcher(id=1, path="/watch", destination_path="/dest", status="active"):
    return SimpleNamespace(
        id=id,
        path=path,
        destination_path=destination_path,
        status=status,
    )


def test_start_watcher_starts_observer_when_db_status_is_active_but_not_running():
    watcher = make_watcher(status="active")
    observer = MagicMock()
    service = WatcherService()

    with (
        patch("src.watcher_service.get_or_create_watcher", return_value=watcher),
        patch("src.watcher_service.update_watcher_status", return_value=watcher) as update_status,
        patch("src.watcher_service.start_observer", return_value=observer) as start_observer,
    ):
        result = service.start_watcher(MagicMock(), watcher.path, watcher.destination_path)

    start_observer.assert_called_once_with(watcher.path, watcher.destination_path)
    update_status.assert_called_once_with(ANY, watcher.id, "active")
    assert result == {"status": "watching", "target": watcher.path, "id": watcher.id}
    assert service.active == [
        {"id": watcher.id, "path": watcher.path, "observer": observer},
    ]


def test_start_watcher_reuses_observer_when_already_running_in_process():
    watcher = make_watcher(status="active")
    observer = MagicMock()
    service = WatcherService()
    service.active.append({"id": watcher.id, "path": watcher.path, "observer": observer})

    with (
        patch("src.watcher_service.get_or_create_watcher", return_value=watcher),
        patch("src.watcher_service.update_watcher_status") as update_status,
        patch("src.watcher_service.start_observer") as start_observer,
    ):
        result = service.start_watcher(MagicMock(), watcher.path, watcher.destination_path)

    start_observer.assert_not_called()
    update_status.assert_not_called()
    assert result is watcher
    assert service.active == [
        {"id": watcher.id, "path": watcher.path, "observer": observer},
    ]


def test_stop_watcher_deletes_stale_db_record_when_observer_is_not_running():
    watcher = make_watcher(status="active")
    service = WatcherService()

    with patch("src.watcher_service.delete_watcher", return_value=watcher) as delete_watcher:
        result = service.stop_watcher(watcher.id, MagicMock())

    delete_watcher.assert_called_once_with(ANY, watcher.id)
    assert result is watcher
    assert service.active == []
