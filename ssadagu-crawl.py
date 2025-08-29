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

# --- 이미지 번역 기능에 대한 주석 추가 ---
def ocr_and_translate_image(image_url):
    """
    [안내] 이 함수는 가상의 OCR 및 번역 기능을 나타냅니다.
    실제 사용 시에는 Google Cloud Vision API, Azure Cognitive Services 등
    외부 OCR/번역 API를 사용하도록 이 함수를 수정해야 합니다.
    현재는 실제 번역이 아닌 가상의 텍스트만 반환합니다.
    """
    print(f"이미지 번역 시도: {image_url}")
    try:
        translated_text = "번역된 이미지 텍스트 예시입니다."
        print(f"✓ 번역 성공: '{translated_text[:20]}...'")
        return translated_text
    except Exception as e:
        print(f"✗ 이미지 번역 실패: {e}")
        return None

# --- SSADAGUCrawler 클래스 (crawler.py에서 가져옴) ---
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
        """Selenium WebDriver 설정"""
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

    def calculate_rating(self, soup):
        """별점 계산 (별=1, 반별=0.5, 빈별=0)"""
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
        """상품 옵션들 추출"""
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
        """상품 이미지들 추출"""
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
        """재료 및 상품 정보 추출"""
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

    def crawl_product_detail(self, product_url):
        """개별 상품 상세 정보 크롤링"""
        try:
            if self.use_selenium:
                return self.crawl_with_selenium(product_url)
            else:
                return self.crawl_with_requests(product_url)
        except Exception as e:
            print(f"상품 크롤링 오류 ({product_url}): {e}")
            return None

    def crawl_with_selenium(self, product_url):
        """Selenium으로 상품 정보 크롤링"""
        self.driver.get(product_url)
        time.sleep(3)
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        return self.extract_product_data(soup, product_url)

    def crawl_with_requests(self, product_url):
        """requests로 상품 정보 크롤링"""
        response = self.session.get(product_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        return self.extract_product_data(soup, product_url)

    def extract_product_data(self, soup, product_url):
        """soup 객체에서 상품 데이터 추출"""
        title_element = soup.find('h1', {'id': 'kakaotitle'})
        title = title_element.get_text(strip=True) if title_element else "제목 없음"
        if title == "제목 없음" or not title:
            alt_titles = [
                soup.find('h1'),
                soup.find('title'),
                soup.find('div', class_=re.compile(r'title|name'))
            ]
            for alt_title in alt_titles:
                if alt_title:
                    title = alt_title.get_text(strip=True)
                    if title and title != "제목 없음":
                        break
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
        product_images = self.extract_product_images(soup)

        translated_images = []
        for img_url in product_images:
            translated_text = ocr_and_translate_image(img_url)
            translated_images.append({
                'original_url': img_url,
                'translated_text': translated_text
            })

        product_data = {
            'url': product_url,
            'title': title,
            'price': price,
            'rating': rating,
            'options': options,
            'material_info': material_info,
            'product_images': translated_images,
            'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        return product_data

    def crawl_search_results(self, keyword, max_products=5):
        """검색 결과에서 상품들 크롤링"""
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
            product_data = self.crawl_product_detail(link)
            if product_data:
                crawled_products.append(product_data)
                print(f"✓ 크롤링 성공: {product_data['title'][:50]}...")
            else:
                print("✗ 크롤링 실패")
            time.sleep(random.uniform(2, 4))
        return crawled_products

    def __del__(self):
        """소멸자 - Selenium 드라이버 종료"""
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
            except:
                pass

def install_packages():
    """필요한 라이브러리를 설치합니다."""
    try:
        print("필수 라이브러리 (beautifulsoup4, requests, selenium) 설치를 시도합니다...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4", "requests", "selenium"])
        print("라이브러리가 성공적으로 준비되었습니다.")
    except subprocess.CalledProcessError as e:
        print(f"라이브러리 설치 중 오류 발생: {e}")
        print("스크립트를 실행하려면 'pip install beautifulsoup4 requests selenium' 명령어를 터미널에서 직접 실행해주세요.")
        sys.exit(1)

TOP_LEVEL_CATEGORIES = {
    "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002",
    "디지털/가전": "50000003", "가구/인테리어": "50000004", "출산/육아": "50000005",
    "식품": "50000006", "스포츠/레저": "50000007", "생활/건강": "50000008",
    "여가/생활편의": "50000009", "면세점": "50000010", "도서": "50005542"
}

def search_naver_rank(category_id):
    """네이버 데이터랩에서 카테고리별 인기 검색어 순위를 가져옵니다."""
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
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        try:
            data = response.json()
            for item in data.get('ranks', []):
                keywords.append(item.get('keyword'))
        except json.JSONDecodeError:
            print("JSON 데이터를 파싱하는 데 실패했습니다.")
    else:
        print(f"네이버 데이터랩에서 데이터를 가져오는 데 실패했습니다. 상태 코드: {response.status_code}")
    return keywords

# --- 수정된 메인 로직 ---
def main_merged():
    install_packages()

    print("\n=== SSADAGU 통합 크롤러 ===")
    
    # 네이버 데이터랩에서 랜덤 키워드 가져오기
    category_name = random.choice(list(TOP_LEVEL_CATEGORIES.keys()))
    category_id = TOP_LEVEL_CATEGORIES[category_name]
    print(f"🌟 랜덤으로 선택된 카테고리: '{category_name}'")
    trending_keywords = search_naver_rank(category_id)
    if not trending_keywords:
        print("네이버 데이터랩에서 인기 검색어를 가져오지 못했습니다. '악세사리'로 대체합니다.")
        keyword = "악세사리"
    else:
        keyword = random.choice(trending_keywords)
    print(f"🔍 선택된 검색 키워드: '{keyword}'")
    
    crawler = SSADAGUCrawler(use_selenium=True)
    products = crawler.crawl_search_results(keyword, max_products=1)

    print(f"\n=== 크롤링 결과: {len(products)}개 상품 ===")
    for i, product in enumerate(products, 1):
        if product:
            print(f"\n--- 상품 {i} ---")
            print(f"제목: {product['title']}")
            print(f"가격: {product['price']}원")
            print(f"별점: {product['rating']}/5.0")
            print(f"옵션 개수: {len(product['options'])}개")
            
            print("상품 이미지 (번역된 텍스트 포함):")
            for j, img_info in enumerate(product['product_images'], 1):
                print(f"  {j}. URL: {img_info['original_url']}")
                print(f"     번역 텍스트: {img_info['translated_text']}")
    
    if products:
        filename_keyword = keyword
        output_filename = f"ssadagu_products_{filename_keyword}_{int(time.time())}.json"
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        print(f"\n결과가 '{output_filename}' 파일로 저장되었습니다.")
        total_options = sum(len(p['options']) for p in products)
        total_images = sum(len(p['product_images']) for p in products)
        avg_rating = sum(p['rating'] for p in products) / len(products) if products else 0
        print(f"\n=== 크롤링 통계 ===")
        print(f"총 상품 수: {len(products)}개")
        print(f"총 옵션 수: {total_options}개")
        print(f"총 이미지 수: {total_images}개")
        print(f"평균 별점: {avg_rating:.2f}/5.0")
    else:
        print("\n크롤링된 상품이 없습니다.")

if __name__ == "__main__":
    main_merged()