import logging
import re


def redact_sensitive_params(value: str) -> str:
    return re.sub(r'(?i)([?&](?:code|access_token|token|jwt)=)[^&\s"\']+',r'\1[redacted]',value)


class SensitiveQueryFilter(logging.Filter):
    def filter(self,record):
        if isinstance(record.msg,str):
            record.msg=redact_sensitive_params(record.msg)
        if isinstance(record.args,tuple):
            record.args=tuple(redact_sensitive_params(v) if isinstance(v,str) else v for v in record.args)
        return True


def install_log_redaction():
    for name in ['uvicorn.access','uvicorn.error']:
        logger=logging.getLogger(name)
        if not any(isinstance(f,SensitiveQueryFilter) for f in logger.filters):
            logger.addFilter(SensitiveQueryFilter())
