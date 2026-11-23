LOGO = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 120"><defs><linearGradient id="n" x2=".8" y2="1"><stop stop-color="#bd57ff"/><stop offset=".5" stop-color="#8d17ff"/><stop offset="1" stop-color="#6500ed"/></linearGradient></defs><path fill="url(#n)" d="M4 108C21 77 44 13 72 9c32-5 36 60 49 58 14-3 47-54 75-60-24 39-48 100-79 101-31 1-31-60-44-61C59 46 36 91 4 108Z"/><path fill="#360083" d="M4 108 63 62c12-10 16 4 27 18-9-32-13-48-24-29Z"/><path fill="#420098" d="M97 24c16 36 19 48 30 35l69-52-71 30c-9 3-19-4-28-13Z"/></svg>'''

def render_home(data):
    from home_assets import build_home
    return build_home(HOME,SHORTCUTS,data)

ICONS = {
 'menu':'<path d="M4 6h16M4 12h16M4 18h16"/>',
 'back':'<path d="m14 5-7 7 7 7M7 12h14"/>',
 'forward':'<path d="m10 5 7 7-7 7M17 12H3"/>',
 'reload':'<path d="M20 8a8 8 0 1 0 .3 8M20 3v6h-6"/>',
 'home':'<path d="m3 11 9-8 9 8M6 9v12h5v-7h3v7h5V9"/>',
 'star':'<path d="m12 3 2.8 5.8 6.4.9-4.6 4.5 1.1 6.3L12 17.5l-5.7 3 1.1-6.3L2.8 9.7l6.4-.9Z"/>',
 'download':'<path d="M12 3v13m-5-5 5 5 5-5M5 21h14"/>',
 'extensions':'<path d="M9 4h6v4c5-3 7 4 2 4h-2v8h-5v-3c0-4-6-4-6 0v3H2v-8h4C3 7 9 5 9 9Z"/>',
 'profile':'<circle cx="12" cy="12" r="10"/><circle cx="12" cy="9" r="3"/><path d="M5 20c0-8 14-8 14 0"/>',
 'settings':'<path d="m10 2 4 0 1 3 3 1 3 3-2 3 1 4-3 2-3-1-2 4-4-1-1-3-4-1-1-4 3-2-1-4 3-2Z"/><circle cx="12" cy="11" r="3"/>',
 'plus':'<path d="M12 4v16M4 12h16"/>',
 'close':'<path d="m6 6 12 12M18 6 6 18"/>',
 'min':'<path d="M5 12h14"/>',
 'max':'<rect x="5" y="5" width="14" height="14" rx="2"/>',
 'search':'<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/>',
 'video':'<rect x="3" y="5" width="18" height="14" rx="4"/><path d="m10 9 5 3-5 3Z"/>',
}
def svg_icon(name,color='#c6b9ed'):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>'

