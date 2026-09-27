from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=['Infrastructure'])
SNAPSHOT = Path(__file__).resolve().parents[3] / 'data/map/geo_objects.json'


@router.get('/geo-objects', summary='Объекты инфраструктуры Красноярска')
def geo_objects():
    if not SNAPSHOT.is_file():
        raise HTTPException(status_code=503, detail='Объекты на карте временно недоступны')
    return FileResponse(SNAPSHOT, media_type='application/json', headers={'Cache-Control':'public, max-age=3600'})
