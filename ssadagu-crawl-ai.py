import requests
import urllib.parse
from bs4 import BeautifulSoup
import re
import json
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import subprocess
import sys
import csv

from transformers import AutoTokenizer, AutoModel
import torch
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# JSON 직렬화를 위한 커스텀 인코더 클래스
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

# SSADAGUCrawler 클래스 (KoNLPy 오류 수정)
class SSADAGUCrawler:
    def __init__(self, use_selenium=True):
        self.base_url = "https://ssadagu.kr"
        self.use_selenium = use_selenium
        self.konlpy_available = False
        
        # KoNLPy 사용 가능 여부 확인
        try:
            from konlpy.tag import Okt
            test_okt = Okt()
            test_result = test_okt.morphs("테스트")
            if test_result:
                self.konlpy_available = True
                print("KoNLPy 형태소 분석기 사용 가능")
        except Exception as e:
            print(f"KoNLPy 사용 불가 (규칙 기반으로 대체): {e}")
        
        if use_selenium:
            self.setup_selenium()
        else:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
    def setup_selenium(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            print("Selenium WebDriver 초기화 완료")
        except Exception as e:
            print(f"Selenium 초기화 실패: {e}")
            print("requests 방식으로 대체합니다.")
            self.use_selenium = False
            self.session = requests.Session()

    def search_products_selenium(self, keyword):
        """Selenium을 사용한 상품 검색"""
        encoded_keyword = urllib.parse.quote(keyword)
        search_url = f"{self.base_url}/shop/search.php?ss_tx={encoded_keyword}"
        try:
            self.driver.get(search_url)
            time.sleep(5)
            product_links = []
            link_elements = self.driver.find_elements(By.TAG_NAME, "a")
            for element in link_elements:
                href = element.get_attribute('href')
                if href and 'view.php' in href and ('platform=1688' in href or 'num_iid' in href):
                    product_links.append(href)
            product_links = list(set(product_links))
            print(f"Selenium으로 발견한 상품 링크: {len(product_links)}개")
            return product_links
        except Exception as e:
            print(f"Selenium 검색 오류: {e}")
            return []

    def search_products_requests(self, keyword):
        """requests를 사용한 상품 검색"""
        encoded_keyword = urllib.parse.quote(keyword)
        search_url = f"{self.base_url}/shop/search.php?ss_tx={encoded_keyword}"
        try:
            response = self.session.get(search_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            product_links = []
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link['href']
                if 'view.php' in href and ('platform=1688' in href or 'num_iid' in href):
                    full_url = f"{self.base_url}{href}" if href.startswith('/') else href
                    product_links.append(full_url)
            print(f"requests로 발견한 상품 링크: {len(product_links)}개")
            return product_links
        except Exception as e:
            print(f"requests 검색 오류: {e}")
            return []

    def crawl_product_basic(self, product_url):
        """기본 상품 정보만 크롤링"""
        try:
            if self.use_selenium:
                self.driver.get(product_url)
                self.wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            else:
                response = requests.get(product_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
            
            title_element = soup.find('h1', {'id': 'kakaotitle'})
            title = title_element.get_text(strip=True) if title_element else "제목 없음"
            
            price = 0
            price_selectors = [
                'span.price.gsItemPriceKWR',
                '.pdt_price span.price',
                'span.price',
                '.price'
            ]
            for selector in price_selectors:
                price_element = soup.select_one(selector)
                if price_element:
                    price_text = price_element.get_text(strip=True).replace(',', '').replace('원', '')
                    price_match = re.search(r'(\d+)', price_text)
                    if price_match:
                        price = int(price_match.group(1))
                        break

            rating = self.calculate_rating(soup)
            
            return {
                'url': product_url,
                'title': title,
                'price': price,
                'rating': rating
            }
        except Exception as e:
            print(f"기본 상품 크롤링 오류 ({product_url}): {e}")
            return None

    def crawl_product_detail(self, product_url, include_images=False):
        """상세 상품 정보 크롤링"""
        try:
            if self.use_selenium:
                self.driver.get(product_url)
                self.wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            else:
                response = requests.get(product_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
            
            title_element = soup.find('h1', {'id': 'kakaotitle'})
            title = title_element.get_text(strip=True) if title_element else "제목 없음"
            
            price = 0
            price_selectors = [
                'span.price.gsItemPriceKWR',
                '.pdt_price span.price',
                'span.price',
                '.price'
            ]
            for selector in price_selectors:
                price_element = soup.select_one(selector)
                if price_element:
                    price_text = price_element.get_text(strip=True).replace(',', '').replace('원', '')
                    price_match = re.search(r'(\d+)', price_text)
                    if price_match:
                        price = int(price_match.group(1))
                        break

            rating = self.calculate_rating(soup)
            options = self.extract_product_options(soup)
            material_info = self.extract_material_info(soup)
            
            product_data = {
                'url': product_url,
                'title': title,
                'price': price,
                'rating': rating,
                'options': options,
                'material_info': material_info,
                'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            if include_images:
                print("이미지 정보 추출 중...")
                product_images = self.extract_product_images(soup)
                product_data['product_images'] = [{'original_url': img_url} for img_url in product_images]
            else:
                product_data['product_images'] = []
                
            return product_data
        except Exception as e:
            print(f"상품 크롤링 오류 ({product_url}): {e}")
            return None

    def calculate_rating(self, soup):
        rating = 0.0
        star_containers = [
            soup.find('a', class_='start'),
            soup.find('div', class_=re.compile(r'star|rating')),
            soup.find('a', href='#reviews_wrap')
        ]
        for container in star_containers:
            if container:
                star_imgs = container.find_all('img')
                for img in star_imgs:
                    src = img.get('src', '')
                    if 'icon_star.svg' in src:
                        rating += 1
                    elif 'icon_star_half.svg' in src:
                        rating += 0.5
                break
        return rating

    def extract_product_options(self, soup):
        options = []
        sku_list = soup.find('ul', {'id': 'skubox'})
        if sku_list:
            option_items = sku_list.find_all('li', class_=re.compile(r'imgWrapper'))
            for item in option_items:
                title_element = item.find('a', title=True)
                if title_element:
                    option_name = title_element.get('title', '').strip()
                    stock = 0
                    item_text = item.get_text()
                    stock_match = re.search(r'재고\s*:\s*(\d+)', item_text)
                    if stock_match:
                        stock = int(stock_match.group(1))
                    img_element = item.find('img', class_='colorSpec_hashPic')
                    image_url = ""
                    if img_element and img_element.get('src'):
                        image_url = img_element['src']
                    if option_name:
                        options.append({
                            'name': option_name,
                            'stock': stock,
                            'image_url': image_url
                        })
        return options

    def extract_product_images(self, soup):
        images = []
        img_elements = soup.find_all('img', {'id': re.compile(r'img_translate_\d+')})
        for img in img_elements:
            src = img.get('src', '')
            if src:
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = self.base_url + src
                elif src.startswith('http'):
                    pass
                else:
                    continue
                images.append(src)
        return images

    def extract_material_info(self, soup):
        material_info = {}
        info_items = soup.find_all('div', class_='pro-info-item')
        for item in info_items:
            title_element = item.find('div', class_='pro-info-title')
            info_element = item.find('div', class_='pro-info-info')
            if title_element and info_element:
                title = title_element.get_text(strip=True)
                info = info_element.get_text(strip=True)
                material_info[title] = info
        return material_info

    def contains_keyword(self, title, keyword):
        """안전한 키워드 매칭 (KoNLPy 오류 방지)"""
        title_lower = title.lower().strip()
        keyword_lower = keyword.lower().strip()
        
        # 1. 완전 포함 검사
        if keyword_lower in title_lower:
            return True
        
        # 2. 형태소 분석 (안전하게)
        try:
            if self.konlpy_available:
                from konlpy.tag import Okt
                okt = Okt()
                
                keyword_morphs = okt.nouns(keyword_lower)
                if not keyword_morphs:  # 명사가 없으면 일반 형태소
                    keyword_morphs = okt.morphs(keyword_lower)
                
                title_morphs = okt.nouns(title_lower)
                if not title_morphs:
                    title_morphs = okt.morphs(title_lower)
                
                # 형태소 매칭
                matched = 0
                for kw in keyword_morphs:
                    if len(kw) >= 2:
                        for tw in title_morphs:
                            if kw == tw or kw in tw or tw in kw:
                                matched += 1
                                break
                
                match_ratio = matched / len(keyword_morphs) if keyword_morphs else 0
                if match_ratio >= 0.4:
                    print(f"    형태소 매칭 성공: {matched}/{len(keyword_morphs)} = {match_ratio:.3f}")
                    return True
                    
        except Exception as e:
            print(f"    형태소 분석 오류, 규칙 기반으로 대체: {e}")
        
        # 3. 규칙 기반 분석 (KoNLPy 실패시)
        return self._simple_keyword_match(title_lower, keyword_lower)
    
    def _simple_keyword_match(self, title, keyword):
        """간단한 키워드 매칭"""
        # 공백으로 분리
        title_words = title.split()
        keyword_words = keyword.split()
        
        matched = 0
        for kw in keyword_words:
            if len(kw) >= 2:
                for tw in title_words:
                    if kw in tw or tw in kw:
                        matched += 1
                        break
        
        match_ratio = matched / len(keyword_words) if keyword_words else 0
        return match_ratio >= 0.3

    def __del__(self):
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
            except:
                pass

# 텍스트 유사도 분석기
class SimilarityAnalyzer:
    def __init__(self):
        try:
            self.tokenizer = AutoTokenizer.from_pretrained('klue/bert-base')
            self.model = AutoModel.from_pretrained('klue/bert-base')
            print("KLUE BERT 모델 로딩 성공")
        except Exception as e:
            print(f"KLUE BERT 로딩 실패, 다국어 BERT로 대체: {e}")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained('bert-base-multilingual-cased')
                self.model = AutoModel.from_pretrained('bert-base-multilingual-cased')
                print("다국어 BERT 모델 로딩 성공")
            except Exception as e2:
                print(f"모든 BERT 모델 로딩 실패: {e2}")
                raise e2
    
    def get_embedding(self, text):
        inputs = self.tokenizer(text, return_tensors='pt', padding=True, truncation=True, max_length=128)
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state[:, 0, :].numpy()

    def get_similarity(self, text1, text2):
        embedding1 = self.get_embedding(text1)
        embedding2 = self.get_embedding(text2)
        return cosine_similarity(embedding1, embedding2)[0][0]

# 라이브러리 설치 함수
def install_packages():
    try:
        print("필수 라이브러리 설치를 시도합니다...")
        packages = [
            "beautifulsoup4", 
            "requests", 
            "selenium", 
            "torch", 
            "transformers", 
            "numpy", 
            "scikit-learn",
            "protobuf"
        ]
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + packages)
        print("라이브러리가 성공적으로 준비되었습니다.")
        
        # KoNLPy는 선택적 설치
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "konlpy"])
            print("KoNLPy 설치 성공")
        except:
            print("KoNLPy 설치 실패 (선택사항) - 규칙 기반으로 대체")
            
    except subprocess.CalledProcessError as e:
        print(f"라이브러리 설치 중 오류 발생: {e}")
        print("스크립트를 실행하려면 다음 명령어를 터미널에서 직접 실행해주세요:")
        print("pip install beautifulsoup4 requests selenium torch transformers numpy scikit-learn protobuf")
        sys.exit(1)

# 네이버 데이터랩
TOP_LEVEL_CATEGORIES = {
    "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002",
    "디지털/가전": "50000003", "가구/인테리어": "50000004", "출산/육아": "50000005",
    "식품": "50000006", "스포츠/레저": "50000007", "생활/건강": "50000008",
    "여가/생활편의": "50000009", "면세점": "50000010", "도서": "50005542"
}

def search_naver_rank(category_id):
    url = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }
    keywords = []
    payload = {
        "cid": category_id,
        "timeUnit": "date",
        "startDate": "2025-08-28",
        "endDate": "2025-08-29",
        "age": "",
        "gender": "",
        "device": "",
        "page": 1,
    }
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        data = response.json()
        for item in data.get('ranks', []):
            keywords.append(item.get('keyword'))
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"네이버 데이터랩에서 데이터를 가져오는 데 실패했습니다: {e}")
    return keywords

