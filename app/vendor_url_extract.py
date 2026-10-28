"""Conservative, review-first extraction of public product-page prices."""
import ipaddress
import json
import re
import socket
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

MAX_HTML = 2_000_000

class _Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.title=''; self._title=False; self.scripts=[]; self._script=False; self._buf=''; self.meta={}; self.text=[]; self._skip=0
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='title': self._title=True
        if tag=='script': self._script=attrs.get('type','').lower()=='application/ld+json'; self._buf=''
        if tag in ('style','noscript'): self._skip+=1
        if tag=='meta':
            key=(attrs.get('property') or attrs.get('name') or '').lower()
            if key: self.meta[key]=attrs.get('content','')
    def handle_endtag(self,tag):
        if tag=='title': self._title=False
        if tag=='script' and self._script: self.scripts.append(self._buf); self._script=False
        if tag in ('style','noscript') and self._skip: self._skip-=1
    def handle_data(self,data):
        if self._title: self.title+=data
        if self._script: self._buf+=data
        if not self._skip and not self._script and data.strip(): self.text.append(data.strip())

def public_url(url):
    parsed=urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Enter a public HTTP or HTTPS product URL.')
    if parsed.port not in (None,80,443): raise ValueError('Only standard web ports are allowed.')
    if len(url)>2048: raise ValueError('URL too long.')
    host=parsed.hostname.rstrip('.').lower()
    if host=='localhost' or host.endswith(('.localhost','.local','.internal')):
        raise ValueError('Private/local destinations are not allowed.')
    try: addresses=socket.getaddrinfo(host,parsed.port or (443 if parsed.scheme=='https' else 80),type=socket.SOCK_STREAM)
    except socket.gaierror: raise ValueError('Cannot resolve product host.')
    if not addresses or any(not ipaddress.ip_address(addr[4][0]).is_global for addr in addresses):
        raise ValueError('Private, reserved, or local destinations are not allowed.')
    return url

def fetch_public_page(url):
    import httpx
    for _ in range(4):
        public_url(url)
        # Never trust proxy settings inherited from the host, and inspect each redirect.
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=8.0, headers={'User-Agent':'TrackerProductPricePreview/1.0','Accept':'text/html,application/xhtml+xml'}) as client:
            with client.stream('GET',url) as response:
                if response.status_code in (301,302,303,307,308):
                    location=response.headers.get('location')
                    if not location: raise ValueError('Redirect has no destination.')
                    url=urljoin(url,location); continue
                response.raise_for_status()
                if 'text/html' not in response.headers.get('content-type','').lower(): raise ValueError('URL does not return an HTML page.')
                buf=bytearray()
                for chunk in response.iter_bytes():
                    buf.extend(chunk)
                    if len(buf)>MAX_HTML: raise ValueError('Page is too large (2 MB limit).')
                return url,bytes(buf).decode(response.encoding or 'utf-8',errors='replace')
    raise ValueError('Too many redirects.')

def _products(node):
    if isinstance(node,list):
        for x in node: yield from _products(x)
    elif isinstance(node,dict):
        kind=node.get('@type',[])
        if isinstance(kind,str): kind=[kind]
        if any(str(k).lower().endswith('product') for k in kind): yield node
        for key in ('@graph','mainEntity','itemListElement','hasVariant'):
            if key in node: yield from _products(node[key])

def _price(value):
    if isinstance(value,(int,float,Decimal)): value=str(value)
    if not isinstance(value,str): return None
    match=re.search(r'(?<!\d)(\d{1,8}(?:,\d{3})*(?:\.\d{1,2})?)(?!\d)',value.replace('$',''))
    if not match: return None
    price=Decimal(match.group(1).replace(',',''))
    return str(price) if price>=0 else None

def extract_product(html, url):
    page=_Page(); page.feed(html)
    variants=[]
    for script in page.scripts:
        try: payload=json.loads(script)
        except (ValueError,TypeError): continue
        for product in _products(payload):
            name=str(product.get('name') or '')[:200]
            offers=product.get('offers',[])
            if isinstance(offers,dict): offers=[offers]
            if not offers: offers=[{}]
            for offer in offers[:40]:
                if not isinstance(offer,dict): continue
                price=_price(offer.get('price') or offer.get('lowPrice') or offer.get('highPrice'))
                if not price and isinstance(offer.get('priceSpecification'),dict): price=_price(offer['priceSpecification'].get('price'))
                currency=str(offer.get('priceCurrency') or '')
                variants.append({'name':name,'price':price or '', 'currency':currency, 'description':str(product.get('description') or '')[:500]})
    name=(variants[0]['name'] if variants else '') or page.meta.get('og:title') or page.title.strip()
    price=(variants[0]['price'] if variants else '') or _price(page.meta.get('product:price:amount','')) or _price(page.meta.get('og:price:amount',''))
    currency=(variants[0]['currency'] if variants else '') or page.meta.get('product:price:currency') or page.meta.get('og:price:currency') or ''
    if not price:
        # Don't guess from arbitrary page text (which can contain discounts, crossed-out prices, etc.).
        price=''
    description=(variants[0]['description'] if variants else '') or page.meta.get('description','')
    snippet=' '.join((name,description))
    strength=re.search(r'(?<!\w)(\d+(?:\.\d+)?)\s*(mg|iu)\s*(?:/\s*vial|per\s*vial)?\b',snippet,re.I)
    count=re.search(r'(?<!\w)(\d+)\s*(?:vials?|vls?)\b',snippet,re.I)
    kit=re.search(r'\b(half[ -]?kit|kit)\b',snippet,re.I)
    qty=int(count.group(1)) if count else (5 if kit and 'half' in kit.group(1).lower() else 10 if kit else None)
    return {'url':url,'name':name[:200],'price':price,'currency':currency,'content_amount':strength.group(1) if strength else '', 'content_unit':strength.group(2).upper() if strength and strength.group(2).lower()=='iu' else 'mg', 'package_type':{1:'vial',5:'half-kit',10:'kit'}.get(qty,''),'vial_count':qty,'variants':variants[:30]}
