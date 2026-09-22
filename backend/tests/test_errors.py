from app.core.errors import AppError, error_body


def test_error_body_shape():
    body = error_body("validation_error", "bad", {"field": "title"})
    assert body == {
        "error": {
            "code": "validation_error",
            "message": "bad",
            "details": {"field": "title"},
        }
    }


def test_app_error_fields():
    err = AppError("database_error", "down", status_code=503)
    assert err.code == "database_error"
    assert err.status_code == 503