BACKGROUND = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1672 830" preserveAspectRatio="none"><defs>
<linearGradient id="r" x1="0" y1="0" x2=".8" y2="1"><stop stop-color="#05030c"/><stop offset=".65" stop-color="#160a41"/><stop offset=".86" stop-color="#7925ff"/><stop offset="1" stop-color="#100924"/></linearGradient>
<linearGradient id="l" x1=".5" y1="0" x2=".5" y2="1"><stop stop-color="#090511"/><stop offset=".7" stop-color="#200c59"/><stop offset=".85" stop-color="#a63cff"/><stop offset="1" stop-color="#080410"/></linearGradient>
<linearGradient id="b" x2="0" y2="1"><stop stop-color="#6623df"/><stop offset=".25" stop-color="#1a0c40"/><stop offset="1" stop-color="#030208"/></linearGradient>
<filter id="glow"><feGaussianBlur stdDeviation="9"/></filter></defs>
<path fill="url(#l)" d="M0 130C250 210 345 300 457 379S734 598 950 559 1325 350 1672 160V499C1290 661 1050 657 813 585S280 281 0 270Z"/>
<path fill="url(#r)" d="M0 320C245 215 367 383 520 460S904 707 1197 523 1432 286 1672 213V385C1498 358 1423 442 1263 536 1025 710 681 543 448 455S160 407 0 572Z"/>
<path stroke="#8e37ff" stroke-width="13" fill="none" filter="url(#glow)" d="M0 365C253 234 373 432 590 494S1033 693 1284 518 1451 327 1672 302"/>
<path fill="url(#b)" d="M0 575C259 485 337 558 528 613S932 662 1175 682 1450 624 1672 497V830H0Z"/>
<path fill="#030208" d="M0 695C237 636 407 658 627 691S982 652 1143 688 1428 749 1672 650V830H0Z"/>
<g fill="none" stroke="#8b35ed" stroke-width="1.1"><path d="M0 270C281 270 365 346 501 429S952 732 1263 536 1491 266 1672 213"/><path d="M0 365C253 234 373 432 590 494S1033 693 1284 518 1451 327 1672 302"/><path d="M0 434C258 379 403 465 617 538S1057 671 1264 600 1491 531 1672 520"/><path d="M0 575C259 485 337 558 528 613S932 662 1175 682 1450 624 1672 497"/><path d="M0 695C237 636 407 658 627 691S982 652 1143 688 1428 749 1672 650"/><path opacity=".3" d="M0 788C464 608 810 823 1672 712"/></g></svg>'''

SHORTCUTS = [
('YouTube','https://www.youtube.com','<svg viewBox="0 0 48 48"><rect x="2" y="8" width="44" height="32" rx="10" fill="#ff001b"/><path d="m20 16 14 8-14 8" fill="white"/></svg>'),
('Google','https://www.google.com','<svg viewBox="0 0 48 48"><path d="M44 24H25" stroke="#4285f4" stroke-width="9"/><path d="M39 10A19 19 0 0 0 8 15" fill="none" stroke="#ea4335" stroke-width="9"/><path d="M8 15a19 19 0 0 0 0 18" fill="none" stroke="#fbbc05" stroke-width="9"/><path d="M8 33a19 19 0 0 0 30 5" fill="none" stroke="#34a853" stroke-width="9"/><path d="M38 38a19 19 0 0 0 6-14" fill="none" stroke="#4285f4" stroke-width="9"/></svg>'),
('Twitch','https://www.twitch.tv','<svg viewBox="0 0 48 48"><path d="M7 4h37v27L31 44H21l-8 4v-9H4V14Z" fill="#9146ff"/><path d="M13 9v25h9v7l7-7h7l5-6V9Z" fill="white"/><path d="M24 15v12m9-12v12" stroke="#9146ff" stroke-width="4"/></svg>'),
('Netflix','https://www.netflix.com','<svg viewBox="0 0 48 48"><path d="M12 3h9v42h-9m15-42h9v42h-9" fill="#a60014"/><path d="m12 3 15 42h9L21 3" fill="#ec0825"/></svg>'),
('Discord','https://discord.com','<svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="23" fill="#5865f2"/><path d="M14 14 9 33l9 4 2-4h8l2 4 9-4-5-19-6-2-1 3h-6l-1-3Z" fill="white"/><ellipse cx="19" cy="25" rx="3" ry="4" fill="#5865f2"/><ellipse cx="29" cy="25" rx="3" ry="4" fill="#5865f2"/></svg>'),
('Ajouter','https://nova.local/add',svg_icon('plus','#9876d6'))]

HOME = '''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; form-action https://www.google.com; base-uri 'none'"><title>Nouvel onglet</title><style>
*{box-sizing:border-box}body{margin:0;height:100vh;overflow:hidden;background:radial-gradient(ellipse at 50% 70%,#13062d 0,#030208 65%);color:#f3edff;font:16px 'Segoe UI',sans-serif}.backdrop{position:absolute;inset:0;pointer-events:none}.backdrop>svg{width:100%;height:100%}main{position:absolute;top:15.3%;left:50%;transform:translateX(-50%) scale(.93);transform-origin:top center;width:min(850px,85vw);text-align:center}.logo{width:190px;height:120px;margin:0 auto 13px;filter:drop-shadow(0 0 20px #7a14ff55)}h1{font-size:48px;font-weight:600;line-height:1.2;margin:12px 0 6px;background:linear-gradient(100deg,#b697f2,#fff 62%);background-clip:text;color:transparent}p{font-size:22px;color:#b8a4df;margin:6px 0 22px}form{display:flex;align-items:center;height:68px;padding:0 24px;border-radius:38px;background:linear-gradient(110deg,#100b20ee,#0b0815f5);border:1px solid #5a2585;box-shadow:0 0 50px #7015ff18}form>svg{width:26px;height:26px;margin-right:18px}input{min-width:0;flex:1;font:19px 'Segoe UI';color:#f1e9ff;background:transparent;outline:0;border:0}input::placeholder{color:#a38fc8}button{background:none;color:#d7c5ff;border:0;cursor:pointer}form button{width:30px;height:30px;padding:0}form button svg{width:100%;height:100%;transform:rotate(180deg)}.links{display:flex;justify-content:space-between;gap:20px;margin-top:50px}.links a{color:white;text-decoration:none;font-size:16px}.tile{width:108px;height:90px;display:grid;place-items:center;background:linear-gradient(140deg,#100a20,#17102bee);border:1px solid #402367;border-radius:25px;margin-bottom:8px;transition:border-color .15s,transform .15s}.tile:hover{border-color:#a045ff;transform:translateY(-3px)}.tile svg{width:48px;height:48px}.privacy{position:absolute;right:22px;top:26px;width:250px;border:1px solid #332047;border-radius:22px;background:#100c1bcc;padding:16px 18px;color:#e2d7f7;font-size:15px}.privacy .line{display:flex;align-items:center;gap:10px}.privacy small{display:block;color:#9d8eb5;font-size:13px;margin:12px 0 0 34px}.shield{width:25px;height:29px;background:#6722a5;clip-path:polygon(50% 0,95% 18%,87% 68%,50% 100%,13% 68%,5% 18%);display:grid;place-items:center;color:#fff}.settings{position:absolute;left:22px;bottom:24px;width:56px;height:56px;border:1px solid #502078;border-radius:19px;background:#100a1c;display:grid;place-items:center;box-shadow:0 0 25px #690f8b22}.settings svg{width:28px;height:28px}@media(max-height:580px){main{top:9%}.logo{height:85px;width:145px}h1{font-size:38px}.links{margin-top:30px}}@media(max-width:900px){.privacy{display:none}.tile{width:75px;height:75px}.links{gap:8px}}
</style><div class="backdrop">''' + BACKGROUND + '''</div><div class="privacy"><div class="line"><span class="shield">✓</span>Protection du moteur</div><small>VPN non configuré</small></div><main><div class="logo">''' + LOGO + '''</div><h1>Nova Browser</h1><p>Naviguez sans limites.</p><form action="https://www.google.com/search">''' + svg_icon('search') + '''<input name="q" placeholder="Rechercher sur le web..." aria-label="Recherche" required><button aria-label="Rechercher">''' + svg_icon('back') + '''</button></form><div class="links">''' + ''.join(f'<a href="{url}"><div class="tile">{icon}</div>{name}</a>' for name,url,icon in SHORTCUTS) + '''</div></main><a class="settings" href="https://nova.local/settings" aria-label="Paramètres">''' + svg_icon('settings') + '''</a></html>'''
