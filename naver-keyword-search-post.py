import requests
import json
category_map = {
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

# 예시: '식품' 카테고리의 ID 가져오기
food_cid = category_map["출산/육아"]
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

print("\n--- 인기 검색어 순위 ---")
for k, v in dic1.items():
    print(f"{k}: {v}")

with open('naver_shopping_categories.json', 'w', encoding='utf-8') as f:
    json.dump(dic1, f, ensure_ascii=False, indent=2)
