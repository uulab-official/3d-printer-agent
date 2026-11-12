"""Compare explicit user-provided offers; this module never claims live prices."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _amount(value,field,positive=False):
    if isinstance(value,bool):
        raise ValueError(f'{field}: 숫자를 입력하세요.')
    try:
        result=Decimal(str(value))
    except (InvalidOperation,ValueError):
        raise ValueError(f'{field}: 올바른 숫자를 입력하세요.') from None
    if not result.is_finite() or result<0 or (positive and result<Decimal('0.001')) or result>Decimal('1000000000000'):
        raise ValueError(f'{field}: 유효한 양수 범위의 값을 입력하세요.')
    return result


def compare_offers(offers:list[dict]) -> dict:
    if not isinstance(offers,list) or not 1<=len(offers)<=50:
        raise ValueError('1~50개의 상품을 비교할 수 있습니다.')
    groups=defaultdict(list)
    for offer in offers:
        if not isinstance(offer,dict):
            raise ValueError('상품 정보 형식이 올바르지 않습니다.')
        name=str(offer.get('name','')).strip()[:120]
        currency=str(offer.get('currency','KRW')).upper().strip()
        if not name or currency not in ('KRW','USD','EUR','JPY','CNY'):
            raise ValueError('상품명과 지원되는 통화가 필요합니다.')
        price=_amount(offer.get('price'),'가격')
        grams=_amount(offer.get('grams'),'중량',positive=True)
        shipping=None if offer.get('shipping') is None else _amount(offer['shipping'],'배송비')
        total=None if shipping is None else price+shipping
        perkg=None if total is None else (total*1000/grams).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
        groups[currency].append({'name':name,'price':float(price),'grams':float(grams),
            'shipping':None if shipping is None else float(shipping),'currency':currency,
            'delivered_total':None if total is None else float(total),'price_per_kg':None if perkg is None else float(perkg),
            'product_price_per_kg':float((price*1000/grams).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)),
            'conditions':'사용자가 입력한 가격·중량·배송비 기준. 세금·쿠폰·회원조건·재고·호환성은 확인하지 않았습니다.'})
    for items in groups.values():
        items.sort(key=lambda item:(item['price_per_kg'] is None,item['price_per_kg'] if item['price_per_kg'] is not None else float('inf')))
    return {'groups':dict(groups),'source':'user_entered','live_prices':False,'calculated_at':datetime.now(timezone.utc).isoformat(),
        'notice':'같은 제품·구성·색상·배송 조건인지 확인하세요. 다른 통화는 별도로 비교합니다.'}
