"""Export the collected OSM snapshot and optionally refresh public parking locations."""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq
import httpx
from krasnoyarsk_ml.osm import check_payload

LABELS = {'school':'Школа','kindergarten':'Детский сад','college':'Колледж','university':'Университет',
    'park':'Парк','forest':'Лес','playground':'Детская площадка','pharmacy':'Аптека','clinic':'Поликлиника',
    'hospital':'Больница','bus_stop':'Остановка автобуса','tram_stop':'Остановка трамвая','station':'Станция',
    'supermarket':'Супермаркет','mall':'Торговый центр','sports_centre':'Спортивный центр','fitness_centre':'Фитнес',
    'parking':'Парковка'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-parking',action='store_true')
    parser.add_argument('--parking-json',type=Path,help='Previously collected Overpass parking response')
    args=parser.parse_args()
    output=Path('data/map/geo_objects.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    parking_path=output.with_name('parking.json')
    if args.refresh_parking or args.parking_json:
        query='''[out:json][timeout:90];
rel["place"="city"]["wikidata"="Q919"]->.boundary;
.boundary out tags;
.boundary map_to_area ->.city;
nwr(area.city)["amenity"="parking"]["access"!~"^(private|no)$"];
out meta center;'''
        if args.parking_json:
            payload=json.loads(args.parking_json.read_text())
            if payload.get('remark'): raise ValueError('Incomplete Overpass response')
        else:
            response=httpx.post('https://overpass-api.de/api/interpreter',data={'data':query},timeout=110)
            response.raise_for_status()
            payload=response.json()
            check_payload(payload)
        rows=[]
        for item in payload['elements']:
            tags=item.get('tags',{})
            if tags.get('amenity') != 'parking' or tags.get('access') in {'private','no'}: continue
            point=item.get('center',item)
            if 'lat' not in point or 'lon' not in point: continue
            rows.append({'osm_id':item['id'],'osm_type':item['type'],'source_id':f"{item['type']}/{item['id']}",
                'category':'parking','subcategory':'parking','name':tags.get('name','Парковка'),
                'address':', '.join(filter(None,[tags.get('addr:street'),tags.get('addr:housenumber')])) or None,
                'lat':point['lat'],'lon':point['lon'],'source':'OpenStreetMap',
                'source_url':f"https://www.openstreetmap.org/{item['type']}/{item['id']}",
                'source_updated_at':item.get('timestamp'),'collected_at':datetime.now(UTC).isoformat()})
        parking_path.write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')))
    rows=[]
    for item in pq.read_table('packages/scoring/data/processed/geo_objects.parquet').to_pylist():
        row={key:item.get(key) for key in ['osm_id','osm_type','source_id','category','subcategory','name','address','lat','lon','source','source_url','source_updated_at','collected_at']}
        row['name']=row['name'] or LABELS.get(row['subcategory'],'Объект инфраструктуры')
        rows.append(row)
    if parking_path.exists(): rows.extend(json.loads(parking_path.read_text()))
    output.write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':'),default=lambda x:x.isoformat()))
    print(f'Exported {len(rows)} map objects to {output}; parking: {sum(x["category"]=="parking" for x in rows)}')

if __name__=='__main__': main()
