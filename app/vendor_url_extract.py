"""Conservative, review-first extraction of public product-page prices.

Every HTTP connection is made to the exact public IP verified by this
request's DNS lookup, preventing a second DNS lookup from rebinding the
connection to an internal service. HTTPS still verifies the original host's
certificate and uses that hostname for SNI.
"""
import http.client
import ipaddress
import json
import re
import socket
import ssl
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

MAX_HTML = 2_000_000
REDIRECTS = frozenset((301, 302, 303, 307, 308))
REQUEST_TIMEOUT = 8


class _Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ''
        self._title = False
        self.scripts = []
        self._script = False
        self._buf = ''
        self.meta = {}
        self.text = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'title':
            self._title = True
        if tag == 'script':
            self._script = attrs.get('type', '').lower() == 'application/ld+json'
            self._buf = ''
        if tag in ('style', 'noscript'):
            self._skip += 1
        if tag == 'meta':
            key = (attrs.get('property') or attrs.get('name') or '').lower()
            if key:
                self.meta[key] = attrs.get('content', '')

    def handle_endtag(self, tag):
        if tag == 'title':
            self._title = False
        if tag == 'script' and self._script:
            self.scripts.append(self._buf)
            self._script = False
        if tag in ('style', 'noscript') and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._title:
            self.title += data
        if self._script:
            self._buf += data
        if not self._skip and not self._script and data.strip():
            self.text.append(data.strip())


def _validated_destination(url):
    """Return (parsed URL, selected vetted public IP), no DNS at connect time."""
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError('Product URL must be a public HTTP or HTTPS URL.')
    if any(ord(ch) < 32 or ch.isspace() for ch in url):
        raise ValueError('Product URL contains unsafe whitespace.')
    try:
        parsed = urlsplit(url)
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    except ValueError:
        raise ValueError('Invalid product URL.') from None
    if (
        parsed.scheme not in ('http', 'https')
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 80, 443)
    ):
        raise ValueError('Enter a public HTTP or HTTPS product URL.')
    host = parsed.hostname.rstrip('.').lower()
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
        raise ValueError('Private/local destinations are not allowed.')
    try:
        addresses = socket.getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
    except (socket.gaierror, ValueError):
        raise ValueError('Cannot resolve product host.') from None
    if not addresses:
        raise ValueError('Cannot resolve product host.')
    try:
        ips = [ipaddress.ip_address(row[4][0]) for row in addresses]
    except (ValueError, IndexError, TypeError):
        raise ValueError('Invalid product host address.') from None
    if any(not ip.is_global for ip in ips):
        raise ValueError('Private, reserved, or local destinations are not allowed.')
    return parsed, str(ips[0])


def public_url(url):
    """Public URL validation retained for existing callers."""
    _validated_destination(url)
    return url


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, hostname, port, ip):
        super().__init__(hostname, port, timeout=REQUEST_TIMEOUT)
        self._approved_ip = ip

    def connect(self):
        # Never call socket.getaddrinfo on the hostname a second time.
        self.sock = socket.create_connection(
            (self._approved_ip, self.port), self.timeout,
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname, port, ip):
        super().__init__(
            hostname, port, timeout=REQUEST_TIMEOUT,
            context=ssl.create_default_context(),
        )
        self._approved_ip = ip

    def connect(self):
        raw = socket.create_connection(
            (self._approved_ip, self.port), self.timeout,
        )
        try:
            # Keep TLS certificate verification + SNI tied to the URL host.
            self.sock = self._context.wrap_socket(
                raw, server_hostname=self.host,
            )
        except BaseException:
            raw.close()
            raise


def _fetch_once(url, parsed, approved_ip):
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    connection = (
        _PinnedHTTPSConnection(parsed.hostname, port, approved_ip)
        if parsed.scheme == 'https' else
        _PinnedHTTPConnection(parsed.hostname, port, approved_ip)
    )
    # Origin-form path only; no absolute-form requests to proxies.
    target = urlunsplit(('', '', parsed.path or '/', parsed.query, ''))
    try:
        connection.request(
            'GET', target,
            headers={
                'Host': parsed.netloc,
                'User-Agent': 'TrackerProductPricePreview/1.1',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Encoding': 'identity',
                'Connection': 'close',
            },
        )
        response = connection.getresponse()
        if response.status in REDIRECTS:
            return response.status, response.getheader('Location'), None
        if not 200 <= response.status < 300:
            raise ValueError(f'Upstream product page returned HTTP {response.status}.')
        if 'text/html' not in (response.getheader('Content-Type') or '').lower():
            raise ValueError('URL does not return an HTML page.')
        if (response.getheader('Content-Encoding') or 'identity').lower() != 'identity':
            raise ValueError('Unexpected compressed product page.')
        raw = response.read(MAX_HTML + 1)
        if len(raw) > MAX_HTML:
            raise ValueError('Page is too large (2 MB limit).')
        charset = response.headers.get_content_charset() or 'utf-8'
        try:
            page = raw.decode(charset, errors='replace')
        except LookupError:
            page = raw.decode('utf-8', errors='replace')
        return response.status, None, page
    finally:
        connection.close()


def fetch_public_page(url):
    """Fetch a bounded public HTML page, revalidating each redirect destination."""
    for _ in range(4):
        parsed, approved_ip = _validated_destination(url)
        try:
            status, location, page = _fetch_once(url, parsed, approved_ip)
        except (http.client.HTTPException, OSError, ssl.SSLError):
            raise ValueError('Unable to retrieve the public product page.') from None
        if status in REDIRECTS:
            if not location:
                raise ValueError('Redirect has no destination.')
            url = urljoin(url, location)
            continue
        return url, page
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
