"""Explicit opt-in enforcement; default preserves legacy report-only behavior.

Do not enable for an instance until every browser form and upload workflow
has received and passed CSRF integration testing.
"""

def reject_write(method, report, setting):
    if setting != '1':
        return False
    if method.upper() not in ('POST','PUT','PATCH','DELETE'):
        return False
    return report != 'valid'
