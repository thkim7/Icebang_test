import urllib

import requests
import json
from bs4 import BeautifulSoup


def search_products(search_term, filters=None, sort_by="default", page=1, price_min="", price_max=""):
    """
    싸다구 (ssadagu.kr) 사이트에서 상품을 검색하는 함수

    Args:
        search_term (str): 검색할 상품 키워드.
        filters (list, optional): 적용할 필터 리스트. Defaults to ['activeType'].
                                  (예: ['activeType', 'totalEpScoreLv1'])
        sort_by (str, optional): 정렬 방식. Defaults to "default".
                                 (옵션: price_asc, price_desc, monthSold_desc 등)
        page (int, optional): 조회할 페이지 번호. Defaults to 1.
        price_min (str, optional): 최소 가격. Defaults to "".
        price_max (str, optional): 최대 가격. Defaults to "".

    Returns:
        dict: 서버로부터 받은 응답 데이터 (JSON) 또는 에러 발생 시 None.
    """
    # 기본 필터 설정 (필터값이 주어지지 않은 경우)
    if filters is None:
        filters = ['activeType']  # '중국내 무료 배송' 기본값

    # 데이터를 요청할 서버 API 주소
    search_url = "https://ssadagu.kr/shop/ajax.infinity_shop_list.php"

    # 서버로 전송할 데이터 (Payload)
    payload = {
        'page_div_id': 'infinity_item_list',
        'page_type': 'pc',
        'ss_tx': search_term,
        'search_option_array': filters,
        'hi_platform': '1688',
        'price_min': price_min,
        'price_max': price_max,
        'sort_item': sort_by,
        'page': page
    }

    # 웹사이트가 AJAX 요청임을 인지하도록 헤더 설정
    encoded_q = urllib.parse.quote(search_term, safe="")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': f'https://ssadagu.kr/shop/search.php?ss_tx={encoded_q}'  # 요청 출처를 명시
    }

    try:
        # requests 라이브러리를 사용하여 POST 요청 전송
        response = requests.post(search_url, data=payload, headers=headers)

        # HTTP 상태 코드가 200 (성공)인지 확인
        response.raise_for_status()

        # 응답 받은 JSON 데이터를 파이썬 딕셔너리로 변환하여 반환
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"HTTP 요청 중 에러가 발생했습니다: {e}")
        return None
    except json.JSONDecodeError:
        print("JSON 데이터를 파싱하는 데 실패했습니다.")
        print("응답 내용:", response.text)
        return None


# --- 코드 실행 예제 ---
if __name__ == "__main__":
    search_keyword = "물티슈"
    # '중국내 무료 배송'과 '별점 5점' 필터 적용
    active_filters = ['activeType', 'totalEpScoreLv1']

    # 함수 호출
    result_data = search_products(search_keyword)

    if result_data and result_data.get('success'):
        print(f"✅ '{search_keyword}' 검색 성공!")

        # 상품 목록은 HTML 형태로 반환됨
        product_html_list = result_data.get('data', [])

        print(f"📄 총 {len(product_html_list)}개의 상품을 찾았습니다.\n")

        # 첫 번째 상품의 정보만 파싱해서 출력해보기
        if product_html_list:
                first_product_html = product_html_list[0]
                soup = BeautifulSoup(first_product_html, 'html.parser')

                title = soup.select_one('.product_title a')
                price = soup.select_one('.product_price')
                link = soup.select_one('.product_image a')

                print("--- 첫 번째 상품 정보 ---")
                if title:
                    print(f"상품명: {title.text.strip()}")
                if price:
                    # '원' 글자와 공백을 제거하여 숫자만 남김
                    price_text = price.text.replace('원', '').strip()
                    print(f"가격: {price_text}")
                if link and link.has_attr('href'):
                    product_url = link['href']
                    print(f"링크: {product_url}")
                print("-----------------------\n")

    else:
        print(f"❌ '{search_keyword}' 상품 조회에 실패했습니다.")