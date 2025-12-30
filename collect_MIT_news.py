

import os
import feedparser
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

# .env 파일에서 환경 변수 로드
load_dotenv()

# Supabase 클라이언트 초기화
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# RSS 피드 URL
rss_url = "https://www.technologyreview.com/topic/artificial-intelligence/feed/"

# User-Agent 헤더 추가하여 RSS 피드 파싱
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
}
response = requests.get(rss_url, headers=headers, timeout=10)
feed = feedparser.parse(response.text)

# 현재 시간(UTC)
now = datetime.now(timezone.utc)

# 웹 페이지에서 본문 내용을 추출하는 함수
def get_article_content(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')

        # MIT Technology Review 기사 본문 선택자
        content_div = soup.find('div', id='content--body')
        if content_div:
            paragraphs = content_div.find_all('p')
            # 문단들을 줄바꿈으로 구분하여 결합
            full_text = '\n\n'.join([
                p.get_text(strip=True)
                for p in paragraphs
                if p.get_text(strip=True)
            ])
            return full_text if full_text else None
        else:
            print(f"본문을 찾지 못했습니다: {url}")
            return None
    except Exception as e:
        print(f"본문 내용을 가져오는 중 오류 발생: {e}")
        return None

# 'articles' 테이블에 데이터 삽입 또는 업데이트
for entry in feed.entries:
    # 게시 시간을 파싱하여 UTC 시간으로 변환
    published_time = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z').astimezone(timezone.utc)

    # 24시간 이내의 기사인지 확인
    if now - published_time <= timedelta(days=1):
        # 데이터베이스에 이미 있는 링크인지 확인
        response = supabase.table('articles').select('link, full_content').eq('link', entry.link).execute()
        
        # response.data가 비어있지 않다면, 이미 존재하는 데이터
        if not response.data:
            # 기사 본문 내용 가져오기
            content = get_article_content(entry.link)

            data = {
                'title': entry.title,
                'link': entry.link,
                'published_at': entry.published,
                'summary': entry.summary,
                'full_content': content,
                'source': 'MIT Technology Review' # 출처 추가
            }
            try:
                supabase.table('articles').insert(data).execute()
                print(f"'{entry.title}' 기사가 성공적으로 저장되었습니다.")
            except Exception as e:
                print(f"오류가 발생했습니다: {e}")
        else:
            # 이미 존재하는 기사 정보 가져오기
            existing_article = response.data[0]
            
            # full_content가 비어있거나 source가 비어있는 경우 업데이트 시도
            if not existing_article.get('full_content') or not existing_article.get('source'):
                print(f"'{entry.title}' 기사의 본문 또는 출처가 비어있어 업데이트합니다.")
                update_data = {}
                
                if not existing_article.get('full_content'):
                    content = get_article_content(entry.link)
                    if content:
                        update_data['full_content'] = content
                    else:
                        print(f"'{entry.title}' 기사의 본문을 가져오지 못했습니다.")
                
                if not existing_article.get('source'):
                    update_data['source'] = 'MIT Technology Review'

                if update_data:
                    try:
                        supabase.table('articles').update(update_data).eq('link', entry.link).execute()
                        print(f"'{entry.title}' 기사가 성공적으로 업데이트되었습니다.")
                    except Exception as e:
                        print(f"업데이트 중 오류가 발생했습니다: {e}")
                else:
                    print(f"'{entry.title}' 기사는 업데이트할 내용이 없습니다.")
            else:
                print(f"이미 존재하는 기사입니다: '{entry.title}'")

print("24시간 이내의 뉴스 기사 수집 및 저장이 완료되었습니다.")

