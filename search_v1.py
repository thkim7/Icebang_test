import subprocess
import sys
import requests
import json
import time
import random
import urllib
from bs4 import BeautifulSoup
import csv


def install_packages():
    """필요한 라이브러리를 설치합니다."""
    try:
        print("필수 라이브러리 (beautifulsoup4, requests) 설치를 시도합니다...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4", "requests"])
        print("라이브러리가 성공적으로 준비되었습니다.")
    except subprocess.CalledProcessError as e:
        print(f"라이브러리 설치 중 오류 발생: {e}")
        print("스크립트를 실행하려면 'pip install beautifulsoup4 requests' 명령어를 터미널에서 직접 실행해주세요.")
        sys.exit(1)


# --- 1. 최상위 카테고리 목록 ---
TOP_LEVEL_CATEGORIES = {
    "패션의류": "50000000",
    "패션잡화": "50000001",
    "화장품/미용": "50000002",
    "디지털/가전": "50000003",
    "가구/인테리어": "50000004",
    "출산/육아": "50000005",
    "식품": "50000006",
    "스포츠/레저": "50000007",
    "생활/건강": "50000008",
    "여가/생활편의": "50000009",
    "면세점": "50000010",
    "도서": "50005542"
}

def search_naver_rank(food_cid):
    print(f"식품 카테고리 ID: {food_cid}")
    # 출력: 식품 카테고리 ID: 50000006
    # 1. 요청을 보낼 URL
    url = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"

    # 2. Headers 정보 설정 (User-Agent는 본인 것으로 교체하는 것을 권장)
    #    개발자 도구 -> Network -> getCategoryKeywordRank.naver -> Headers -> Request Headers 에서 복사
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }
    dic1 = {}

    # 3. Payload (Form Data) 정보 설정 - 원하는 조건으로 수정하여 사용
    #    '패션의류(50000000)' 카테고리의 2024년 1월 한 달간 전체 인기 검색어 순위
    for a in range(1, 3):
        payload = {
            "cid": food_cid,
            "timeUnit": "date",  # 월간 단위
            "startDate": "2025-08-28",
            "endDate": "2025-08-29",
            "age": "",  # 전체 연령
            "gender": "",  # 전체 성별
            "device": "",  # 전체 기기
            "page": a,
        }

        # 4. POST 요청 보내기
        response = requests.post(url, headers=headers, data=payload)

        # 5. 응답 확인 및 데이터 파싱
        if response.status_code == 200:
            try:
                # 응답 받은 데이터를 JSON 형태로 파싱
                data = response.json()

                # 보기 좋게 출력 (indent=2)
                print(json.dumps(data, indent=2, ensure_ascii=False))

                # 순위와 키워드만 추출하여 출력
                # print("\n--- 인기 검색어 순위 ---")
                for item in data.get('ranks', []):
                    dic1[item.get('rank')] = item.get('keyword')
                    # print(f"{item['rank']}. {item['keyword']}")

            except json.JSONDecodeError:
                print("JSON 데이터를 파싱하는 데 실패했습니다.")
                print("응답 내용:", response.text)
        else:
            print(f"데이터를 가져오는 데 실패했습니다. 상태 코드: {response.status_code}")
    return dic1


# --- 2. '싸다구' 상품 검색 관련 함수 ---
def search_products_ssadagu(search_term, page=1):
    """싸다구 (ssadagu.kr) 사이트에서 상품을 검색하는 함수"""
    search_url = "https://ssadagu.kr/shop/ajax.infinity_shop_list.php"
    payload = {
        'page_div_id': 'infinity_item_list', 'page_type': 'pc', 'ss_tx': search_term,
        'search_option_array': ['activeType'], 'hi_platform': '1688', 'sort_item': 'default', 'page': page
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
        print("JSON 데이터를 파싱하는 데 실패했습니다.");
        print("응답 내용:", response.text)
        return None






# --- 3. 메인 실행 로직 ---
if __name__ == "__main__":
    install_packages()

    print("\n✅ 최상위 카테고리 목록에서 하나를 랜덤으로 선택합니다.")

    # 최상위 카테고리 이름들 중에서 하나를 랜덤으로 선택
    top_level_names = list(TOP_LEVEL_CATEGORIES.keys())
    search_categories = random.choice(top_level_names)
    print(f"🌟 랜덤으로 선택된 카테고리: '{search_categories}'")
    dic = search_naver_rank(TOP_LEVEL_CATEGORIES[search_categories])
    search_keyword = random.choice(dic)

    # '싸다구'에서 상품 검색 및 CSV 저장
    result_data = search_products_ssadagu(search_keyword)

    if result_data and result_data.get('success'):
        product_html_list = result_data.get('data', [])
        print(f"📄 총 {len(product_html_list)}개의 상품을 찾았습니다.\n")

        if not product_html_list:
            print(f"'{search_keyword}'에 대한 검색 결과가 없어 CSV 파일을 생성하지 않습니다.")
        else:
            safe_keyword = "".join(c for c in search_keyword if c.isalnum() or c in (' ', '_')).rstrip()
            csv_filename = f'{safe_keyword}_ssadagu_products.csv'

            with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                csv_writer = csv.writer(csvfile)
                header = ['상품ID', '상품명', '가격(원)', '링크', '이미지URL']
                csv_writer.writerow(header)

                for product_html in product_html_list:
                    soup = BeautifulSoup(product_html, 'html.parser')
                    li_tag = soup.find('li')
                    if not li_tag: continue
                    gs_id = li_tag.get('data-gs-id', 'N/A')
                    title = li_tag.get('data-title', 'N/A')
                    image_url = li_tag.get('data-img-url', 'N/A')
                    price_tag = soup.select_one('.product_price')
                    price_krw = price_tag.text.replace('원', '').strip() if price_tag else 'N/A'
                    link_tag = soup.select_one('.product_image a')
                    product_url = link_tag['href'] if link_tag and link_tag.has_attr('href') else 'N/A'
                    csv_writer.writerow([gs_id, title, price_krw, product_url, image_url])

            print(f"🎉 상품 정보가 '{csv_filename}' 파일로 성공적으로 저장되었습니다.")
    else:
        print(f"❌ '{search_keyword}' 상품 조회에 실패했습니다.")