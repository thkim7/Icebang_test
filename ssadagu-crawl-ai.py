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

# 이미지 분석용 추가 라이브러리
import torchvision.transforms as transforms
from torchvision import models
from PIL import Image
import io

# JSON 직렬화를 위한 커스텀 인코더 클래스 추가
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

# SSADAGUCrawler 클래스 (기존 코드 그대로)
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

    def crawl_search_results(self, keyword, max_products=20):
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
            product_data = self.crawl_product_detail(link, include_images=True)
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

# AI 모델을 활용한 유사도 분석 함수 (기존 코드)
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

# 2단계 검증 분석기 (텍스트 + 이미지)
class DualVerificationAnalyzer(SimilarityAnalyzer):
    """텍스트 + 이미지 2단계 검증 분석기"""
    
    def __init__(self):
        # 기존 텍스트 유사도 초기화
        super().__init__()
        
        # 이미지 분석 모델 추가
        self.setup_image_analyzer()
        
    def setup_image_analyzer(self):
        """이미지 분석 모델 초기화"""
        try:
            print("이미지 분석 모델 로딩 중...")
            self.image_model = models.resnet50(pretrained=True)
            self.image_model.eval()
            
            # 마지막 분류층 제거 (특성 벡터만 추출)
            self.image_model = torch.nn.Sequential(*list(self.image_model.children())[:-1])
            
            # 이미지 전처리 파이프라인
            self.transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            ])
            
            print("✓ 이미지 분석 모델 로딩 완료")
            
        except Exception as e:
            print(f"✗ 이미지 분석 모델 로딩 실패: {e}")
            self.image_model = None
    
    def search_naver_images(self, keyword, num_images=3):
        """네이버에서 키워드 이미지 검색"""
        print(f"  네이버 이미지 검색 시도: {keyword}")
        encoded_keyword = urllib.parse.quote(keyword)
        naver_url = f"https://search.naver.com/search.naver?where=image&query={encoded_keyword}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        try:
            response = requests.get(naver_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            image_urls = []
            
            # 다양한 이미지 셀렉터 시도
            selectors = [
                'img._img',
                'img[class*="img"]',
                'img[src*="pstatic"]',
                'img[data-src*="pstatic"]'
            ]
            
            for selector in selectors:
                img_elements = soup.select(selector)
                print(f"  셀렉터 '{selector}'로 {len(img_elements)}개 이미지 발견")
                
                for img in img_elements[:num_images]:
                    img_src = img.get('src') or img.get('data-src')
                    if img_src and img_src.startswith('http'):
                        image_urls.append(img_src)
                        print(f"    이미지 URL 추가: {img_src[:50]}...")
                        
                if image_urls:
                    break
                    
            # 중복 제거
            image_urls = list(set(image_urls))[:num_images]
            print(f"  최종 수집된 이미지: {len(image_urls)}개")
            return image_urls
            
        except Exception as e:
            print(f"  네이버 이미지 검색 실패: {e}")
            return []
    
    def download_and_process_image(self, image_url):
        """이미지 다운로드 및 전처리"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.google.com/'
            }
            
            print(f"    이미지 다운로드 시도: {image_url[:50]}...")
            response = requests.get(image_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            print(f"    응답 크기: {len(response.content)} bytes")
            image = Image.open(io.BytesIO(response.content)).convert('RGB')
            print(f"    이미지 크기: {image.size}")
            
            image_tensor = self.transform(image).unsqueeze(0)
            print(f"    텐서 형태: {image_tensor.shape}")
            
            return image_tensor
            
        except Exception as e:
            print(f"    이미지 처리 실패: {e}")
            return None
    
    def extract_image_features(self, image_tensor):
        """이미지에서 특성 벡터 추출"""
        if self.image_model is None:
            return None
            
        try:
            with torch.no_grad():
                features = self.image_model(image_tensor)
                features = features.view(features.size(0), -1)
                return features.numpy()
        except Exception as e:
            return None
    
    def get_reference_features(self, keyword):
        """네이버 검색 이미지들의 평균 특성 벡터 계산"""
        if self.image_model is None:
            print("  이미지 모델이 없음")
            return None
            
        naver_images = self.search_naver_images(keyword, num_images=3)
        
        if not naver_images:
            print("  네이버 이미지 수집 실패")
            return None
            
        reference_features = []
        
        for i, img_url in enumerate(naver_images):
            print(f"  참조 이미지 {i+1}/{len(naver_images)} 처리 중...")
            image_tensor = self.download_and_process_image(img_url)
            if image_tensor is not None:
                features = self.extract_image_features(image_tensor)
                if features is not None:
                    reference_features.append(features)
                    print(f"    특성 추출 성공: {features.shape}")
                else:
                    print(f"    특성 추출 실패")
            else:
                print(f"    이미지 다운로드 실패")
                    
        if reference_features:
            avg_features = np.mean(reference_features, axis=0)
            print(f"  최종 평균 특성: {avg_features.shape}, 성공한 이미지: {len(reference_features)}개")
            return avg_features
        else:
            print("  모든 참조 이미지 처리 실패")
            return None

# 2단계 검증 크롤러 (기존 코드 기반)
class DualVerificationCrawler(SSADAGUCrawler):
    """2단계 검증 크롤러 (기존 코드 기반)"""
    
    def __init__(self, use_selenium=True):
        super().__init__(use_selenium)
        
    def extract_product_image_urls(self, soup):
        """상품 페이지에서 이미지 URL 추출"""
        image_urls = []
        
        # 기존 extract_product_images 메서드 활용
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
                image_urls.append(src)
                
        return image_urls[:2]  # 처음 2개만
    
    def calculate_image_similarity_for_product(self, analyzer, reference_features, product_url):
        """특정 상품의 이미지 유사도 계산"""
        if reference_features is None:
            print("    참조 특성 없음")
            return 0.0
            
        if analyzer.image_model is None:
            print("    이미지 모델 없음")
            return 0.0
            
        try:
            # 상품 페이지 로딩
            if self.use_selenium:
                self.driver.get(product_url)
                time.sleep(2)
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            else:
                response = requests.get(product_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
            
            # 상품 이미지 URL 추출
            product_image_urls = self.extract_product_image_urls(soup)
            print(f"    상품 이미지 {len(product_image_urls)}개 발견")
            
            if not product_image_urls:
                print("    상품 이미지 없음")
                return 0.0
                
            product_features = []
            
            for i, img_url in enumerate(product_image_urls):
                print(f"    상품 이미지 {i+1}/{len(product_image_urls)} 처리 중...")
                image_tensor = analyzer.download_and_process_image(img_url)
                if image_tensor is not None:
                    features = analyzer.extract_image_features(image_tensor)
                    if features is not None:
                        product_features.append(features)
                        print(f"      특성 추출 성공")
                    else:
                        print(f"      특성 추출 실패")
                else:
                    print(f"      이미지 다운로드 실패")
                        
            if not product_features:
                print("    모든 상품 이미지 처리 실패")
                return 0.0
                
            # 상품 이미지들의 평균 특성
            avg_product_features = np.mean(product_features, axis=0)
            
            # 코사인 유사도 계산
            similarity = cosine_similarity(
                reference_features.reshape(1, -1), 
                avg_product_features.reshape(1, -1)
            )[0][0]
            
            print(f"    유사도 계산 완료: {similarity:.4f}")
            return max(0.0, similarity)
            
        except Exception as e:
            print(f"    이미지 유사도 계산 실패: {e}")
            return 0.0

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

# 설치 함수 및 네이버 데이터랩 함수 (기존 코드)
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
            "protobuf",
            "torchvision",
            "pillow"
        ]
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + packages)
        print("라이브러리가 성공적으로 준비되었습니다.")
    except subprocess.CalledProcessError as e:
        print(f"라이브러리 설치 중 오류 발생: {e}")
        print("스크립트를 실행하려면 다음 명령어를 터미널에서 직접 실행해주세요:")
        print("pip install beautifulsoup4 requests selenium torch transformers numpy scikit-learn protobuf torchvision pillow")
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

# 기존 main_merged 함수 (fallback용)
def main_merged():
    install_packages()
    print("\n=== SSADAGU 통합 크롤러 ===")

    crawler = SSADAGUCrawler(use_selenium=True)
    analyzer = SimilarityAnalyzer()

    SIMILARITY_THRESHOLD = 0.7
    MAX_RETRY = 5

    best_match_product = None
    best_match_url = None
    max_similarity = 0.0

    for attempt in range(MAX_RETRY):
        category_name = random.choice(list(TOP_LEVEL_CATEGORIES.keys()))
        category_id = TOP_LEVEL_CATEGORIES[category_name]
        trending_keywords = search_naver_rank(category_id)

        keyword = random.choice(trending_keywords) if trending_keywords else "악세사리"
        print(f"\n[{attempt+1}/{MAX_RETRY}] 선택된 카테고리: {category_name}, 키워드: {keyword}")

        search_results_urls = (
            crawler.search_products_selenium(keyword)
            if crawler.use_selenium
            else crawler.search_products_requests(keyword)
        )

        if not search_results_urls:
            print("검색 결과 없음 → 다음 키워드로 재시도")
            continue

        try:
            keyword_embedding = analyzer.get_embedding(keyword)
            temp_best_url = None
            temp_max_sim = 0.0

            for i, url in enumerate(search_results_urls[:20]):
                basic_data = crawler.crawl_product_basic(url)
                if not basic_data:
                    continue
                if basic_data['title'] == "제목 없음":
                    print("제목 없음 → 스킵")
                    continue

                title_embedding = analyzer.get_embedding(basic_data['title'])
                similarity = cosine_similarity(keyword_embedding, title_embedding)[0][0]
                print(f"상품 {i+1}: {basic_data['title'][:30]} | 유사도: {similarity:.4f}")

                if similarity > temp_max_sim:
                    temp_max_sim = similarity
                    temp_best_url = url

            if temp_max_sim >= SIMILARITY_THRESHOLD:
                best_match_url = temp_best_url
                max_similarity = temp_max_sim
                break
            else:
                print(f"유사도 {temp_max_sim:.4f} → 기준 미달, 다음 키워드로 재시도")

        except Exception as e:
            print(f"유사도 분석 오류: {e}")
            continue

    if best_match_url:
        best_match_product = crawler.crawl_product_detail(best_match_url, include_images=True)
        if best_match_product:
            print(f"\n최종 상품: {best_match_product['title']}")
            print(f"가격: {best_match_product['price']}원 | 유사도: {max_similarity:.4f}")

            output_filename = f"ssadagu_best_match_{int(time.time())}.json"
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump([best_match_product], f, ensure_ascii=False, indent=2)
            print(f"결과 저장 완료: {output_filename}")
        else:
            print("최종 상품 상세 정보를 가져오지 못함")
    else:
        print("추천할 상품을 찾지 못했습니다.")

    return best_match_product

# 2단계 검증 메인 함수 (기존 구조 유지)
def main_dual_verification():
    """2단계 검증 메인 함수 (기존 구조 유지)"""
    install_packages()
    print("\n=== SSADAGU 2단계 검증 크롤러 ===")

    crawler = DualVerificationCrawler(use_selenium=True)
    analyzer = DualVerificationAnalyzer()

    TEXT_SIMILARITY_THRESHOLD = 0.6   
    IMAGE_SIMILARITY_THRESHOLD = 0.25 
    MAX_RETRY = 5

    best_match_product = None
    best_match_url = None
    max_combined_score = 0.0

    for attempt in range(MAX_RETRY):
        category_name = random.choice(list(TOP_LEVEL_CATEGORIES.keys()))
        category_id = TOP_LEVEL_CATEGORIES[category_name]
        trending_keywords = search_naver_rank(category_id)

        keyword = random.choice(trending_keywords) if trending_keywords else "악세사리"
        print(f"\n[{attempt+1}/{MAX_RETRY}] 선택된 카테고리: {category_name}, 키워드: {keyword}")

        # 네이버 참조 이미지 특성 추출
        print("네이버 참조 이미지 분석 중...")
        reference_features = analyzer.get_reference_features(keyword)
        
        if reference_features is not None:
            print("✓ 네이버 참조 이미지 특성 추출 완료")
        else:
            print("✗ 네이버 참조 이미지 특성 추출 실패 → 텍스트만 사용")

        # 검색
        search_results_urls = (
            crawler.search_products_selenium(keyword)
            if crawler.use_selenium
            else crawler.search_products_requests(keyword)
        )

        if not search_results_urls:
            print("검색 결과 없음 → 다음 키워드로 재시도")
            continue

        try:
            keyword_embedding = analyzer.get_embedding(keyword)
            temp_best_url = None
            temp_max_score = 0.0

            for i, url in enumerate(search_results_urls[:15]):
                basic_data = crawler.crawl_product_basic(url)
                if not basic_data or basic_data['title'] == "제목 없음":
                    continue

                # 1단계: 텍스트 유사도 검증
                title_embedding = analyzer.get_embedding(basic_data['title'])
                text_similarity = cosine_similarity(keyword_embedding, title_embedding)[0][0]
                
                print(f"상품 {i+1}: {basic_data['title'][:30]} | 텍스트 유사도: {text_similarity:.4f}")

                # 텍스트 유사도 1단계 통과 체크
                if text_similarity >= TEXT_SIMILARITY_THRESHOLD:
                    print("  ✓ 1단계(텍스트) 통과 → 2단계(이미지) 검증 중...")
                    
                    # 2단계: 이미지 유사도 검증
                    image_similarity = crawler.calculate_image_similarity_for_product(
                        analyzer, reference_features, url
                    )
                    
                    print(f"  이미지 유사도: {image_similarity:.4f}")
                    
                    if image_similarity >= IMAGE_SIMILARITY_THRESHOLD:
                        # 종합 점수 계산 (텍스트 60% + 이미지 40%)
                        combined_score = (text_similarity * 0.6) + (image_similarity * 0.4)
                        print(f"  ✓ 2단계(이미지) 통과! 종합점수: {combined_score:.4f}")
                        
                        if combined_score > temp_max_score:
                            temp_max_score = combined_score
                            temp_best_url = url
                    else:
                        print(f"  ✗ 2단계(이미지) 실패 (< {IMAGE_SIMILARITY_THRESHOLD})")
                else:
                    print(f"  ✗ 1단계(텍스트) 실패 (< {TEXT_SIMILARITY_THRESHOLD})")

            # 2단계 모두 통과한 상품이 있는지 확인
            if temp_best_url and temp_max_score > max_combined_score:
                best_match_url = temp_best_url
                max_combined_score = temp_max_score
                print(f"\n🎯 2단계 검증 통과! 종합점수: {max_combined_score:.4f}")
                break
            else:
                print(f"2단계 검증 통과 상품 없음 → 다음 키워드로 재시도")

        except Exception as e:
            print(f"검증 과정 오류: {e}")
            continue

    # 최종 상품 크롤링
    if best_match_url:
        print(f"\n=== 최종 선택된 상품 상세 크롤링 ===")
        best_match_product = crawler.crawl_product_detail(best_match_url, include_images=True)
        if best_match_product:
            # ⭐ 핵심 수정: float32를 일반 float로 변환
            best_match_product['text_image_combined_score'] = float(max_combined_score)
            
            print(f"\n🎉 2단계 검증 완료!")
            print(f"제목: {best_match_product['title']}")
            print(f"가격: {best_match_product['price']}원")
            print(f"종합점수: {max_combined_score:.4f}")

            output_filename = f"dual_verification_result_{int(time.time())}.json"
            
            # ⭐ 핵심 수정: NumpyEncoder 사용
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(best_match_product, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)
            print(f"결과 저장 완료: {output_filename}")
            
            return best_match_product
        else:
            print("최종 상품 상세 정보 크롤링 실패")
    else:
        print("\n😞 2단계 검증을 통과한 상품을 찾지 못했습니다.")
        
        # 실패시 기존 방식으로 대체
        print("기존 방식(텍스트만)으로 대체 시도...")
        fallback_result = main_merged()
        return fallback_result

    return best_match_product

# --- 메인 실행 ---
if __name__ == "__main__":
    main_dual_verification()