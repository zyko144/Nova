from urllib.parse import urlsplit

def snapshot(browser):
    if getattr(browser,'private',False):return {'tabs':[],'selected':0}
    tabs=[];selected=0
    for i in range(browser.tabs.count()):
        view=browser.tabs.widget(i);url=view.url().toString();p=urlsplit(url)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.hostname in ('127.0.0.1','localhost','nova.local'):continue
        if view is browser.current():selected=len(tabs)
        tabs.append({'url':url,'title':view.title()[:250],'pinned':bool(getattr(view,'_pinned',False)),'muted':bool(getattr(view,'_muted',False))})
    return {'tabs':tabs[:100],'selected':min(selected,max(0,len(tabs)-1))}
