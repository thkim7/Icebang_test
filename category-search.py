import requests
import json
import time

# 요청 URL 및 Headers
url = "https://datalab.naver.com/shoppingInsight/getCategory.naver"
headers = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}

# 최상위(1depth) 카테고리 목록
top_level_categories = {
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

# 모든 카테고리를 저장할 리스트
all_categories = []


def get_subcategories(parent_cid, parent_name, depth):
    """
    특정 카테고리 ID를 받아 하위 카테고리를 재귀적으로 탐색하는 함수
    :param parent_cid: 부모 카테고리 ID
    :param parent_name: 부모 카테고리 이름
    :param depth: 현재 카테고리의 깊이 (출력 시 들여쓰기용)
    """
    # 서버에 부담을 주지 않기 위해 잠시 대기
    time.sleep(0.3)

    # Payload 설정
    payload = {"cid": parent_cid}

    # POST 요청
    response = requests.post(url, headers=headers, data=payload)

    if response.status_code != 200:
        print(f"Error: {response.status_code} - {parent_name}({parent_cid})")
        return

    try:
        subcategories = response.json()

        # 하위 카테고리가 없으면 함수 종료
        if not subcategories:
            return

        for sub_cat in subcategories:
            cat_name = sub_cat['name']
            cat_id = sub_cat['cid']

            # 카테고리 정보 저장 및 출력
            indent = "  " * depth
            print(f"{indent}- {cat_name} ({cat_id})")
            all_categories.append({'name': cat_name, 'cid': cat_id, 'depth': depth + 1})

            # 하위 카테고리가 더 있다면 재귀 호출
            if sub_cat['hasChild']:
                get_subcategories(cat_id, cat_name, depth + 1)

    except json.JSONDecodeError:
        print(f"JSON Decode Error for {parent_name}({parent_cid})")


# --- 실행 부분 ---
print("네이버 쇼핑 전체 카테고리 목록 크롤링 시작")

# 최상위 카테고리부터 탐색 시작
for name, cid in top_level_categories.items():
    print(f"\n[{name}] ({cid})")
    all_categories.append({'name': name, 'cid': cid, 'depth': 1})
    get_subcategories(cid, name, depth=1)

print("\n\n--- 크롤링 완료 ---")
print(f"총 {len(all_categories)}개의 카테고리를 찾았습니다.")

# 찾은 카테고리 목록을 JSON 파일로 저장 (선택 사항)
with open('naver_shopping_categories.json', 'w', encoding='utf-8') as f:
    json.dump(all_categories, f, ensure_ascii=False, indent=2)

print("naver_shopping_categories.json 파일로 저장되었습니다.")