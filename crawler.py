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
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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
        chrome_options.add_argument('--headless')  # 헤드리스 모드
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
            time.sleep(3)  # 페이지 로딩 대기
            
            # 상품 링크들 찾기
            product_links = []
            
            # 다양한 셀렉터 시도
            selectors = [
                "a[href*='view.php'][href*='platform=1688']",
                "a[href*='view.php'][href*='num_iid']",
                "a[href*='view.php']",
                ".product-item a",
                ".goods-item a",
                ".item-link"
            ]
            
            for selector in selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for element in elements:
                        href = element.get_attribute('href')
                        if href and 'view.php' in href:
                            product_links.append(href)
                    break
            
            # 중복 제거
            product_links = list(set(product_links))
            print(f"Selenium으로 발견한 상품 링크: {len(product_links)}개")
            
            return product_links[:10]
            
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
            
            # HTML 내용 일부 출력 (디버깅용)
            print("페이지 내용 일부:")
            print(str(soup)[:500] + "...")
            
            # 상품 링크들 추출
            product_links = []
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link['href']
                if 'view.php' in href and ('platform=1688' in href or 'num_iid' in href):
                    full_url = f"{self.base_url}{href}" if href.startswith('/') else href
                    product_links.append(full_url)
            
            print(f"requests로 발견한 상품 링크: {len(product_links)}개")
            return product_links[:10]
            
        except Exception as e:
            print(f"requests 검색 오류: {e}")
            return []
    
    def calculate_rating(self, soup):
        """별점 계산 (별=1, 반별=0.5, 빈별=0)"""
        rating = 0.0
        
        # 별 컨테이너 찾기
        star_containers = [
            soup.find('a', class_='start'),
            soup.find('div', class_=re.compile(r'star|rating')),
            soup.find('a', href='#reviews_wrap')
        ]
        
        for container in star_containers:
            if container:
                # 별 이미지들 찾기
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
        
        # skubox에서 옵션 추출
        sku_list = soup.find('ul', {'id': 'skubox'})
        if sku_list:
            option_items = sku_list.find_all('li', class_=re.compile(r'imgWrapper'))
            
            for item in option_items:
                # title 속성에서 옵션명 추출
                title_element = item.find('a', title=True)
                if title_element:
                    option_name = title_element.get('title', '').strip()
                    
                    # 재고 정보 추출 - 텍스트에서 직접 찾기
                    stock = 0
                    item_text = item.get_text()
                    stock_match = re.search(r'재고\s*:\s*(\d+)', item_text)
                    if stock_match:
                        stock = int(stock_match.group(1))
                    
                    # 이미지 URL 추출
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
        
        # img_translate_숫자 패턴으로 이미지 찾기
        img_elements = soup.find_all('img', {'id': re.compile(r'img_translate_\d+')})
        
        for img in img_elements:
            src = img.get('src', '')
            if src:
                # URL 정규화
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
        
        # pro-info-item 클래스에서 정보 찾기
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
        time.sleep(3)  # 페이지 로딩 대기
        
        # BeautifulSoup으로 파싱
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
        # 1. 상품명 추출
        title_element = soup.find('h1', {'id': 'kakaotitle'})
        title = title_element.get_text(strip=True) if title_element else "제목 없음"
        
        # 제목이 없으면 다른 방법으로 시도
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
        
        # 2. 가격 추출
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
        
        # 3. 별점 추출
        rating = self.calculate_rating(soup)
        
        # 4. 상품 옵션들 추출
        options = self.extract_product_options(soup)
        
        # 5. 재료 정보 추출
        material_info = self.extract_material_info(soup)
        
        # 6. 상품 이미지들 추출
        product_images = self.extract_product_images(soup)
        
        product_data = {
            'url': product_url,
            'title': title,
            'price': price,
            'rating': rating,
            'options': options,
            'material_info': material_info,
            'product_images': product_images,
            'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return product_data
    
    def get_manual_test_urls(self):
        """수동으로 테스트할 상품 URL들"""
        return [
            "https://ssadagu.kr/shop/view.php?platform=1688&num_iid=840606222752&ss_tx=%EC%95%85%EC%84%B8%EC%82%AC%EB%A6%AC",
            # 추가 테스트 URL이 있으면 여기에 추가
        ]
    
    def crawl_search_results(self, keyword, max_products=5):
        """검색 결과에서 상품들 크롤링"""
        print(f"'{keyword}' 검색 시작...")
        
        # 검색 결과 가져오기
        if self.use_selenium:
            product_links = self.search_products_selenium(keyword)
        else:
            product_links = self.search_products_requests(keyword)
        
        # 검색 결과가 없으면 수동 테스트 URL 사용
        if not product_links:
            print("검색 결과를 찾을 수 없어 테스트 URL을 사용합니다.")
            product_links = self.get_manual_test_urls()
        
        print(f"{len(product_links)}개의 상품 링크를 처리합니다.")
        
        # 각 상품 상세 정보 크롤링
        crawled_products = []
        for i, link in enumerate(product_links[:max_products]):
            print(f"\n상품 {i+1}/{min(len(product_links), max_products)} 크롤링 중...")
            
            product_data = self.crawl_product_detail(link)
            if product_data:
                crawled_products.append(product_data)
                print(f"✓ 크롤링 성공: {product_data['title'][:50]}...")
            else:
                print("✗ 크롤링 실패")
            
            # 요청 간 딜레이
            time.sleep(random.uniform(2, 4))
        
        return crawled_products
    
    def search_products_selenium(self, keyword):
        """Selenium을 사용한 상품 검색"""
        encoded_keyword = urllib.parse.quote(keyword)
        search_url = f"{self.base_url}/shop/search.php?ss_tx={encoded_keyword}"
        
        try:
            self.driver.get(search_url)
            time.sleep(5)  # 페이지 완전 로딩 대기
            
            # JavaScript가 실행된 후 상품 링크들 찾기
            product_links = []
            
            # 상품 링크 찾기 - 여러 패턴 시도
            link_elements = self.driver.find_elements(By.TAG_NAME, "a")
            
            for element in link_elements:
                href = element.get_attribute('href')
                if href and 'view.php' in href and ('platform=1688' in href or 'num_iid' in href):
                    product_links.append(href)
            
            return list(set(product_links))
            
        except Exception as e:
            print(f"Selenium 검색 오류: {e}")
            return []
    
    def search_products_requests(self, keyword):
        """requests를 사용한 상품 검색"""
        return []  # 이미 검색이 잘 안되므로 빈 리스트 반환
    
    def __del__(self):
        """소멸자 - Selenium 드라이버 종료"""
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
            except:
                pass

# 네이버 데이터랩 실시간 검색어 (실제로는 API 키 필요)
def get_random_trending_keyword():
    """실제 프로덕션에서는 네이버 데이터랩 API 사용"""
    sample_keywords = [
        "악세사리", "목걸이", "귀걸이", "반지", "팔찌", 
        "시계", "헤어핀", "브로치", "발찌", "목도리"
    ]
    return random.choice(sample_keywords)

def main():
    # Selenium 사용 여부 선택
    # use_selenium = input("Selenium을 사용하시겠습니까? (y/n, 기본값: y): ").strip().lower()
    # use_selenium = use_selenium != 'n'
    # crawler = SSADAGUCrawler(use_selenium=use_selenium)
    crawler = SSADAGUCrawler(use_selenium=True)
    
    print("=== SSADAGU 상품 크롤러 ===")
    print("1. 랜덤 트렌딩 키워드로 검색")
    print("2. 직접 키워드 입력")
    print("3. 테스트 URL로 직접 크롤링")
    
    choice = input("선택하세요 (1, 2, 또는 3): ").strip()
    
    if choice == "1":
        keyword = get_random_trending_keyword()
        print(f"선택된 트렌딩 키워드: {keyword}")
        products = crawler.crawl_search_results(keyword, max_products=1)
    elif choice == "3":
        # 테스트용 직접 크롤링
        test_urls = crawler.get_manual_test_urls()
        products = []
        for url in test_urls:
            print(f"테스트 URL 크롤링: {url}")
            product_data = crawler.crawl_product_detail(url)
            if product_data:
                products.append(product_data)
    else:
        keyword = input("검색 키워드를 입력하세요: ").strip()
        if not keyword:
            print("키워드를 입력해주세요.")
            return
        products = crawler.crawl_search_results(keyword, max_products=1)
    
    # 결과 출력
    print(f"\n=== 크롤링 결과: {len(products)}개 상품 ===")
    
    for i, product in enumerate(products, 1):
        if product:
            print(f"\n--- 상품 {i} ---")
            print(f"제목: {product['title']}")
            print(f"가격: {product['price']}원")
            print(f"별점: {product['rating']}/5.0")
            print(f"옵션 개수: {len(product['options'])}개")
            print(f"상품 이미지 개수: {len(product['product_images'])}개")
            
            if product['options']:
                print("옵션 목록 (5개):")
                for j, option in enumerate(product['options'][:5], 1):
                    print(f"  {j}. {option['name']} (재고: {option['stock']})")
            
            if product['material_info']:
                print("상품 정보:")
                for key, value in product['material_info'].items():
                    print(f"  {key}: {value}")
    
    # JSON 파일로 저장
    if products:
        keyword_for_filename = choice if choice == "3" else (keyword if 'keyword' in locals() else "test")
        output_filename = f"ssadagu_products_{keyword_for_filename}_{int(time.time())}.json"
        
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        
        print(f"\n결과가 '{output_filename}' 파일로 저장되었습니다.")
        
        # 간단한 통계
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
    main()