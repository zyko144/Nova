import base64,re
from functools import lru_cache
from pathlib import Path
from html import escape
from urllib.parse import urlsplit,urlunsplit
from PySide6.QtGui import QImage
from PySide6.QtCore import QByteArray,QBuffer,QIODevice,Qt

def canonical_url(url):
    parts=urlsplit(url)
    return urlunsplit((parts.scheme.lower(),parts.netloc.lower(),'' if parts.path=='/' else parts.path,parts.query,parts.fragment))

@lru_cache(maxsize=4)
def data_image(name,width):
    image=QImage(str(Path(__file__).parent/'assets'/name))
    if image.isNull():return ''
    if name=='nova-controls.png':
        alpha=image.createAlphaMask().convertToFormat(QImage.Format.Format_Grayscale8)
        alpha.invertPixels()
        image.setAlphaChannel(alpha)
    image=image.scaledToWidth(width,Qt.TransformationMode.SmoothTransformation)
    array=QByteArray();buffer=QBuffer(array);buffer.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buffer,'PNG')
    return 'data:image/png;base64,'+base64.b64encode(bytes(array)).decode()

def build_home(template,shortcuts,data):
    brands=data_image('nova-shortcuts.png',384);controls=data_image('nova-controls.png',384)
    hidden={canonical_url(u) for u in data.get('hidden_shortcuts',[])}
    items=[{'title':n,'url':u,'index':i,'fallback':s} for i,(n,u,s) in enumerate(shortcuts[:-1]) if canonical_url(u) not in hidden]
    for entry in data.get('shortcuts',[]):
        items=[x for x in items if canonical_url(x['url'])!=canonical_url(entry['url'])]
        items.append({'title':entry['title'],'url':entry['url'],'index':None,'fallback':''})
    items=items[:8]+[{'title':'Ajouter','url':'https://nova.local/add','index':5,'fallback':shortcuts[-1][2]}]
    for item in items:
        if item['title']=='Google':item.update(title='Nova Search',url=data.get('nova_search_base','https://nova.local/') if data.get('preferences',{}).get('search_engine','Google')=='Nova Search' else 'https://www.google.com/',index=None)
    tiles=[]
    for item in items:
        if item['title']=='Nova Search':
            from design import LOGO
            inner=LOGO
        elif brands and item['index'] is not None:
            i=item['index'];inner=f'<span class="brandSprite" style="background-position:{-(i%3)*44}px {-(i//3)*44}px"></span>'
        else:inner=f'<span class="customInitial">{escape(item["title"][:1].upper())}</span>'
        tiles.append(f'<a href="{escape(item["url"],quote=True)}"><div class="tile">{inner}</div>{escape(item["title"])}</a>')
    start=template.index('<div class="links">');end=template.index('</div></main>',start)
    result=template[:start]+'<div class="links">'+''.join(tiles)+template[end:]
    result=result.replace("default-src 'none';", "default-src 'none'; img-src data:;")
    css=f'''.brandSprite{{display:block;width:44px;height:44px;background-image:url('{brands}');background-size:132px 88px;background-repeat:no-repeat}}.customInitial{{font-size:26px;color:#c7a0ff;font-weight:600}}.links{{justify-content:center;gap:32px;flex-wrap:wrap}}.tile{{width:90px;height:76px;border-radius:22px}}.tile svg{{width:34px;height:34px}}.links a{{font-size:14px}}'''
    if controls:
        css+=f'''.novaControl{{display:inline-block;width:30px;height:30px;background-image:url('{controls}');background-size:120px 120px;background-repeat:no-repeat}}.settings svg{{display:none}}.settings:after{{content:'';width:30px;height:30px;background-image:url('{controls}');background-size:120px 120px;background-position:0 -60px}}.shield{{background:none;clip-path:none;width:30px;height:30px}}.shield:after{{content:'';width:30px;height:30px;display:block;background-image:url('{controls}');background-size:120px 120px;background-position:-30px -60px}}'''
        result=result.replace('<span class="shield">✓</span>','<span class="shield"></span>')
    result=result.replace('<div class="privacy">','<a class="privacy" href="https://nova.local/vpn" style="text-decoration:none">').replace('</small></div><main>','</small></a><main>')
    prefs=data.get('preferences',{})
    if prefs.get('theme')=='black':css+='body{background:#020203}.backdrop{opacity:.2}.tile,form,.privacy{background:#09080ddf}'
    accent=prefs.get('accent','#9338ff')
    if re.fullmatch(r'#[0-9a-fA-F]{6}',accent):css+=f'form{{border-color:{accent}66}}.tile:hover{{border-color:{accent}}}'
    engine=prefs.get('search_engine','Nova Search')
    if engine=='Nova Search':result=result.replace('https://www.google.com/search',escape(data.get('nova_search_base','https://nova.local/')+'search',quote=True))
    if engine=='DuckDuckGo':result=result.replace('https://www.google.com/search','https://duckduckgo.com/')
    elif engine=='Bing':result=result.replace('https://www.google.com/search','https://www.bing.com/search')
    allowed={'Nova Search':data.get('nova_search_base','https://nova.local/'),'DuckDuckGo':'https://duckduckgo.com/','Bing':'https://www.bing.com/','Google':'https://www.google.com/'}[engine if engine in ('Nova Search','DuckDuckGo','Bing','Google') else 'Nova Search']
    origin=urlsplit(allowed);result=result.replace('form-action https://www.google.com;','form-action '+escape(origin.scheme+'://'+origin.netloc,quote=True)+';')
    options=''.join('<option value="'+escape(value,quote=True)+'">' for value in data.get('recent_searches',[])[:12])
    result=result.replace('<input name="q"','<input list="nova-queries" autocomplete="on" name="q"').replace('</form>','</form><datalist id="nova-queries">'+options+'</datalist>')
    css+=':root{color-scheme:dark}'
    result=re.sub(r'<a class="privacy".*?</a>','',result,flags=re.S)
    css+='.settings{left:auto;right:22px;bottom:22px;width:44px;height:44px;display:grid;place-items:center;padding:0;border-radius:13px}.settings:after{display:block;margin:0}.settings svg{display:none}'
    return result.replace('</style>',css+'</style>')
