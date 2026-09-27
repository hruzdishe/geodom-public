from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from geodom_backend.apartments.photo_presenter import ApartmentPhotoPresenter


def photo(identifier, allowed):
    return SimpleNamespace(id=identifier, position=identifier, is_cover=identifier==1,
        publication_allowed=allowed, bucket='test', storage_key=str(identifier), width=10,
        height=10,mime_type='image/png',size_bytes=100)


@pytest.mark.asyncio
async def test_public_presenter_never_signs_restricted_seed_media():
    storage=SimpleNamespace(get_presigned_url=AsyncMock(return_value='http://minio/allowed'))
    presenter=ApartmentPhotoPresenter(storage)
    response=await presenter.build([photo(1,False),photo(2,True)],public_only=True)
    assert [item.id for item in response]==[2]
    assert response[0].url=='http://minio/allowed'
    storage.get_presigned_url.assert_awaited_once_with(bucket='test',key='2')


@pytest.mark.asyncio
async def test_owner_can_manage_both_restricted_and_uploaded_photos():
    storage=SimpleNamespace(get_presigned_url=AsyncMock(return_value='http://minio/private'))
    result=await ApartmentPhotoPresenter(storage).build([photo(1,False),photo(2,True)],public_only=False)
    assert len(result)==2
