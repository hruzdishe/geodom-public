"""Exercise the running local API and MinIO. Creates a user and deletes its test listing."""
import asyncio
from io import BytesIO
from uuid import uuid4

import httpx
from PIL import Image
from sqlalchemy import select

from geodom_backend.db.models import ApartmentPhoto
from geodom_backend.db.session import session_factory, dispose_engine


async def main():
    async with httpx.AsyncClient(base_url='http://localhost:8000/api/v1', timeout=40) as client:
        async def call(method, path, expected=200, **kwargs):
            response = await client.request(method, path, **kwargs)
            assert response.status_code == expected, (method, path, response.status_code, response.text[:1500])
            print(f'{method} {path}: {response.status_code}')
            return response.json() if response.content else None

        await call('GET', '/health')
        cors=await client.options('/auth/login',headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
        assert cors.headers.get('access-control-allow-origin') == 'http://localhost:5173'
        assert cors.headers.get('access-control-allow-credentials') == 'true'
        districts=await call('GET','/districts')
        assert len(districts)==7
        page=await call('GET','/apartments?limit=100')
        assert page['total'] >= 300
        detail=await call('GET',f"/apartments/{page['items'][0]['id']}")
        assert detail['latitude'] and detail['longitude']
        await call('GET','/apartments?deal_type=rent')
        studios=await call('GET','/apartments?rooms=0')
        assert all(item['rooms']==0 for item in studios['items'])
        await call('GET','/apartments?deal_type=sale&rent_period=month',422)
        recommendation=await call('POST','/recommendations',json={'price_max':12000000,'priorities':{'schools':4,'parks':4,'transport':4,'ecology':3,'safety':3},'limit':10})
        assert not recommendation['fallback_used'] and recommendation['items']
        assert recommendation['items'][0]['score'] > 0
        print('Ranking:',recommendation['eligible_count'],recommendation['returned_count'],recommendation['items'][0]['score'])
        async with session_factory() as session:
            forbidden=set((await session.scalars(select(ApartmentPhoto.id).where(ApartmentPhoto.publication_allowed.is_(False)))).all())
        public_photos=[photo for item in page['items'] for photo in item['photos']]
        public_photos+=detail['photos']
        public_photos += [photo for item in recommendation['items'] for photo in item['apartment']['photos']]
        assert not any(photo['id'] in forbidden for photo in public_photos)
        print('Public photo rights checked; restricted seed photos:',len(forbidden))
        credentials={'login':f'smoke_{uuid4().hex[:12]}','password':uuid4().hex}
        registered=await call('POST','/auth/register',201,json=credentials)
        assert (await call('GET','/auth/me'))['id']==registered['user']['id']
        await call('POST','/auth/logout',204)
        await call('GET','/auth/me',401)
        login=await client.post('/auth/login',json=credentials)
        assert login.status_code==200 and 'httponly' in login.headers['set-cookie'].lower()
        async with httpx.AsyncClient(base_url=str(client.base_url),cookies=client.cookies) as reload:
            assert (await reload.get('/auth/me')).status_code==200
        await call('GET','/apartments/my')
        apartment=await call('POST','/apartments',201,json={'title':'Smoke test GeoDom','price':6500000,'deal_type':'sale','rooms':2,'area':54,'floor':3,'total_floors':9,'address':'Красноярск, улица Ленина, 25','description':'Temporary integration smoke test'})
        ident=apartment['id']
        try:
            await call('GET',f'/apartments/my/{ident}')
            await call('PATCH',f'/apartments/{ident}',json={'price':6600000,'address':apartment['address']})
            await call('POST',f'/apartments/{ident}/hide')
            await call('GET',f'/apartments/{ident}',404)
            await call('POST',f'/apartments/{ident}/publish')
            data=BytesIO(); Image.new('RGB',(40,40),'#58a6a0').save(data,format='PNG')
            photos=[]
            for i in range(2):
                photos.append(await call('POST',f'/apartments/{ident}/photos',201,files={'file':(f'smoke-{i}.png',data.getvalue(),'image/png')}))
            assert (await client.get(photos[0]['url'])).status_code==200
            await call('GET',f'/apartments/my/{ident}/photos')
            await call('POST',f"/apartments/{ident}/photos/{photos[1]['id']}/cover")
            await call('PUT',f'/apartments/{ident}/photos/order',json={'photo_ids':[photos[1]['id'],photos[0]['id']]})
            public=await call('GET',f'/apartments/{ident}')
            assert all(p['url'] for p in public['photos']) and len(public['photos'])==2
            async with httpx.AsyncClient(base_url=str(client.base_url)) as anonymous:
                assert (await anonymous.patch(f'/apartments/{ident}',json={'price':1})).status_code==401
            for photo in photos:
                await call('DELETE',f"/apartments/{ident}/photos/{photo['id']}",204)
        finally:
            await call('DELETE',f'/apartments/{ident}',204)
        assert not any(a['id']==ident for a in await call('GET','/apartments/my'))
        await call('POST','/auth/logout',204)
        await dispose_engine()
        print('PASS: auth, catalog, recommendations, listing lifecycle and MinIO')

if __name__=='__main__':
    asyncio.run(main())
