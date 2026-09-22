from app.application.smart_day import build_smart_day_snapshot, plan_progress


def test_smart_day_free_and_next():
    snapshot = build_smart_day_snapshot(
        [
            {
                "id": "e1",
                "title": "Meeting",
                "startAt": "2026-09-18T10:00:00",
                "endAt": "2026-09-18T11:00:00",
                "color": "#0f766e",
                "allDay": False,
            }
        ],
        [],
        "2026-09-18T09:00:00",
    )
    assert snapshot.status == "free"
    assert snapshot.label == "Сейчас свободно"
    assert snapshot.next is not None
    assert snapshot.next.title == "Meeting"


def test_smart_day_busy_elapsed():
    snapshot = build_smart_day_snapshot(
        [
            {
                "id": "e1",
                "title": "Meeting",
                "startAt": "2026-09-18T10:00:00",
                "endAt": "2026-09-18T11:00:00",
                "color": "#0f766e",
                "allDay": False,
            }
        ],
        [],
        "2026-09-18T10:20:00",
    )
    assert snapshot.status == "busy"
    assert snapshot.elapsed_ms == 20 * 60_000
    assert snapshot.remaining_ms == 40 * 60_000


def test_plan_progress_percentage():
    assert plan_progress(
        [
            {"id": "1", "completed": True},
            {"id": "2", "completed": False},
            {"id": "3", "completed": True, "deletedAt": "x"},
        ]
    ) == {"completed": 1, "total": 2, "percentage": 50}
