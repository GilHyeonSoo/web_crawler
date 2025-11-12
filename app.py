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
        try:
            encoded_name = urllib.parse.quote(facility_name)
            search_url = f"https://map.naver.com/p/search/{encoded_name}"
            print(f"🔍 검색 URL: {search_url}")
            self.driver.get(search_url)
            time.sleep(2)
            current_url = self.driver.current_url
            place_id_match = re.search(r'/place/(\d+)', current_url)
            if place_id_match:
                place_id = place_id_match.group(1)
                print(f"✅ Place ID 찾음: {place_id}")
                return place_id
            try:
                self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "searchIframe")))
                time.sleep(1)
                list_items = self.driver.find_elements(By.CSS_SELECTOR, "li.VLTHu.OW9LQ")
                if list_items:
                    first_li = list_items[0]
                    # 내부 a태그(클릭용)
                    try:
                        link = first_li.find_element(By.CSS_SELECTOR, "a.place_bluelink")
                    except Exception:
                        # place_bluelink가 없으면 그냥 첫 번째 a 태그 클릭
                        link = first_li.find_element(By.TAG_NAME, "a")
                    ActionChains(self.driver).move_to_element(link).click(link).perform()
                    time.sleep(2)
                    self.driver.switch_to.default_content()
                    self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "entryIframe")))
                    time.sleep(1)
                    new_url = self.driver.current_url
                    place_id_match = re.search(r'place/(\d+)', new_url)
                    if place_id_match:
                        place_id = place_id_match.group(1)
                        print(f"✅ 목록에서 클릭 후 Place ID 획득: {place_id}")
                        return place_id
                    else:
                        print("❌ entryIframe에서 place ID를 다시 못 찾음")
                else:
                    print("❌ li.VLTHu.OW9LQ 목록 결과가 없음")
            except Exception as e3:
                print("❌ 목록 클릭/진입 에러:", e3)
            print("❌ Place ID를 찾을 수 없음")
            return None
        except Exception as e:
            print(f"🔴 Place ID 추출 오류: {e}")
            return None

    def extract_real_images_from_place(self, place_id):
        try:
            detail_urls = [
                f"https://m.place.naver.com/place/{place_id}/photo",
                f"https://m.place.naver.com/place/{place_id}/home",
                f"https://m.place.naver.com/place/{place_id}",
                f"https://place.naver.com/place/{place_id}/photo"
            ]
            for detail_url in detail_urls:
                print(f"📸 상세 페이지 접속 시도: {detail_url}")
                self.driver.get(detail_url)
                time.sleep(2)
                self.analyze_page_content()
                image_url = self.find_real_photos()
                if image_url:
                    return image_url
            return None
        except Exception as e:
            print(f"🔴 실제 사진 추출 오류: {e}")
            return None

    def analyze_page_content(self):
        try:
            page_source = self.driver.page_source
            photo_keywords = ['사진', 'photo', 'image', 'gallery', '리뷰사진']
            found_keywords = [kw for kw in photo_keywords if kw in page_source]
            if found_keywords:
                print(f"✅ 페이지 내 사진 관련 키워드 발견: {found_keywords}")
            images = self.driver.find_elements(By.TAG_NAME, "img")
            print(f"📸 페이지 내 이미지 태그 수: {len(images)}")
            for i, img in enumerate(images[:10]):
                src = img.get_attribute('src') or img.get_attribute('data-src') or img.get_attribute('data-original')
                if src:
                    print(f" 이미지 {i+1}: {src[:100]}...")
                if self.is_real_facility_photo(src):
                    print(f" ✅ 실제 시설 사진으로 판단!")
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
        try:
            print("🔄 실제 사진 찾기 시도...")
            image_url = self.try_image_selectors()
            if image_url:
                return image_url
            image_url = self.try_data_attributes()
            if image_url:
                return image_url
            image_url = self.try_background_images()
            if image_url:
                return image_url
            image_url = self.try_javascript_extraction()
            if image_url:
                return image_url
            return None
        except Exception as e:
            print(f"🔴 사진 찾기 오류: {e}")
            return None

    def try_image_selectors(self):
        photo_selectors = [
            "img.Y6Ccc", "img._3y6cI", "img._3lmHh", "img._3ocDE", "img._27qo_",
            "img.place_thumb", "div.photo_area img", "div._2y6cI img", "div._section img", "div.photo_list img",
            "ul._3W4A1 img", "div._3uDEe img", "a._3lmHh img", "div.Y5ZjY img", "div.zDcC3 img",
            "img[src*='photo']", "img[src*='image']", "img[src*='upload']", "img[src*='thum']", "img[src*='blog']"
        ]
        for selector in photo_selectors:
            try:
                images = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for img in images:
                    src = img.get_attribute('src')
                    if src and self.is_real_facility_photo(src):
                        print(f"✅ 선택자로 실제 사진 발견: {selector}")
                        print(f" 이미지 URL: {src[:100]}...")
                        return src
            except:
                continue
        return None

    def try_data_attributes(self):
        try:
            images_with_data = self.driver.find_elements(By.CSS_SELECTOR, "img[data-src]")
            for img in images_with_data:
                src = img.get_attribute('data-src')
                if src and self.is_real_facility_photo(src):
                    print(f"✅ data-src에서 실제 사진 발견")
                    print(f" 이미지 URL: {src[:100]}...")
                    return src
            images_with_original = self.driver.find_elements(By.CSS_SELECTOR, "img[data-original]")
            for img in images_with_original:
                src = img.get_attribute('data-original')
                if src and self.is_real_facility_photo(src):
                    print(f"✅ data-original에서 실제 사진 발견")
                    print(f" 이미지 URL: {src[:100]}...")
                    return src
            return None
        except:
            return None

    def try_background_images(self):
        try:
            elements_with_bg = self.driver.find_elements(By.CSS_SELECTOR, "[style*='background-image']")
            for element in elements_with_bg:
                style = element.get_attribute('style')
                bg_match = re.search(r'background-image:\s*url\(([^)]+)\)', style)
                if bg_match:
                    bg_url = bg_match.group(1).strip('"\'').replace('\\', '')
                    if bg_url and self.is_real_facility_photo(bg_url):
                        print(f"✅ 배경 이미지에서 실제 사진 발견")
                        print(f" 이미지 URL: {bg_url[:100]}...")
                        return bg_url
            return None
        except:
            return None

    def try_javascript_extraction(self):
        try:
            js_script = """
var images = document.querySelectorAll('img');
var imageUrls = [];
for (var i = 0; i < images.length; i++) {
var src = images[i].src || images[i].getAttribute('data-src') || images[i].getAttribute('data-original');
if (src && src.startsWith('http')) { imageUrls.push(src); }
}
var elements = document.querySelectorAll('[style*="background-image"]');
for (var i = 0; i < elements.length; i++) {
var style = elements[i].getAttribute('style');
var match = style.match(/background-image:\\s*url\\(['\"]?([^'\")]+)['\"]?\\)/);
if (match && match[1]) { imageUrls.push(match[1]); }
}
return imageUrls;
"""
            all_image_urls = self.driver.execute_script(js_script)
            if all_image_urls:
                for img_url in all_image_urls:
                    if self.is_real_facility_photo(img_url):
                        print(f"✅ JavaScript로 실제 사진 발견")
                        print(f" 이미지 URL: {img_url[:100]}...")
                        return img_url
            return None
        except:
            return None

    def is_real_facility_photo(self, img_url):
        if not img_url:
            return False
        img_url_lower = img_url.lower()
        ignore_patterns = [
            'npay', 'promo', 'banner', 'gstatic', 'al-icon', 'logo', 'icon', 'spi', 'ad','btn', 'button',
            'nav', 'menu', 'mobile', 'm_', 'pcweb', 'web', 'static/common', 'bar/', 'gnb/', 'svg', 'ico',
            'marker', 'category', 'around-category', 'selected-marker', 'mantle', 'data:image', 'transparent',
            'pixel', 'spacer', 'loading', 'placeholder'
        ]
        for pattern in ignore_patterns:
            if pattern in img_url_lower:
                return False
        photo_patterns = [
            'photo', 'image', 'img', 'upload', 'thum', 'blogfiles', 'postfiles', 'phinf', 'pstatic',
            'navercdn', 'placeimg', 'store', 'review', 'visit', 'contents'
        ]
        for pattern in photo_patterns:
            if pattern in img_url_lower:
                return True
        is_likely_photo = (
            any(ext in img_url_lower for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']) and
            'http' in img_url_lower and len(img_url) > 50
        )
        return is_likely_photo

    def search_real_facility_images(self, facility_name):
        print(f"\n🎯 시설 검색: {facility_name}")
        place_id = self.get_place_id_from_search(facility_name)
        if not place_id:
            print("❌ Place ID를 찾을 수 없음")
            return None
        image_url = self.extract_real_images_from_place(place_id)
        if image_url:
            print(f"🎊 최종 성공: {image_url}")
        else:
            print("❌ 실제 시설 사진을 찾을 수 없음")
        self.driver.save_screenshot(f"debug_{facility_name}_final.png")
        print(f"📸 최종 디버그 스크린샷 저장: debug_{facility_name}_final.png")
        return image_url

    def crawl_from_csv(self, csv_file_path, output_file="final_results.xlsx", start_index=0):
        try:
            print("📁 CSV 파일 읽는 중...")
            df = pd.read_csv(csv_file_path, encoding='cp949')
            facilities = df.iloc[1:, 0].tolist()
            ids = df.iloc[1:, 3].tolist()
            facilities = [str(f) for f in facilities if pd.notna(f)]
            ids = [i for i in ids if pd.notna(i)]
            print(f"📊 총 {len(facilities)}개 시설 발견")
            existing_results = []
            if os.path.exists(output_file):
                existing_df = pd.read_excel(output_file)
                existing_results = existing_df.to_dict('records')
                print(f"📁 기존 결과 파일 발견: {len(existing_results)}개 진행됨")
            results = existing_results
            for i, (facility, fac_id) in enumerate(zip(facilities[start_index:], ids[start_index:]), start_index+1):
                print(f"\n{'='*60}")
                print(f"🏥 처리 중 ({i}/{len(facilities)}): {facility} (ID: {fac_id})")
                if any(r['시설명'] == facility and r.get('ID', None) == fac_id for r in results):
                    print("⏭ 이미 처리된 시설, 건너뜀")
                    continue
                image_url = self.search_real_facility_images(facility)
                results.append({
                    "시설명": facility,
                    "이미지_URL": image_url,
                    "ID": fac_id
                })
                if i % 10 == 0:
                    self.save_progress(results, output_file)
                    print(f"💾 중간 저장 완료: {i}개 처리")
                time.sleep(2)
            self.save_progress(results, output_file)
            print(f"🎉 모든 처리 완료! 총 {len(results)}개 시설 처리됨")
            successful = sum(1 for r in results if r['이미지_URL'] is not None)
            print(f"📊 최종 성공률: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
            return results
        except Exception as e:
            print(f"🔴 CSV 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            return []

    def save_progress(self, results, output_file):
        df = pd.DataFrame(results)
        df.to_excel(output_file, index=False)

    def close(self):
        if self.driver:
            self.driver.quit()

def main():
    crawler = FinalImageCrawler()
    try:
        csv_file = "Animallo-vb1.csv"
        if not os.path.exists(csv_file):
            print(f"❌ CSV 파일을 찾을 수 없습니다: {csv_file}")
            return
        start_index = 0
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
