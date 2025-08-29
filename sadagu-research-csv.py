import urllib

import requests
import json
from bs4 import BeautifulSoup
import csv  # CSV 작업을 위해 모듈 추가


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
    if filters is None:
        filters = ['activeType']

    search_url = "https://ssadagu.kr/shop/ajax.infinity_shop_list.php"

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
    encoded_q = urllib.parse.quote(search_term, safe="")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': f'https://ssadagu.kr/shop/search.php?ss_tx={encoded_q}'
    }

    try:
        response = requests.post(search_url, data=payload, headers=headers)
        response.raise_for_status()
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
    result_data = search_products(search_keyword)

    if result_data and result_data.get('success'):
        print(f"✅ '{search_keyword}' 검색 성공!")
        product_html_list = result_data.get('data', [])
        print(f"📄 총 {len(product_html_list)}개의 상품을 찾았습니다.\n")

        # CSV 파일로 저장하기
        csv_filename = search_keyword+'ssadagu_products.csv'

        # 'utf-8-sig' 인코딩은 Excel에서 한글이 깨지지 않도록 도와줍니다.
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            # CSV 작성기 생성
            csv_writer = csv.writer(csvfile)

            # 1. 헤더(머리말) 작성
            header = ['상품ID', '상품명', '가격(원)', '링크', '이미지URL']
            csv_writer.writerow(header)

            # 2. 각 상품 정보를 한 줄씩 CSV에 작성
            for product_html in product_html_list:
                soup = BeautifulSoup(product_html, 'html.parser')

                # <li> 태그에서 데이터 속성 추출
                li_tag = soup.find('li')
                if not li_tag:
                    continue

                gs_id = li_tag.get('data-gs-id', 'N/A')
                title = li_tag.get('data-title', 'N/A')
                image_url = li_tag.get('data-img-url', 'N/A')

                # 가격과 링크는 내부 태그에서 추출
                price_tag = soup.select_one('.product_price')
                price_krw = price_tag.text.replace('원', '').strip() if price_tag else 'N/A'

                link_tag = soup.select_one('.product_image a')
                product_url = link_tag['href'] if link_tag and link_tag.has_attr('href') else 'N/A'

                # 추출한 데이터를 리스트로 묶어서 CSV 파일에 한 줄 쓰기
                csv_writer.writerow([gs_id, title, price_krw, product_url, image_url])

        print(f"🎉 상품 정보가 '{csv_filename}' 파일로 성공적으로 저장되었습니다.")

    else:
        print(f"❌ '{search_keyword}' 상품 조회에 실패했습니다.")
