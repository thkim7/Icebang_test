import torch
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class HybridMatcher:
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
    
    def is_related_product(self, title, keyword, bert_threshold=0.7, debug=False):
        """
        개선된 하이브리드 로직으로 관련 상품 판단
        1. 키워드가 상품명에 직접 포함되면 관련 상품으로 판단 (가장 높은 우선순위)
        2. BERT 유사도 점수가 임계값을 넘으면 관련 상품으로 판단
        """
        
        # 띄어쓰기 없이 키워드 포함 여부 확인 (1단계)
        normalized_title = title.replace(' ', '')
        normalized_keyword = keyword.replace(' ', '')
        
        if normalized_keyword in normalized_title:
            if debug:
                print(f"✅ 관련상품 | 키워드 일치 | 상품명: '{title}'")
            return True, "키워드 일치"

        # BERT 유사도 계산 (2단계)
        similarity = self.get_similarity(title, keyword)

        if debug:
            print(f"    키워드: '{keyword}'")
            print(f"    상품명: '{title}'")
            print(f"    유사도: {similarity:.4f}")
            
        if similarity >= bert_threshold:
            if debug:
                print(f"✅ 관련상품 | BERT 유사도 {similarity:.4f} > {bert_threshold}")
            return True, f"BERT 유사도 {similarity:.4f}"
        else:
            if debug:
                print(f"❌ 무관상품 | 유사도 {similarity:.4f} (기준 미달)")
            return False, f"유사도 {similarity:.4f} (기준 미달)"

def run_tests():
    matcher = HybridMatcher()
    
    # 더 명확하게 구분되는 테스트 케이스
    test_cases_refined = [
        {
            "keyword": "콜라겐마스크팩",
            "products": [
                # ✅ 관련 상품
                ("Wei Xue의 동일한 콜라겐 글루코스아민 유연 스킨 마스크", True),
                ("V 얼굴 마스크 콜라겐 빨간 병 리프팅 페이스 페이드 커팅 퍼팅 마스크", True),
                ("프리미엄 콜라겐 페이셜 마스크 10매", True),
                ("콜라겐마스크팩 100장 (직접 키워드 포함)", True),
                
                # ❌ 무관 상품 (BERT가 혼동했던 유형 + 명확히 다른 카테고리)
                ("히알루론산 수분 앰플 100ml 대용량", False),
                ("비타민C 브라이트닝 세럼", False),
                ("천연 허브 클렌징 폼", False),
                ("애플워치 8세대 45mm 케이스", False),
            ]
        },
        {
            "keyword": "무선이어폰",
            "products": [
                # ✅ 관련 상품
                ("애플 에어팟 프로 무선 이어폰 3세대", True),
                ("삼성 갤럭시 버즈 블루투스 이어폰", True), 
                ("소니 완전무선이어폰 노이즈캔슬링", True),
                
                # ❌ 무관 상품
                ("젠하이저 유선 이어폰 고음질", False),
                ("JBL 블루투스 스피커 휴대용", False),
                ("마이크로소프트 무선 마우스", False),
                ("아이폰 충전기 케이블", False),
            ]
        },
    ]

    print("=" * 80)
    print("🚀 하이브리드 키워드 매칭 테스트 결과")
    print("=" * 80)
    
    bert_thresholds = [0.6, 0.7, 0.8]
    for threshold in bert_thresholds:
        print(f"\n📊 BERT 유사도 임계값: {threshold}")
        print("-" * 60)
        
        total_correct = 0
        total_cases = 0
        
        for case in test_cases_refined:
            keyword = case["keyword"]
            print(f"\n🔍 키워드: '{keyword}'")
            
            for title, expected in case["products"]:
                is_related, reason = matcher.is_related_product(title, keyword, bert_threshold=threshold)
                predicted = is_related
                is_correct = (predicted == expected)
                
                status = "✅" if is_correct else "❌"
                print(f"  {status} {'관련' if predicted else '무관'} (기대: {'관련' if expected else '무관'}) | {title[:40]} | {reason}")
                
                total_correct += is_correct
                total_cases += 1
        
        accuracy = total_correct / total_cases
        print(f"\n🎯 최종 정확도: {total_correct}/{total_cases} = {accuracy:.3f} ({accuracy*100:.1f}%)")

if __name__ == "__main__":
    run_tests()