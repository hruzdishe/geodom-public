"""Offline review page for the exported dataset; no external image requests."""

from html import escape


def render_preview(apartments: list[dict], media: list[dict]) -> str:
    cards = []
    for apartment in apartments:
        room_label = "Студия" if apartment["rooms"] == 0 else f"{apartment['rooms']}-комн."
        photos = sorted(
            (m for m in media if m["entity_id"] == apartment["id"]), key=lambda p: p["position"]
        )
        pictures = "".join(
            f'<a href="../../{escape(p["local_path"], quote=True)}" target="_blank">'
            f'<img loading="lazy" src="../../{escape(p["local_path"], quote=True)}" alt="Фото объявления"></a>'
            for p in photos
        )
        cards.append(
            f'<article data-district="{escape(apartment["district_name"], quote=True)}">'
            f'<div class="photos">{pictures}</div><div class="body">'
            f"<small>{escape(apartment['district_name'])} · {escape(apartment['id'])}</small>"
            f"<h2>{apartment['price']:,.0f} ₽</h2>"
            f"<p>{room_label} · {apartment['area']} м² · "
            f"{apartment['floor']}/{apartment['floors_total']} этаж</p>"
            f"<p>{escape(apartment['address'])}</p>"
            f'<a href="{escape(apartment["source_url"], quote=True)}" target="_blank" rel="noopener">Объявление на СИБДОМ</a>'
            "</div></article>"
        )
    options = '<option value="">Все районы</option>' + "".join(
        f"<option>{escape(name)}</option>"
        for name in sorted({a["district_name"] for a in apartments})
    )
    return (
        """<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Квартиры Красноярска — просмотр набора</title>
<style>body{font:16px system-ui;background:#f3f5f7;color:#142231;margin:0}header{padding:28px 5%;background:#173449;color:white}h1{margin:0 0 8px}header p{max-width:900px;color:#d0dde6}select{font:inherit;padding:10px;border-radius:8px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px;padding:24px 5%}article{background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px #0001}article[hidden]{display:none}.photos{height:230px;display:flex;overflow-x:auto;scroll-snap-type:x mandatory}.photos a{min-width:100%;scroll-snap-align:start}.photos img{width:100%;height:100%;object-fit:contain;background:#edf0f3}.body{padding:18px}h2{margin:10px 0;font-size:24px}small{color:#60717c}p{line-height:1.5}a{color:#176385}header label{display:flex;align-items:center;gap:18px}</style>
<header><h1>Квартиры Красноярска</h1><p>Локальная проверка собранных объявлений. Фотографии листаются горизонтально. В галереях могут быть интерьеры, фасады, планировки и рендеры. Районы указаны по источнику, актуальность продажи не подтверждена звонком.</p><label><select id="district">"""
        + options
        + """</select><span id="count"></span></label></header>
<main>"""
        + "".join(cards)
        + """</main><script>
const filter=document.getElementById('district'),cards=[...document.querySelectorAll('article')];
function apply(){let n=0;for(const card of cards){card.hidden=!!filter.value&&card.dataset.district!==filter.value;if(!card.hidden)n++;}document.getElementById('count').textContent=n+' квартир';}
filter.addEventListener('change',apply);apply();</script></html>"""
    )
