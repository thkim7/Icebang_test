# test_mecab.py 파일 생성
import MeCab
import os

print(f"MECABRC 환경 변수: {os.environ.get('MECABRC', '설정되지 않음')}")

try:
    # MeCab 초기화
    mecab = MeCab.Tagger()
    
    # 테스트 텍스트
    text = "KoNLPy가 정상적으로 설치되었음을 확인합니다."
    
    # 형태소 분석
    result = mecab.parse(text)
    print("=== MeCab 형태소 분석 결과 ===")
    print(result)
    
    # 형태소만 추출
    morphs = []
    for line in result.split('\n'):
        if line == 'EOS' or line == '':
            continue
        parts = line.split('\t')
        if len(parts) >= 1:
            morphs.append(parts[0])
    
    print(f"\n추출된 형태소: {morphs}")
    print("✅ MeCab 테스트 성공!")
    
except Exception as e:
    print(f"❌ MeCab 테스트 실패: {e}")
    print("\n추가 디버깅 정보:")
    print(f"설정 파일 존재 여부: {os.path.exists('/usr/local/etc/mecabrc')}")
    print(f"사전 디렉토리 존재 여부: {os.path.exists('/opt/homebrew/lib/mecab/dic/mecab-ko-dic')}")