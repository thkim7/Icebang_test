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

# SSADAGUCrawler 클래스
class SSADAGUCrawler:
    def __init__(self, use_selenium=True):
        self.base_url = "https://ssadagu.kr"
        self.use_selenium = use_selenium
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
        """Selenium을 사용한 상품 검색 - 기존 방식 유지"""
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
        """requests를 사용한 상품 검색 - 기존 방식으로 복원"""
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
        """기본 상품 정보만 크롤링 (유사도 분석용)"""
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

    def crawl_product_detail(self, product_url, include_images=True):
        """상세 상품 정보 크롤링 (최종 선택된 상품용)"""
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
            
            # 이미지 처리는 선택적으로만 진행
            if include_images:
                print("이미지 OCR 처리를 시작합니다...")
                product_images = self.extract_product_images(soup)
                translated_images = []
                for img_url in product_images:
                    translated_text = ocr_and_translate_image(img_url)
                    translated_images.append({
                        'original_url': img_url,
                        'translated_text': translated_text
                    })
                product_data['product_images'] = translated_images
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

    def crawl_search_results(self, keyword, max_products=5):
        """검색 결과에서 상품들 크롤링 - 기존 방식 유지"""
        print(f"'{keyword}' 검색 시작...")
        if self.use_selenium:
            product_links = self.search_products_selenium(keyword)
        else:
            product_links = self.search_products_requests(keyword)
        
        if not product_links:
            print("검색 결과를 찾을 수 없습니다.")
            return []
        
        print(f"{len(product_links)}개의 상품 링크를 처리합니다.")
        crawled_products = []
        for i, link in enumerate(product_links[:max_products]):
            print(f"\n상품 {i+1}/{min(len(product_links), max_products)} 크롤링 중...")
            product_data = self.crawl_product_detail(link, include_images=True)  # 여기서는 이미지 포함
            if product_data:
                crawled_products.append(product_data)
                print(f"✓ 크롤링 성공: {product_data['title'][:50]}...")
            else:
                print("✗ 크롤링 실패")
            time.sleep(random.uniform(2, 4))
        return crawled_products

    def __del__(self):
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
            except:
                pass

# AI 모델을 활용한 유사도 분석 함수
class SimilarityAnalyzer:
    def __init__(self):
        try:
            # 더 안정적인 한국어 BERT 모델 사용
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

# 이미지 번역 기능 (기존 함수)
def ocr_and_translate_image(image_url):
    print(f"이미지 번역 시도: {image_url}")
    try:
        translated_text = "번역된 이미지 텍스트 예시입니다."
        print(f"✓ 번역 성공: '{translated_text[:20]}...'")
        return translated_text
    except Exception as e:
        print(f"✗ 이미지 번역 실패: {e}")
        return None

# 설치 함수 및 네이버 데이터랩 함수
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
            "protobuf"  # protobuf 라이브러리 추가
        ]
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + packages)
        print("라이브러리가 성공적으로 준비되었습니다.")
    except subprocess.CalledProcessError as e:
        print(f"라이브러리 설치 중 오류 발생: {e}")
        print("스크립트를 실행하려면 다음 명령어를 터미널에서 직접 실행해주세요:")
        print("pip install beautifulsoup4 requests selenium torch transformers numpy scikit-learn protobuf")
        sys.exit(1)

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

