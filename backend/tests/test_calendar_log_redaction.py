def test_auth_query_redaction_preserves_non_sensitive_path():
    from app.core.log_redaction import redact_sensitive_params
    raw='/api/auth/folio?code=opaque-secret&kind=event&access_token=full-jwt'
    safe=redact_sensitive_params(raw)
    assert 'opaque-secret' not in safe and 'full-jwt' not in safe
    assert 'kind=event' in safe