# 메인 함수 (원래대로 단순하게)
def main_simplified():
    """원래 코드와 동일한 단순한 크롤러 - KoNLPy 오류만 수정"""
    install_packages()
    print("\n=== SSADAGU 크롤러 (KoNLPy 오류 수정) ===")

    crawler = SSADAGUCrawler(use_selenium=True)
    analyzer = SimilarityAnalyzer()

    TEXT_SIMILARITY_THRESHOLD = 0.6
    MAX_RETRY = 5

    best_match_product = None
    best_match_url = None

    for attempt in range(MAX_RETRY):
        category_name = random.choice(list(TOP_LEVEL_CATEGORIES.keys()))
        category_id = TOP_LEVEL_CATEGORIES[category_name]
        trending_keywords = search_naver_rank(category_id)

        keyword = random.choice(trending_keywords) if trending_keywords else "악세사리"
        print(f"\n[{attempt+1}/{MAX_RETRY}] 선택된 카테고리: {category_name}, 키워드: {keyword}")

        # 검색
        search_results_urls = (
            crawler.search_products_selenium(keyword)
            if crawler.use_selenium
            else crawler.search_products_requests(keyword)
        )

        if not search_results_urls:
            print("검색 결과 없음 → 다음 키워드로 재시도")
            continue

        print(f"총 {len(search_results_urls)}개 상품 검색됨, 최대 20개까지 분석")

        try:
            # 1단계: 전체 상품에서 기본 정보 수집
            all_products = []
            keyword_included_products = []
            
            for i, url in enumerate(search_results_urls[:20]):
                basic_data = crawler.crawl_product_basic(url)
                if not basic_data or basic_data['title'] == "제목 없음":
                    continue
                
                print(f"상품 {i+1}: {basic_data['title'][:50]}")
                all_products.append(basic_data)
                
                # 키워드 포함 여부 확인 (수정된 매칭 사용)
                if crawler.contains_keyword(basic_data['title'], keyword):
                    keyword_included_products.append(basic_data)
                    print(f"  🔍 키워드 '{keyword}' 매칭됨!")

            print(f"\n전체 유효 상품: {len(all_products)}개")
            print(f"키워드 매칭 상품: {len(keyword_included_products)}개")

            # 2단계: 선택 로직
            selected_product = None
            selection_reason = ""

            if len(keyword_included_products) == 1:
                selected_product = keyword_included_products[0]
                selection_reason = "키워드 매칭 상품 1개 → 바로 선택"
                print(f"✅ {selection_reason}")
                
            elif len(keyword_included_products) > 1:
                print("🔄 키워드 매칭 상품 여러개 → 텍스트 유사도 비교")
                keyword_embedding = analyzer.get_embedding(keyword)
                best_similarity = 0.0
                
                for product in keyword_included_products:
                    title_embedding = analyzer.get_embedding(product['title'])
                    similarity = cosine_similarity(keyword_embedding, title_embedding)[0][0]
                    print(f"  {product['title'][:40]} | 유사도: {similarity:.4f}")
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        selected_product = product
                        
                selection_reason = f"키워드 매칭 상품 중 최고 유사도({best_similarity:.4f})"
                print(f"✅ {selection_reason}")
                
            elif len(keyword_included_products) == 0:
                print("🔄 키워드 매칭 상품 없음 → 전체 텍스트 유사도 검증")
                keyword_embedding = analyzer.get_embedding(keyword)
                best_similarity = 0.0
                
                for product in all_products:
                    title_embedding = analyzer.get_embedding(product['title'])
                    similarity = cosine_similarity(keyword_embedding, title_embedding)[0][0]
                    print(f"  {product['title'][:40]} | 유사도: {similarity:.4f}")
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        selected_product = product
                
                if best_similarity >= TEXT_SIMILARITY_THRESHOLD:
                    selection_reason = f"전체 검증 중 최고 유사도({best_similarity:.4f}) 기준 통과"
                    print(f"✅ {selection_reason}")
                else:
                    print(f"❌ 최고 유사도({best_similarity:.4f}) < 기준({TEXT_SIMILARITY_THRESHOLD}) → 다음 키워드로")
                    continue

            # 3단계: 선택된 상품이 있으면 상세 크롤링 후 종료
            if selected_product:
                print(f"\n🎯 최종 선택: {selected_product['title']}")
                print(f"선택 이유: {selection_reason}")
                
                # 상세 정보 크롤링
                best_match_product = crawler.crawl_product_detail(selected_product['url'], include_images=True)
                if best_match_product:
                    best_match_product['selection_reason'] = selection_reason
                    best_match_url = selected_product['url']
                    break
                else:
                    print("상세 크롤링 실패 → 다음 키워드로 재시도")
                    continue

        except Exception as e:
            print(f"분석 과정 오류: {e}")
            continue

    # 최종 결과 처리
    if best_match_product:
        print(f"\n🎉 크롤링 완료!")
        print(f"제목: {best_match_product['title']}")
        print(f"가격: {best_match_product['price']}원")
        print(f"별점: {best_match_product['rating']}")
        print(f"선택 이유: {best_match_product['selection_reason']}")

        output_filename = f"fixed_crawler_result_{int(time.time())}.json"
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(best_match_product, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)
        print(f"결과 저장 완료: {output_filename}")
        
        return best_match_product
    else:
        print("\n😞 조건을 만족하는 상품을 찾지 못했습니다.")
        return None

# 메인 실행
if __name__ == "__main__":
    main_simplified()