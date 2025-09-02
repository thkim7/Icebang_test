import torch
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class BERTOnlyMatcher:
    def __init__(self):
        try:
            # 한국어 특화 모델 우선 시도
            self.tokenizer = AutoTokenizer.from_pretrained('klue/bert-base')
            self.model = AutoModel.from_pretrained('klue/bert-base')
            print("✅ KLUE BERT 모델 로딩 성공")
        except Exception as e:
            print(f"KLUE BERT 실패: {e}")
            try:
                # 다국어 모델로 대체
                self.tokenizer = AutoTokenizer.from_pretrained('bert-base-multilingual-cased')
                self.model = AutoModel.from_pretrained('bert-base-multilingual-cased')
                print("✅ 다국어 BERT 모델 로딩 성공")
            except Exception as e2:
                print(f"모든 BERT 모델 실패: {e2}")
                raise e2
    
    def get_embedding(self, text):
        """텍스트를 BERT 임베딩으로 변환"""
        inputs = self.tokenizer(text, return_tensors='pt', padding=True, truncation=True, max_length=128)
        with torch.no_grad():
            outputs = self.model(**inputs)
        # [CLS] 토큰의 임베딩 사용
        return outputs.last_hidden_state[:, 0, :].numpy()
    
    def get_similarity(self, text1, text2):
        """두 텍스트 간의 코사인 유사도 계산"""
        embedding1 = self.get_embedding(text1)
        embedding2 = self.get_embedding(text2)
        return cosine_similarity(embedding1, embedding2)[0][0]
    
    def is_related_product(self, title, keyword, threshold=0.5, debug=False):
        """BERT 유사도만으로 관련 상품 판단"""
        similarity = self.get_similarity(title, keyword)
        
        if debug:
            print(f"    키워드: '{keyword}'")
            print(f"    상품명: '{title}'")
            print(f"    유사도: {similarity:.4f}")
            print(f"    결과: {'✅ 관련상품' if similarity >= threshold else '❌ 무관상품'}")
        
        return similarity >= threshold

# 실제 테스트 케이스들
def test_bert_matching():
    matcher = BERTOnlyMatcher()
    
    # 실제 쇼핑몰에서 나올 법한 케이스들
    test_cases = [
        {
            "keyword": "콜라겐마스크팩",
            "products": [
                ("콜라겐 얼굴 빛나는 폭발 마스크 수분 팩", True),  # 관련상품
                ("프리미엄 콜라겐 페이셜 마스크 10매", True),     # 관련상품
                ("히알루론산 수분 마스크팩 대용량", False),       # 애매한 케이스
                ("비타민C 브라이트닝 마스크", False),             # 무관상품
                ("콜라겐 앰플 에센스 세럼", False),               # 무관상품 (마스크팩 아님)
                ("천연 허브 클렌징 폼", False),                  # 완전 무관
            ]
        },
        {
            "keyword": "무선이어폰",
            "products": [
                ("애플 에어팟 프로 무선 이어폰 3세대", True),
                ("삼성 갤럭시 버즈 블루투스 이어폰", True), 
                ("소니 완전무선이어폰 노이즈캔슬링", True),
                ("젠하이저 유선 이어폰 고음질", False),
                ("JBL 블루투스 스피커 휴대용", False),
                ("아이폰 충전기 케이블", False),
            ]
        },
        {
            "keyword": "운동화",
            "products": [
                ("나이키 에어맥스 런닝화 남성용", True),
                ("아디다스 스니커즈 화이트", True),
                ("뉴발란스 워킹화 편안한", True),
                ("컨버스 캔버스화 클래식", True),
                ("구두 정장화 가죽 남성", False),
                ("슬리퍼 실내화 편한", False),
            ]
        },
        {
            "keyword": "다이어트보조제",
            "products": [
                ("가르시니아 다이어트 보조제 캡슐", True),
                ("체지방감소 CLA 건강기능식품", True),
                ("L-카르니틴 다이어트 서포트", True),
                ("프로틴 파우더 단백질 보충제", False),  # 애매함
                ("종합비타민 멀티비타민", False),
                ("감기약 종합감기", False),
            ]
        }
    ]
    
    # 다양한 임계값으로 테스트
    thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]
    
    print("=" * 80)
    print("BERT 유사도만 사용한 키워드 매칭 테스트")
    print("=" * 80)
    
    for threshold in thresholds:
        print(f"\n📊 임계값: {threshold}")
        print("-" * 60)
        
        total_correct = 0
        total_cases = 0
        
        for test_case in test_cases:
            keyword = test_case["keyword"]
            print(f"\n🔍 키워드: '{keyword}'")
            
            for product_title, expected in test_case["products"]:
                similarity = matcher.get_similarity(product_title, keyword)
                predicted = similarity >= threshold
                is_correct = predicted == expected
                
                status = "✅" if is_correct else "❌"
                expected_str = "관련" if expected else "무관"
                predicted_str = "관련" if predicted else "무관"
                
                print(f"  {status} {similarity:.3f} | {expected_str}→{predicted_str} | {product_title[:40]}")
                
                total_correct += is_correct
                total_cases += 1
        
        accuracy = total_correct / total_cases
        print(f"\n🎯 정확도: {total_correct}/{total_cases} = {accuracy:.3f} ({accuracy*100:.1f}%)")

# 성능 비교 테스트
def performance_comparison():
    """기존 방식 vs BERT만 사용 성능 비교"""
    print("\n" + "="*80)
    print("성능 비교: 기존 키워드 매칭 vs BERT 유사도")
    print("="*80)
    
    matcher = BERTOnlyMatcher()
    
    # 실제 문제가 됐던 케이스들
    problem_cases = [
        {
            "keyword": "콜라겐마스크팩",
            "titles": [
                "콜라겐 얼굴 빛나는 폭발 마스크 수분 팩",  # 키워드 매칭으로는 어려웠던 케이스
                "프리미엄 골드 콜라겐 페이셜 마스크 시트",
                "히알루론산 콜라겐 복합 마스크팩 10매",
            ]
        },
        {
            "keyword": "블루투스이어폰", 
            "titles": [
                "무선 블루투스 이어폰 TWS 노이즈캔슬링",
                "에어팟 스타일 완전무선 이어폰",
                "갤럭시 버즈 호환 블루투스 헤드셋",
            ]
        }
    ]
    
    for case in problem_cases:
        keyword = case["keyword"]
        print(f"\n🔍 검색 키워드: '{keyword}'")
        print("-" * 50)
        
        for title in case["titles"]:
            similarity = matcher.get_similarity(title, keyword)
            print(f"유사도 {similarity:.3f} | {title}")
            
            # 임계값별 판정
            for threshold in [0.4, 0.5, 0.6]:
                result = "관련상품" if similarity >= threshold else "무관상품"
                print(f"  - 임계값 {threshold}: {result}")

if __name__ == "__main__":
    test_bert_matching()
    performance_comparison()