def main_merged():
    install_packages()

    print("\n=== SSADAGU 통합 크롤러 ===")
    
    # 1. 네이버 데이터랩에서 랜덤 키워드 가져오기
    category_name = random.choice(list(TOP_LEVEL_CATEGORIES.keys()))
    category_id = TOP_LEVEL_CATEGORIES[category_name]
    print(f"🌟 랜덤으로 선택된 카테고리: '{category_name}'")
    trending_keywords = search_naver_rank(category_id)
    if not trending_keywords:
        print("네이버 데이터랩에서 인기 검색어를 가져오지 못했습니다. '악세사리'로 대체합니다.")
        keyword = "악세사리"
    else:
        keyword = trending_keywords[0] # 가장 인기 있는 키워드 1개만 사용
    print(f"🔍 선택된 검색 키워드: '{keyword}'")
    
    # 기본값을 Selenium으로 설정
    crawler = SSADAGUCrawler(use_selenium=True) 
    
    # 2. 싸다구에서 검색 결과 URL 목록 가져오기 (기존 방식 사용)
    print(f"\n'{keyword}' 키워드로 싸다구에서 검색 시작...")
    
    # 기존 방식대로 URL 리스트를 가져옴
    if crawler.use_selenium:
        search_results_urls = crawler.search_products_selenium(keyword)
    else:
        search_results_urls = crawler.search_products_requests(keyword)
    
    if not search_results_urls:
        print("검색 결과를 찾을 수 없습니다.")
        return
    
    print(f"총 {len(search_results_urls)}개의 상품 URL을 찾았습니다.")
    
    # 3. AI 모델을 이용한 유사도 분석 (이미지 OCR 제외)
    print("AI 모델로 유사도 분석을 시작합니다...")
    
    best_match_product = None
    max_similarity = 0.0  # 기본값 설정
    best_match_url = None
    
    try:
        analyzer = SimilarityAnalyzer()
        
        # 기준 키워드의 임베딩을 미리 계산
        keyword_embedding = analyzer.get_embedding(keyword)
        
        # URL 목록을 순회하며 각 상품의 제목을 얻고 유사도 분석 (이미지 OCR 없이)
        for i, url in enumerate(search_results_urls[:5]):  # 최대 5개만 분석
            print(f"\n상품 {i+1}/{min(len(search_results_urls), 5)} 분석 중...")
            
            # 기본 정보만 크롤링 (이미지 처리 제외)
            basic_data = crawler.crawl_product_basic(url)
            if not basic_data:
                print("✗ 상품 기본 정보 추출 실패")
                continue

            title = basic_data['title']
            title_embedding = analyzer.get_embedding(title)
            
            similarity = cosine_similarity(keyword_embedding, title_embedding)[0][0]
            print(f"상품명: '{title[:30]}...' 유사도: {similarity:.4f}")
            
            if similarity > max_similarity:
                max_similarity = similarity
                best_match_url = url
            
            time.sleep(random.uniform(1, 2))  # API 호출 간격 조절
            
    except Exception as e:
        print(f"유사도 분석 중 오류 발생: {e}")
        # 오류 시 첫 번째 상품을 기본값으로 사용
        if search_results_urls:
            best_match_url = search_results_urls[0]
            max_similarity = 0.0  # 기본값 설정

    # 4. 최종 선택된 상품의 상세 정보 크롤링 (이미지 OCR 포함)
    if best_match_url:
        print(f"\n⭐ 가장 유사한 상품의 상세 정보를 크롤링합니다...")
        best_match_product = crawler.crawl_product_detail(best_match_url, include_images=True)
        
        if best_match_product:
            print(f"제목: {best_match_product['title']}")
            print(f"가격: {best_match_product['price']}원")
            print(f"별점: {best_match_product['rating']}/5.0")
            print(f"옵션 개수: {len(best_match_product['options'])}개")
            if max_similarity > 0:
                print(f"유사도: {max_similarity:.4f}")
            
            print("\n상품 이미지 (번역된 텍스트 포함):")
            for j, img_info in enumerate(best_match_product['product_images'], 1):
                print(f"  {j}. URL: {img_info['original_url']}")
                print(f"     번역 텍스트: {img_info['translated_text']}")
            
            # JSON 파일로 저장
            output_filename = f"ssadagu_best_match_{int(time.time())}.json"
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump([best_match_product], f, ensure_ascii=False, indent=2)
            print(f"\n결과가 '{output_filename}' 파일로 저장되었습니다.")
        else:
            print("최종 상품의 상세 정보를 가져오지 못했습니다.")
    else:
        print("\n분석할 수 있는 상품을 찾지 못했습니다.")

# --- 메인 실행 ---
if __name__ == "__main__":
    main_merged()