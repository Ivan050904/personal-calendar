from app.ai.prompts import enrich_action_from_message, heuristic_propose
from app.ai.types import StructuredAction


def test_heuristic_requires_date_when_only_clock_given():
    action = heuristic_propose("создай событие сходить в туалет с 16 до 17:00")
    assert action is not None
    assert action.entity_type == "event"
    assert "date" in (action.missing_fields or [])
    assert action.intent == "CLARIFY"
    assert action.payload.get("start") in (None, "")
    assert "туалет" in str(action.payload.get("title", "")).lower()


def test_heuristic_parses_time_range_with_explicit_day():
    action = heuristic_propose(
        "создай событие сходить в туалет сегодня с 16 до 17:00",
        timezone="Asia/Vladivostok",
    )
    assert action is not None
    assert action.intent == "CREATE"
    assert action.entity_type == "event"
    assert action.missing_fields == []
    assert action.payload.get("start") or action.payload.get("startAt")
    assert action.payload.get("end") or action.payload.get("endAt")
    assert action.payload.get("timezone") == "Asia/Vladivostok"
    assert "туалет" in str(action.payload.get("title", "")).lower()


def test_enrich_fills_task_title_and_due_from_message():
    raw = StructuredAction(
        intent="CLARIFY",
        entity_type="task",
        clarification="Пожалуйста, уточните дату задачи.",
        missing_fields=["date"],
        payload={},
    )
    enriched = enrich_action_from_message(
        raw,
        "Салам! Создай задачу сегодня! Помыть полы!",
        timezone="UTC",
    )
    assert enriched.entity_type == "task"
    assert enriched.intent == "CREATE"
    assert "помыть полы" in str(enriched.payload.get("title", "")).lower()
    assert enriched.payload.get("dueDate")
    assert enriched.missing_fields == []
    assert enriched.clarification is None


def test_enrich_fills_groq_clarify_gap_with_day():
    raw = StructuredAction(
        intent="CLARIFY",
        entity_type=None,
        clarification="уточните",
        missing_fields=["entityType"],
        payload={},
    )
    enriched = enrich_action_from_message(
        raw,
        "создай событие сходить в туалет завтра с 16:00 до 17:00",
        timezone="UTC",
    )
    assert enriched.entity_type == "event"
    assert enriched.intent == "CREATE"
    assert enriched.missing_fields == []
    assert enriched.payload.get("start")


def test_enrich_speech_tuesday_weekly_named_event():
    raw = StructuredAction(
        intent="CLARIFY",
        entity_type="event",
        clarification="Укажите дату",
        missing_fields=["date"],
        payload={"title": "события, короче, повторника в неделю Этот называется ОГ физика 9 класс"},
    )
    enriched = enrich_action_from_message(
        raw,
        "Салам создай события, короче, повторника с 15 до 16.00 в неделю. Этот. Событие называется ОГ физика. 9 класс.",
        timezone="UTC",
    )
    assert enriched.intent == "CREATE"
    assert enriched.missing_fields == []
    assert enriched.payload.get("title") == "ОГ физика. 9 класс"
    assert str(enriched.payload.get("start") or "").endswith("T15:00:00")
    assert str(enriched.payload.get("end") or "").endswith("T16:00:00")
    assert enriched.payload.get("recurrence") == {"frequency": "weekly", "interval": 1, "weekdays": [2]}


def test_enrich_speech_tuesday_instrumental_and_nazvanie():
    """«повторником» + «название X» without «в неделю»."""
    raw = StructuredAction(
        intent="CREATE",
        entity_type="event",
        payload={"title": "название Ого и Физика 9 класса"},
        missing_fields=[],
    )
    enriched = enrich_action_from_message(
        raw,
        "Салам, короче, создай события повторником с 15 до 16.00 название Ого и Физика 9 класса.",
        timezone="UTC",
    )
    assert enriched.intent == "CREATE"
    assert enriched.missing_fields == []
    assert enriched.payload.get("title") == "Ого и Физика 9 класса"
    assert str(enriched.payload.get("start") or "").endswith("T15:00:00")
    assert str(enriched.payload.get("end") or "").endswith("T16:00:00")
    assert enriched.payload.get("recurrence") == {"frequency": "weekly", "interval": 1, "weekdays": [2]}


def test_heuristic_today_na_clock_time():
    """Speech: «на сегодня на 20.00 …» — day + time, not ask for date again."""
    action = heuristic_propose(
        "Создай события на сегодня на 20.00 напомнить мане порадовать лысого.",
        timezone="Asia/Vladivostok",
    )
    assert action is not None
    assert action.intent == "CREATE"
    assert action.missing_fields == []
    assert str(action.payload.get("start") or "").endswith("T20:00:00")
    assert str(action.payload.get("end") or "").endswith("T21:00:00")
    title = str(action.payload.get("title") or "").lower()
    assert "20" not in title
    assert "сегодня" not in title
    assert "напомнить" in title or "лысого" in title


def test_enrich_model_startdate_gap_with_today_na_time():
    raw = StructuredAction(
        intent="CLARIFY",
        entity_type="event",
        clarification="Укажите дату",
        missing_fields=["startDate", "date"],
        payload={"title": "на на 20 00 напомнить мане порадовать лысого"},
    )
    enriched = enrich_action_from_message(
        raw,
        "Создай события на сегодня на 20.00 напомнить мане порадовать лысого.",
        timezone="UTC",
    )
    assert enriched.intent == "CREATE"
    assert enriched.missing_fields == []
    assert enriched.clarification is None
    assert str(enriched.payload.get("start") or "").endswith("T20:00:00")
    title = str(enriched.payload.get("title") or "").lower()
    assert "напомнить" in title
    assert "20" not in title


def test_enrich_all_day_phrase():
    raw = StructuredAction(intent="CREATE", entity_type="event", payload={"title": "отпуск"}, missing_fields=["start"])
    enriched = enrich_action_from_message(
        raw,
        "Создай событие отпуск сегодня на весь день",
        timezone="UTC",
    )
    assert enriched.intent == "CREATE"
    assert enriched.payload.get("allDay") is True
    assert str(enriched.payload.get("start") or "").endswith("T00:00:00")
    assert str(enriched.payload.get("end") or "").endswith("T23:59:00")
    assert enriched.missing_fields == []
    bare = heuristic_propose(
        "Создай событие сегодня 18:30 позвонить маме",
        timezone="UTC",
    )
    assert bare is not None
    assert bare.intent == "CREATE"
    assert str(bare.payload.get("start") or "").endswith("T18:30:00")

    with_k = heuristic_propose(
        "Создай событие завтра к 9 часам зарядка",
        timezone="UTC",
    )
    assert with_k is not None
    assert with_k.intent == "CREATE"
    assert str(with_k.payload.get("start") or "").endswith("T09:00:00")
