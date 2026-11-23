import argparse
from .index import Index
from .server import SearchServer
from .crawler import crawl

def main():
    parser=argparse.ArgumentParser(description='Nova Search : index et recherche indépendants')
    parser.add_argument('--db',default='data/nova-search.sqlite3')
    commands=parser.add_subparsers(dest='command',required=True)
    serve=commands.add_parser('serve');serve.add_argument('--host',default='127.0.0.1');serve.add_argument('--port',type=int,default=8787)
    serve.add_argument('--provider',choices=('local','brave'),default='brave')
    explore=commands.add_parser('crawl');explore.add_argument('urls',nargs='+');explore.add_argument('--limit',type=int,default=30)
    remove=commands.add_parser('remove');remove.add_argument('url')
    commands.add_parser('stats')
    args=parser.parse_args();index=Index(args.db)
    if args.command=='crawl':print('Pages indexées :',crawl(index,args.urls,args.limit))
    elif args.command=='remove':index.remove(args.url)
    elif args.command=='stats':print(index.stats())
    else:
        if args.provider=='brave':
            from .brave import BraveSearch
            index=BraveSearch(index)
        server=SearchServer((args.host,args.port),index,'/');print('Nova Search : http://'+args.host+':'+str(server.server_port),flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close()
if __name__=='__main__':main()
