import requests
import pandas as pd
import time
import os
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import re
import json

class FinalImageCrawler:
    def __init__(self):
        self.setup_driver()
    
    def setup_driver(self):
        """드라이버 설정"""
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 15)
    
    def get_place_id_from_search(self, facility_name):
        """검색 결과에서 place ID 추출"""
        try:
            encoded_name = urllib.parse.quote(facility_name)
            search_url = f"https://map.naver.com/p/search/{encoded_name}"
            print(f"🔍 검색 URL: {search_url}")
            
            self.driver.get(search_url)
            time.sleep(5)
            
            # 현재 URL에서 place ID 추출 시도
            current_url = self.driver.current_url
            place_id_match = re.search(r'/place/(\d+)', current_url)
            
            if place_id_match:
                place_id = place_id_match.group(1)
                print(f"✅ Place ID 찾음: {place_id}")
                return place_id
            
            print("❌ Place ID를 찾을 수 없음")
            return None
            
        except Exception as e:
            print(f"🔴 Place ID 추출 오류: {e}")
            return None
    
    def extract_real_images_from_place(self, place_id):
        """Place 상세 페이지에서 실제 시설 사진 추출 - 강화된 버전"""
        try:
            # 상세 페이지 URL (여러 가지 URL 시도)
            detail_urls = [
                f"https://m.place.naver.com/place/{place_id}/photo",
                f"https://m.place.naver.com/place/{place_id}/home",
                f"https://m.place.naver.com/place/{place_id}",
                f"https://place.naver.com/place/{place_id}/photo"
            ]
            
            for detail_url in detail_urls:
                print(f"📸 상세 페이지 접속 시도: {detail_url}")
                self.driver.get(detail_url)
                time.sleep(5)
                
                # 페이지 분석
                self.analyze_page_content()
                
                # 실제 사진 추출 시도
                image_url = self.find_real_photos()
                if image_url:
                    return image_url
            
            return None
            
        except Exception as e:
            print(f"🔴 실제 사진 추출 오류: {e}")
            return None
    
    def analyze_page_content(self):
        """페이지 내용 분석"""
        try:
            # 페이지 소스 분석
            page_source = self.driver.page_source
            
            # 사진 관련 키워드 확인
            photo_keywords = ['사진', 'photo', 'image', 'gallery', '리뷰사진']
            found_keywords = [kw for kw in photo_keywords if kw in page_source]
            if found_keywords:
                print(f"✅ 페이지 내 사진 관련 키워드 발견: {found_keywords}")
            
            # 모든 이미지 태그 분석
            images = self.driver.find_elements(By.TAG_NAME, "img")
            print(f"📸 페이지 내 이미지 태그 수: {len(images)}")
            
            # 이미지 URL들 출력 (상위 10개)
            for i, img in enumerate(images[:10]):
                src = img.get_attribute('src') or img.get_attribute('data-src') or img.get_attribute('data-original')
                if src:
                    print(f"  이미지 {i+1}: {src[:100]}...")
                    # 실제 사진인지 확인
                    if self.is_real_facility_photo(src):
                        print(f"    ✅ 실제 시설 사진으로 판단!")
            
            # 페이지 구조 분석
            container_selectors = [
                "div.photo_area", "div._2y6cI", "div._section", 
                "div.photo_list", "ul._3W4A1", "div._3uDEe",
                "div.Y5ZjY", "div.zDcC3", "div._3ocDE"
            ]
            
            for selector in container_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"✅ 컨테이너 발견: {selector} - {len(elements)}개")
            
            return True
            
        except Exception as e:
            print(f"🔴 페이지 분석 오류: {e}")
            return False
    
    def find_real_photos(self):
        """실제 사진 찾기 - 다양한 방법 시도"""
        try:
            print("🔄 실제 사진 찾기 시도...")
            
            # 방법 1: 다양한 이미지 선택자 시도
            image_url = self.try_image_selectors()
            if image_url:
                return image_url
            
            # 방법 2: data-src 속성에서 찾기 (lazy loading)
            image_url = self.try_data_attributes()
            if image_url:
                return image_url
            
            # 방법 3: 배경 이미지에서 찾기
            image_url = self.try_background_images()
            if image_url:
                return image_url
            
            # 방법 4: JavaScript로 숨겨진 이미지 찾기
            image_url = self.try_javascript_extraction()
            if image_url:
                return image_url
            
            return None
            
        except Exception as e:
            print(f"🔴 사진 찾기 오류: {e}")
            return None
    
    def try_image_selectors(self):
        """다양한 이미지 선택자로 사진 찾기"""
        photo_selectors = [
            # 네이버 플레이스 공식 선택자들
            "img.Y6Ccc",  # 사진 이미지
            "img._3y6cI", 
            "img._3lmHh",
            "img._3ocDE",
            "img._27qo_",
            "img.place_thumb",
            "div.photo_area img",
            "div._2y6cI img",
            "div._section img",
            "div.photo_list img",
            "ul._3W4A1 img",
            "div._3uDEe img",
            "a._3lmHh img",
            "div.Y5ZjY img",
            "div.zDcC3 img",
            # 일반적인 사진 선택자
            "img[src*='photo']",
            "img[src*='image']",
            "img[src*='upload']",
            "img[src*='thum']",
            "img[src*='blog']"
        ]
        
        for selector in photo_selectors:
            try:
                images = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for img in images:
                    src = img.get_attribute('src')
                    if src and self.is_real_facility_photo(src):
                        print(f"✅ 선택자로 실제 사진 발견: {selector}")
                        print(f"   이미지 URL: {src[:100]}...")
                        return src
            except:
                continue
        
        return None
    
    def try_data_attributes(self):
        """data-src 등 데이터 속성에서 이미지 찾기"""
        try:
            # data-src 속성이 있는 이미지 찾기
            images_with_data = self.driver.find_elements(By.CSS_SELECTOR, "img[data-src]")
            for img in images_with_data:
                src = img.get_attribute('data-src')
                if src and self.is_real_facility_photo(src):
                    print(f"✅ data-src에서 실제 사진 발견")
                    print(f"   이미지 URL: {src[:100]}...")
                    return src
            
            # data-original 속성도 확인
            images_with_original = self.driver.find_elements(By.CSS_SELECTOR, "img[data-original]")
            for img in images_with_original:
                src = img.get_attribute('data-original')
                if src and self.is_real_facility_photo(src):
                    print(f"✅ data-original에서 실제 사진 발견")
                    print(f"   이미지 URL: {src[:100]}...")
                    return src
            
            return None
        except:
            return None
    
    def try_background_images(self):
        """CSS 배경 이미지에서 찾기"""
        try:
            # 배경 이미지를 사용하는 요소 찾기
            elements_with_bg = self.driver.find_elements(By.CSS_SELECTOR, "[style*='background-image']")
            for element in elements_with_bg:
                style = element.get_attribute('style')
                bg_match = re.search(r'background-image:\s*url\(([^)]+)\)', style)
                if bg_match:
                    bg_url = bg_match.group(1).strip('"\'').replace('\\', '')
                    if bg_url and self.is_real_facility_photo(bg_url):
                        print(f"✅ 배경 이미지에서 실제 사진 발견")
                        print(f"   이미지 URL: {bg_url[:100]}...")
                        return bg_url
            return None
        except:
            return None
    
    def try_javascript_extraction(self):
        """JavaScript로 이미지 URL 추출"""
        try:
            # 페이지의 모든 이미지 URL을 JavaScript로 수집
            js_script = """
            var images = document.querySelectorAll('img');
            var imageUrls = [];
            for (var i = 0; i < images.length; i++) {
                var src = images[i].src || images[i].getAttribute('data-src') || images[i].getAttribute('data-original');
                if (src && src.startsWith('http')) {
                    imageUrls.push(src);
                }
            }
            
            // 배경 이미지도 수집
            var elements = document.querySelectorAll('[style*="background-image"]');
            for (var i = 0; i < elements.length; i++) {
                var style = elements[i].getAttribute('style');
                var match = style.match(/background-image:\\s*url\\(['"]?([^'")]+)['"]?\\)/);
                if (match && match[1]) {
                    imageUrls.push(match[1]);
                }
            }
            return imageUrls;
            """
            
            all_image_urls = self.driver.execute_script(js_script)
            if all_image_urls:
                for img_url in all_image_urls:
                    if self.is_real_facility_photo(img_url):
                        print(f"✅ JavaScript로 실제 사진 발견")
                        print(f"   이미지 URL: {img_url[:100]}...")
                        return img_url
            
            return None
        except:
            return None
    
    def is_real_facility_photo(self, img_url):
        """실제 시설 사진인지 확인 - 강화된 필터링"""
        if not img_url:
            return False
            
        img_url_lower = img_url.lower()
        
        # 무시할 패턴 (아이콘, 로고, 마커 등)
        ignore_patterns = [
            'npay', 'promo', 'banner',
            'gstatic', 'al-icon',
            'logo', 'icon',
            'spi', 'ad',
            'btn', 'button',
            'nav', 'menu',
            'mobile', 'm_',
            'pcweb', 'web',
            'static/common',
            'bar/', 'gnb/',
            'svg', 'ico',
            'marker',  # 지도 마커
            'category',  # 카테고리 아이콘
            'around-category',  # 주변 카테고리
            'selected-marker',  # 선택된 마커
            'mantle',  # 맨틀
            'data:image',  # base64 데이터
            'transparent',  # 투명 이미지
            'pixel',  # 픽셀 이미지
            'spacer',  # 여백 이미지
            'loading',  # 로딩 이미지
            'placeholder'  # 플레이스홀더
        ]
        
        for pattern in ignore_patterns:
            if pattern in img_url_lower:
                return False
        
        # 실제 사진 패턴 (강화됨)
        photo_patterns = [
            'photo', 'image', 'img',
            'upload', 'thum',
            'blogfiles', 'postfiles',
            'phinf', 'pstatic',
            'navercdn',  # 네이버 CDN
            'placeimg',  # 장소 이미지
            'store',  # 매장 이미지
            'review',  # 리뷰 이미지
            'visit',  # 방문 이미지
            'contents'  # 콘텐츠 이미지
        ]
        
        for pattern in photo_patterns:
            if pattern in img_url_lower:
                return True
        
        # 실제 사진의 일반적인 특성
        is_likely_photo = (
            any(ext in img_url_lower for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']) and
            'http' in img_url_lower and
            len(img_url) > 50  # 실제 사진 URL은 일반적으로 길다
        )
        
        return is_likely_photo
    
    def search_real_facility_images(self, facility_name):
        """실제 시설 사진 검색 메인 함수"""
        print(f"\n🎯 시설 검색: {facility_name}")
        
        # 1. Place ID 추출
        place_id = self.get_place_id_from_search(facility_name)
        if not place_id:
            print("❌ Place ID를 찾을 수 없음")
            return None
        
        # 2. 실제 사진 추출
        image_url = self.extract_real_images_from_place(place_id)
        
        if image_url:
            print(f"🎊 최종 성공: {image_url}")
        else:
            print("❌ 실제 시설 사진을 찾을 수 없음")
            # 디버깅을 위한 스크린샷
            self.driver.save_screenshot(f"debug_{facility_name}_final.png")
            print(f"📸 최종 디버그 스크린샷 저장: debug_{facility_name}_final.png")
        
        return image_url

    def crawl_from_csv(self, csv_file_path, output_file="final_results.xlsx", start_index=0):
        """CSV 파일에서 시설명을 읽어 이미지 수집"""
        try:
            # CSV 파일 읽기
            print("📁 CSV 파일 읽는 중...")
            df = pd.read_csv(csv_file_path, encoding='cp949')
            
            # A열(시설명) 추출 - 2행부터 (1행은 헤더라고 가정)
            facilities = df.iloc[1:, 0].tolist()  # A열은 0번 인덱스
            facilities = [str(f) for f in facilities if pd.notna(f)]
            
            print(f"📊 총 {len(facilities)}개 시설 발견")
            
            # 기존 결과 파일이 있으면 이어서 진행
            existing_results = []
            if os.path.exists(output_file):
                existing_df = pd.read_excel(output_file)
                existing_results = existing_df.to_dict('records')
                print(f"📁 기존 결과 파일 발견: {len(existing_results)}개 진행됨")
            
            results = existing_results
            
            for i, facility in enumerate(facilities[start_index:], start_index + 1):
                print(f"\n{'='*60}")
                print(f"🏥 처리 중 ({i}/{len(facilities)}): {facility}")
                
                # 이미 처리된 시설은 건너뛰기
                if any(r['시설명'] == facility for r in results):
                    print("⏭️ 이미 처리된 시설, 건너뜀")
                    continue
                
                image_url = self.search_real_facility_images(facility)
                
                results.append({
                    "시설명": facility, 
                    "이미지_URL": image_url
                })
                
                # 10개마다 중간 저장
                if i % 10 == 0:
                    self.save_progress(results, output_file)
                    print(f"💾 중간 저장 완료: {i}개 처리")
                
                # 요청 간격
                time.sleep(2)
            
            # 최종 저장
            self.save_progress(results, output_file)
            print(f"🎉 모든 처리 완료! 총 {len(results)}개 시설 처리됨")
            
            # 통계 출력
            successful = sum(1 for r in results if r['이미지_URL'] is not None)
            print(f"📊 최종 성공률: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
            
            return results
            
        except Exception as e:
            print(f"🔴 CSV 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            return []

    def save_progress(self, results, output_file):
        """진행 상황 저장"""
        df = pd.DataFrame(results)
        df.to_excel(output_file, index=False)
    
    def close(self):
        """드라이버 종료"""
        if self.driver:
            self.driver.quit()

# 메인 실행 함수
def main():
    crawler = FinalImageCrawler()
    
    try:
        # CSV 파일 경로
        csv_file = "Animallo-vb1.csv"  # 실제 파일명으로 변경해주세요
        
        if not os.path.exists(csv_file):
            print(f"❌ CSV 파일을 찾을 수 없습니다: {csv_file}")
            return
        
        # 시작 인덱스 (중간에 끊겼을 경우 이어서 시작)
        start_index = 0
        
        # 전체 크롤링 실행
        results = crawler.crawl_from_csv(
            csv_file_path=csv_file,
            output_file="final_facility_images.xlsx",
            start_index=start_index
        )
        
        print("\n🎊 프로그램 완료!")
        
    except Exception as e:
        print(f"🔴 프로그램 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        crawler.close()

if __name__ == "__main__":
    main()