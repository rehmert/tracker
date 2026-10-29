import asyncio
import io
from unittest.mock import Mock, patch
from starlette.datastructures import UploadFile
from app.models import VendorPriceAttachment
from app.routers.vendor_prices import upload_attachment, download_attachment, delete_attachment


def test_archive_upload_does_not_parse_or_create_price_entries():
    db = Mock()
    upload = UploadFile(filename='prices.xlsx', file=io.BytesIO(b'original spreadsheet bytes'))
    with patch('app.routers.vendor_prices.services.flash_redirect', return_value='ok'):
        result = asyncio.run(upload_attachment(Mock(), 'Vendor A', 'Fall list', upload, db))
    assert result == 'ok'
    attachment = db.add.call_args.args[0]
    assert isinstance(attachment, VendorPriceAttachment)
    assert attachment.content == b'original spreadsheet bytes'
    assert attachment.filename == 'prices.xlsx'
    db.commit.assert_called_once()


def test_download_is_forced_attachment():
    db = Mock()
    db.get.return_value = VendorPriceAttachment(filename='list.csv', content=b'hello', content_type='text/csv')
    response = download_attachment(1, db)
    assert response.body == b'hello'
    assert response.headers['content-disposition'].startswith('attachment;')
    assert response.headers['x-content-type-options'] == 'nosniff'


def test_invalid_extension_not_saved():
    db = Mock()
    upload = UploadFile(filename='script.html', file=io.BytesIO(b'<script>x</script>'))
    with patch('app.routers.vendor_prices.page', return_value='error'):
        assert asyncio.run(upload_attachment(Mock(), 'Vendor', '', upload, db)) == 'error'
    db.add.assert_not_called()


def test_delete_attachment():
    db = Mock()
    attachment = object()
    db.get.return_value = attachment
    with patch('app.routers.vendor_prices.services.flash_redirect', return_value='ok'):
        assert delete_attachment(1, db) == 'ok'
    db.delete.assert_called_once_with(attachment)
