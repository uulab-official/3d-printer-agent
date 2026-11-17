"""Where to buy filament in Korea: a curated, dated directory shown in the purchase view.

Every entry records what was actually observed when it was checked (the store's own
site, its Naver directory line, or its current Naver Shopping listings). Prices and
stock are deliberately not stored: they change daily and must be read at the store.
This is not advertising or an endorsement, and no store pays to be listed.
Stores whose operation could not be confirmed are kept apart and labelled so;
stores with positive evidence of closure are excluded and recorded with the reason.
"""
from __future__ import annotations

import copy
from urllib.parse import urlsplit

CHECKED_ON = '2026-11-17'

# Display order of filter tags; every store tag must be one of these.
MATERIALS = ('PLA', 'PETG', 'ABS·ASA', 'TPU', '엔지니어링', '특수 효과', '대용량', '3D펜', '레진')
KINDS = {
    'official_brand_store': '브랜드 공식 스토어',
    'official_distributor': '공식 판매·수입',
    'own_brand': '자체 브랜드·국내 제조',
    'reseller': '여러 브랜드 판매',
}

STORES = [
    # --- Bambu Lab genuine filament ------------------------------------------------
    {'id': 'bambu-kr', 'name': 'Bambu Lab 한국 공식 스토어', 'kinds': ['official_brand_store'], 'bambu': True,
     'urls': [{'label': '공식 스토어', 'url': 'https://kr.store.bambulab.com/'}],
     'materials': ['PLA', 'PETG', 'ABS·ASA', 'TPU', '엔지니어링'],
     'sells': 'Bambu Lab 정품 필라멘트(PLA Basic·Matte 등, PETG, ABS·ASA, TPU, PC, 섬유강화), 리필과 AMS용 스풀',
     'note': 'Bambu Lab이 원화로 직접 판매하는 정품 스풀·리필입니다. 색상별 품절이 잦습니다.',
     'evidence': '공식 한국어·원화 스토어의 필라멘트 컬렉션과 상품 페이지(검색 색인)'},
    {'id': 'dyair', 'name': '덕유항공 (DYAIR)', 'kinds': ['official_distributor', 'own_brand'], 'bambu': True,
     'urls': [{'label': '자사몰', 'url': 'https://dyairkorea.com/'}],
     'materials': ['PLA', 'PETG', 'ABS·ASA'],
     'sells': 'Bambu Lab 정품, Creality·Flashforge·Anycubic 필라멘트, 자체 DY PLA++',
     'note': '상품 페이지에 뱀부랩 공식 판매사·서비스센터로 표기합니다.',
     'evidence': '자사몰 상품 페이지의 공식 판매사 표기와 판매 중인 상품'},
    {'id': 'cnexzone', 'name': '씨넥스몰 (씨넥스존)', 'kinds': ['official_distributor'], 'bambu': True,
     'urls': [{'label': '11번가 스토어', 'url': 'https://shop.11st.co.kr/stores/332437'}],
     'materials': ['PLA'],
     'sells': 'Bambu Lab 정품 PLA 필라멘트, 프린터',
     'note': '11번가 상품에 뱀부랩코리아 공식수입사로 표기합니다.',
     'evidence': '11번가 스토어의 판매 중인 Bambu 필라멘트'},
    {'id': 'printboard', 'name': '프린트보드 공식 쇼핑몰', 'kinds': ['official_distributor', 'own_brand'], 'bambu': True,
     'urls': [{'label': '자사몰', 'url': 'https://www.printboard.co.kr/'}],
     'materials': ['PLA', 'PETG', 'ABS·ASA', 'TPU', '엔지니어링'],
     'sells': 'Bambu Lab 필라멘트(PLA·PETG·ABS·ASA·TPU·PC·PA·섬유강화·서포트), 자체 Premium+ 라인',
     'note': 'Bambu 국내 유통업체로 알려져 있습니다. 일부 품목 품절.',
     'evidence': '자사몰의 Bambu 필라멘트 카테고리와 판매 중인 상품'},
    {'id': '3dmon', 'name': '쓰리디몬', 'kinds': ['official_distributor'], 'bambu': True,
     'urls': [{'label': '자사몰', 'url': 'https://www.3dmon.co.kr'}, {'label': '스마트스토어', 'url': 'https://smartstore.naver.com/_3dmon'}],
     'materials': ['PLA', 'PETG', '엔지니어링', '레진'],
     'sells': 'Bambu Lab 프린터·부품·필라멘트, Ultimaker 필라멘트, Formlabs 등',
     'note': '사이트에 2023년부터 Bambu Lab 국내 공식 유통사로 표기합니다. 출력 대행 서비스는 2026-05에 종료했습니다.',
     'evidence': '자사몰(2026년 게시물 확인)'},
    # --- Korean own brands -----------------------------------------------------------
    {'id': 'taegang3d', 'name': '태강쓰리디', 'kinds': ['own_brand'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/taekang3d'}, {'label': '회사 사이트', 'url': 'https://taegang3d.com/'}],
     'materials': ['PLA', 'PETG', 'ABS·ASA', '엔지니어링', '대용량'],
     'sells': '국산 PLA+(무광·고속 HS), PETG, ABS, ASA, PA6 나일론, PLA+ 5kg',
     'note': '창원 자체 공장에서 만드는 국내 제조사입니다. 고속 출력용 라인이 있습니다.',
     'evidence': 'Naver 쇼핑 현재 상품(오늘출발)과 스토어 디렉터리'},
    {'id': 'rainbow3d', 'name': '레인보우 3D (한일산업사)', 'kinds': ['own_brand'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/3d-rainbow'}],
     'materials': ['PLA', 'PETG', '엔지니어링', '특수 효과', '3D펜'],
     'sells': '고속 PLA(파스텔·마블·무광), PETG, 내열 PETG, PC, 3D펜용 PLA',
     'note': '국내산 필라멘트를 내세우는 공식 스토어입니다.',
     'evidence': 'Naver 쇼핑 현재 상품(공식 배지·오늘출발)과 스토어 디렉터리'},
    {'id': 'plabs', 'name': 'PLABS (이썬)', 'kinds': ['own_brand', 'reseller'], 'bambu': False,
     'urls': [{'label': '자사몰', 'url': 'https://www.plabs.co.kr/'}, {'label': '스마트스토어', 'url': 'https://smartstore.naver.com/plabs'}],
     'materials': ['PLA', 'PETG', 'ABS·ASA', 'TPU', '엔지니어링', '레진'],
     'sells': '자체 PLABS 필라멘트(PLA·ABS·PETG·PEBA·PC-HT), eSUN, ELEGOO·RESIONE 레진과 레진 프린터',
     'note': 'FDM과 레진을 함께 다룹니다. 입고 일정 달력을 제공합니다.',
     'evidence': '자사몰 정상 운영(2026-10 상품 이미지)'},
    {'id': 'kexcelled', 'name': '켁셀드 공식 (Kexcelled)', 'kinds': ['official_brand_store'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/kexcelled'}],
     'materials': ['PLA', 'PETG', 'ABS·ASA', 'TPU', '엔지니어링', '특수 효과'],
     'sells': '무광·팬톤 색상 PLA, 마블·우드·야광·메탈 PLA, PETG HS, ABS, PC, TPU 85A',
     'note': '색상 수가 많습니다(무광 56색 등).',
     'evidence': 'Naver 쇼핑 현재 상품(켁셀드 공식, 오늘출발)'},
    {'id': 'sting3d', 'name': '스팅3D', 'kinds': ['own_brand'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/sting3d'}],
     'materials': ['PLA', '특수 효과', 'TPU'],
     'sells': '고강도·고속 PLA+, SATURN PLA+, 실크·마블·무광 PLA, 플렉시블 FPLA',
     'note': '국내 취미 사용자 사이에서 많이 쓰이며 Bambu 호환을 내세웁니다.',
     'evidence': 'Naver 쇼핑 현재 상품(오늘출발)'},
    {'id': 'green3d', 'name': '건강한쓰리디', 'kinds': ['own_brand'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/green3dmarket'}],
     'materials': ['PLA'],
     'sells': '자체 PLA, 밀리터리 색상 PLA+(카키·올리브·샌드)',
     'note': '국내 생산 표기의 저가 PLA로 후기 수가 많습니다.',
     'evidence': 'Naver 쇼핑 현재 상품과 스토어 디렉터리'},
    {'id': 'coobeen', 'name': 'CooBeen (쿠빈)', 'kinds': ['own_brand'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/gigip'}],
     'materials': ['PLA', 'ABS·ASA', '엔지니어링', '특수 효과', '대용량'],
     'sells': 'PLA 1kg·3kg, 마블·야광·실크 PLA, ASA, PLA/PETG 카본파이버',
     'note': '저가 PLA로 후기 수가 많습니다.',
     'evidence': 'Naver 쇼핑 현재 상품과 스토어 디렉터리'},
    {'id': 'fourway', 'name': '포웨이', 'kinds': ['own_brand'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/fourway'}],
     'materials': ['PLA', 'PETG', '특수 효과', '대용량'],
     'sells': 'PLA(실크·우드·마블), PETG, PLA 5kg',
     'note': '저가 PETG·실크 색상이 많습니다.',
     'evidence': 'Naver 쇼핑 현재 상품(오늘출발)'},
    {'id': 'gadget', 'name': '가제트 공식 (위드피플즈)', 'kinds': ['official_brand_store'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/hellomoto'}],
     'materials': ['PLA', '특수 효과', '3D펜'],
     'sells': '가제트 PLA·PLA PRO(투명·형광·무광·실크·그라데이션), 3D펜용 PCL',
     'note': '가제트 브랜드 공식 판매처입니다. 필라멘트 외 생활용품도 판매합니다.',
     'evidence': 'Naver 쇼핑 현재 상품(공식 배지)'},
    {'id': 'petela', 'name': '페텔라 (PETELA-KOREA)', 'kinds': ['own_brand'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/petela'}],
     'materials': ['PLA', 'TPU', '특수 효과', '엔지니어링'],
     'sells': 'MAGARITA PET-CP(PLA·PETG·ABS 대체, 실크·반투명·고강도), 85A 유연 소재, 의료용 팬텀 필라멘트',
     'note': '무독성을 내세운 PET-CP 소재 국내 제조사입니다(판매자 주장).',
     'evidence': 'Naver 쇼핑 현재 상품, 2026-06 블로그 후기'},
    {'id': 'inova', 'name': '아이노바 iNOVA (JPM 3D)', 'kinds': ['own_brand'], 'bambu': False,
     'urls': [{'label': '자사몰', 'url': 'https://www.jpm3d.com/'}],
     'materials': ['PLA', 'PETG', 'ABS·ASA', 'TPU', '엔지니어링', '특수 효과', '대용량'],
     'sells': '국내 제조 PLA·ABS(1~5kg, 2.85mm 포함), PETG, TPU, 우드, PA6 CF, PVA 서포트',
     'note': '엔지니어링·특수 소재 구색이 넓습니다.',
     'evidence': 'Naver 쇼핑 현재 상품(JPM 3D, 오늘출발)'},
    {'id': 'withfil', 'name': '빙글 (위드필)', 'kinds': ['own_brand', 'reseller'], 'bambu': False,
     'urls': [{'label': '자사몰', 'url': 'https://bingle.kr/'}],
     'materials': ['PLA', '3D펜'],
     'sells': '자체 위드필 국산 고속 PLA, 3D펜용 PLA 30색, 신도리코·큐비콘 필라멘트',
     'note': '신도리코 공식 대리점이며 공방·교육도 운영합니다. 품절 품목이 많습니다.',
     'evidence': '자사몰 정상 운영(2026-11 후기)'},
    {'id': 'top3d', 'name': 'TOP3D', 'kinds': ['own_brand'], 'bambu': False,
     'urls': [{'label': '자사몰', 'url': 'https://top3d.co.kr/'}],
     'materials': ['PLA', 'TPU', '3D펜', '대용량'],
     'sells': '3D펜과 3D펜용 PCL, PLA(내열·메탈릭·5kg), 플렉서블',
     'note': '3D펜·교육용 소모품 중심입니다. 상품 갱신은 오래됐습니다.',
     'evidence': '자사몰 운영(2026-10 게시물)'},
    {'id': 'smbest', 'name': '에스엠베스트 (필라천국)', 'kinds': ['own_brand'], 'bambu': False,
     'urls': [{'label': '자사몰', 'url': 'https://www.filaworld.kr/'}],
     'materials': ['PLA', '특수 효과', '3D펜'],
     'sells': '무독성 표기 3D펜 PLA, 커피·한방 필라멘트',
     'note': '무독성은 판매자 주장입니다. 자사몰 게시판은 오래 갱신되지 않았고 Naver 쇼핑에서는 판매 중입니다.',
     'evidence': 'Naver 쇼핑 현재 상품(에스엠베스트)'},
    # --- Importers and multi-brand resellers ----------------------------------------
    {'id': '37-3', 'name': '삼십칠다시삼 (37-3)', 'kinds': ['official_distributor'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/37-3'}],
     'materials': ['PLA', 'PETG', '특수 효과', '엔지니어링'],
     'sells': 'Fillamentum(우드 Timberfill, NonOilen, Vinyl 303 등), Filament-PM(PLA·PLA+·PETG)',
     'note': '체코 브랜드 공식 수입사입니다. 가격대가 높은 프리미엄·특수 소재.',
     'evidence': 'Naver 쇼핑 현재 상품(공식수입 표기, 오늘출발)'},
    {'id': '3dpmall', 'name': '3dpmall', 'kinds': ['reseller'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/cisvision'}],
     'materials': ['PLA', 'TPU'],
     'sells': '큐비콘(Cubicon) PLA PLUS·TPU 필라멘트와 노즐',
     'note': '큐비콘 프린터 사용자에게 맞습니다. 자체몰 주소는 스마트스토어로 연결됩니다.',
     'evidence': 'Naver 쇼핑 현재 상품(오늘출발)과 스토어 디렉터리'},
    {'id': '3dprinterstore', 'name': '3D프린터 스토어 (이손소프트)', 'kinds': ['reseller'], 'bambu': True,
     'urls': [{'label': '자사몰', 'url': 'https://3dprinterstore.co.kr/'}],
     'materials': ['PLA', 'PETG', 'TPU', '엔지니어링'],
     'sells': 'Bambu Lab, Polymaker, SUNLU, Creality, 큐비콘, 신도리코, 태강 등 여러 브랜드',
     'note': '취급 브랜드가 많은 국내 판매처입니다(공식 총판 표기는 없음).',
     'evidence': '자사몰 브랜드별 필라멘트 카테고리와 판매 중인 상품'},
    {'id': 'sciencetek', 'name': '싸이언스테크', 'kinds': ['reseller'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/siencetek'}],
     'materials': ['PLA', '특수 효과', '3D펜'],
     'sells': 'SUNLU 3D펜용 PCL, 프라임3D 실크 PLA, 다빈치 카트리지 필라멘트',
     'note': '교육·3D펜 쪽에 가깝습니다.',
     'evidence': 'Naver 쇼핑 현재 상품과 스토어 디렉터리'},
    {'id': 'anycubic-kr', 'name': '애니큐빅코리아 (쓰리디메이커즈)', 'kinds': ['official_distributor'], 'bambu': False,
     'urls': [{'label': '자사몰', 'url': 'https://anycubickorea.co.kr/'}],
     'materials': ['PLA', 'PETG', '레진'],
     'sells': 'Anycubic PLA·PETG·고속 PLA, 레진',
     'note': '운영사가 애니큐빅 공식 파트너라고 밝힙니다. 필라멘트는 몇 종뿐입니다.',
     'evidence': '자사몰 필라멘트 카테고리의 판매 중인 상품'},
    {'id': 'lcorporation', 'name': 'L코퍼레이션 (엘코퍼레이션)', 'kinds': ['reseller'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/3developer'}, {'label': '자사몰', 'url': 'https://shop.lcorporation.co.kr/'}],
     'materials': ['PLA', '특수 효과'],
     'sells': 'colorFabb 필라멘트(2.85mm 세트 등), Creality·Formlabs 프린터',
     'note': 'colorFabb 국내 유통 이력이 있습니다. 필라멘트 품목은 적습니다.',
     'evidence': '스토어 디렉터리와 Naver 쇼핑 현재 상품'},
    {'id': 'mfmall', 'name': 'mf몰 (Markforged 공식대리점)', 'kinds': ['official_distributor'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/mf_mall'}],
     'materials': ['엔지니어링'],
     'sells': 'Markforged Onyx, 카본파이버 CFF',
     'note': 'Markforged 프린터 전용 소재입니다. Bambu 등 일반 FDM 프린터에는 맞지 않습니다.',
     'evidence': '스토어 디렉터리와 Naver 쇼핑 현재 상품'},
    {'id': 'coco3d', 'name': '코코쓰리디', 'kinds': ['official_distributor'], 'bambu': False,
     'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/coco3d'}],
     'materials': ['레진'],
     'sells': '프로즌·헤이기어스 레진, 레진 수조',
     'note': '레진 전문점입니다. 필라멘트 판매는 확인하지 못했습니다.',
     'evidence': '스토어 디렉터리(프로즌·헤이기어스 독점 총판)와 Naver 쇼핑 현재 상품'},
    {'id': 'saltronic', 'name': '솔트로닉 3D프린팅 MALL', 'kinds': ['reseller'], 'bambu': False,
     'urls': [{'label': '자사몰', 'url': 'https://sgamt.co.kr/'}],
     'materials': ['PLA'],
     'sells': 'Polymaker PolyTerra PLA',
     'note': '국내에서 Polymaker를 살 수 있는 곳 중 하나입니다. 재고 표시가 불분명합니다.',
     'evidence': '자사몰 상품 페이지(구매 버튼·사업자 정보)'},
]
for store in STORES:
    store['status'] = 'active'

# Listed by the person or known before, but no current listing or directory entry was found.
UNCONFIRMED = [
    {'id': 'plasil', 'name': '플라실', 'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/plasil'}],
     'reason': '현재 판매 상품이나 스토어 디렉터리를 찾지 못했습니다. 폐업 증거도 없습니다.'},
    {'id': 'filaman', 'name': 'FilaMAN', 'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/filaman'}],
     'reason': '현재 판매 상품이나 스토어 디렉터리를 찾지 못했습니다.'},
    {'id': 'puriway', 'name': '퓨리웨이', 'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/puriway'}],
     'reason': '필라멘트 판매 흔적은 2023년 링크뿐이고, 현재는 다른 품목만 보입니다.'},
    {'id': 'sebangfila', 'name': '세방필라', 'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/sebangfila'}],
     'reason': '스토어와 상품의 흔적을 찾지 못했습니다.'},
    {'id': 'urbancollector', 'name': '어반컬렉터', 'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/urbancollector'}],
     'reason': '다른 쇼핑몰의 상품 기록만 있고 현재 판매 목록을 찾지 못했습니다.'},
    {'id': 'copy3d', 'name': '카피3d (완하오)', 'urls': [{'label': '스마트스토어', 'url': 'https://smartstore.naver.com/copy3d'}],
     'reason': '스토어와 상품의 흔적을 찾지 못했습니다.'},
]
for store in UNCONFIRMED:
    store['status'] = 'unconfirmed'

# Positive evidence of closure; kept only to explain why they are not shown.
EXCLUDED = [
    {'name': '퓨어필라', 'url': 'http://purefila.co.kr/', 'reason': '웹사이트 도메인이 등록되어 있지 않습니다(2026-11-17 WHOIS·DNS 확인).'},
]


def _valid_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme in ('http', 'https') and bool(parts.netloc) and not parts.username and not parts.password


def store_guide() -> dict:
    """The directory as sent to the browser: validated and copied, never mutated in place."""
    for store in [*STORES, *UNCONFIRMED]:
        if not all(_valid_url(link['url']) for link in store['urls']):
            raise ValueError(f'잘못된 판매처 주소: {store["id"]}')
    for store in STORES:
        if set(store['materials']) - set(MATERIALS) or set(store['kinds']) - set(KINDS):
            raise ValueError(f'알 수 없는 판매처 분류: {store["id"]}')
    return {
        'schema_version': 1, 'checked_on': CHECKED_ON,
        'materials': list(MATERIALS), 'kinds': dict(KINDS),
        'stores': copy.deepcopy(STORES), 'unconfirmed': copy.deepcopy(UNCONFIRMED), 'excluded': copy.deepcopy(EXCLUDED),
        'scope': ('판매처 사이트·Naver 스토어 디렉터리·Naver 쇼핑의 현재 상품으로 운영 여부를 확인한 목록입니다. '
                  '가격·재고·배송 조건은 저장하지 않으니 판매처에서 확인하세요. 광고나 제휴가 아니며, '
                  '판매자 표기(공식·국산·무독성 등)는 판매자의 주장입니다.'),
    }
