
import os
import feedparser
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import sys
sys.stdout.reconfigure(encoding='utf-8')

# .env 파일에서 환경 변수 로드
load_dotenv()

# Supabase 클라이언트 초기화
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# RSS 피드 URL
rss_url = "https://venturebeat.com/category/ai/feed/"

# RSS 피드 파싱
feed = feedparser.parse(rss_url)

# 현재 시간(UTC)
now = datetime.now(timezone.utc)

# 웹 페이지에서 본문 내용을 추출하는 함수
def get_article_content(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        # VentureBeat 기사 본문 선택자
        article_content_div = soup.find('div', class_='article-content')
        if article_content_div:
            paragraphs = article_content_div.find_all('p')
            full_text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True) and not p.find('em')]) # <em> 태그로 시작하는 불필요한 문단 제외
            return full_text
        else:
            print(f"본문 article-content를 찾지 못했습니다: {url}")
            return None
    except Exception as e:
        print(f"본문 내용을 가져오는 중 오류 발생: {e}")
        return None

# 'articles' 테이블에 데이터 삽입 또는 업데이트
for entry in feed.entries:
    # 게시 시간을 파싱하여 UTC 시간으로 변환 (VentureBeat는 다른 포맷을 사용할 수 있으므로 확인 필요)
    try:
        published_time = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z').astimezone(timezone.utc)
    except ValueError:
        # 다른 시간 포맷 시도 (예시)
        try:
            published_time = datetime.fromisoformat(entry.published).astimezone(timezone.utc)
        except ValueError:
            print(f"게시 시간 파싱 실패: {entry.published}")
            continue

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
                'source': 'VentureBeat' # 출처 추가
            }
            try:
                supabase.table('articles').insert(data).execute()
                print(f"'{entry.title}' 기사가 성공적으로 저장되었습니다.")
            except Exception as e:
                print(f"오류가 발생했습니다: {e}")
        else:
            # 이미 존재하는 기사지만, full_content가 비어있는 경우
            if not response.data[0].get('full_content'):
                print(f"'{entry.title}' 기사의 본문이 비어있어 업데이트합니다.")
                content = get_article_content(entry.link)
                if content:
                    try:
                        supabase.table('articles').update({'full_content': content}).eq('link', entry.link).execute()
                        print(f"'{entry.title}' 기사의 본문이 성공적으로 업데이트되었습니다.")
                    except Exception as e:
                        print(f"본문 업데이트 중 오류가 발생했습니다: {e}")
                else:
                    print(f"'{entry.title}' 기사의 본문을 가져오지 못해 업데이트하지 않았습니다.")
            else:
                print(f"이미 존재하는 기사입니다: '{entry.title}'")

print("VentureBeat 뉴스 기사 수집 및 저장이 완료되었습니다.")
