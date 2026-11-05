"""Cleanup of uncommitted uploads and best-effort post-commit deletion.

Database transactions and filesystem operations are not jointly atomic.
Never remove an existing attachment before its corresponding commit.
"""
from contextlib import contextmanager
import logging

_LOG = logging.getLogger(__name__)


@contextmanager
def uploaded_transaction(db, metadata, directory, delete_file):
    try:
        yield
    except BaseException:
        db.rollback()
        if metadata and metadata.get('original_name') and metadata.get('stored_name'):
            try:
                delete_file(metadata['stored_name'], directory)
            except (OSError, TimeoutError):
                _LOG.exception('Uncommitted upload cleanup failed')
        raise


def delete_after_commit(stored_name, directory, delete_file):
    if not stored_name:
        return
    try:
        delete_file(stored_name, directory)
    except (OSError, TimeoutError):
        _LOG.exception('Committed attachment cleanup failed')
