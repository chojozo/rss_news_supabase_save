import feedparser
import os
from supabase import create_client, Client
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import time
import sys
from datetime import datetime, timedelta, timezone
sys.stdout.reconfigure(encoding='utf-8')

# .env 파일에서 환경 변수 로드
load_dotenv()

# Supabase 설정
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# The Verge RSS 피드 URL 목록 (AI, Tech)
NEWS_URLS = [
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://www.theverge.com/rss/tech/index.xml"
]

def fetch_article_content(url):
    """기사 URL에서 본문 내용을 추출합니다."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        soup = BeautifulSoup(response.text, 'html.parser')

        # The Verge 기사 본문 내용을 포함하는 요소를 찾습니다.
        # 이 부분은 The Verge 웹사이트의 HTML 구조에 따라 조정해야 합니다.
        # 일반적으로 기사 내용은 <article> 태그나 특정 클래스를 가진 div 안에 있습니다.
        # 예시: <div class="c-entry-content"> 또는 <div data-component="PostContent">
        # 정확한 셀렉터를 찾기 위해 실제 기사 페이지를 분석해야 합니다.
        # 여기서는 일반적인 본문 내용을 찾기 위한 몇 가지 시도를 합니다.
        content_div = soup.find('div', {'data-component': 'PostContent'})
        if not content_div:
            content_div = soup.find('div', class_='c-entry-content')
        if not content_div:
            content_div = soup.find('div', class_='duet--article--body-component') # The Verge의 다른 본문 클래스
        if not content_div:
            content_div = soup.find('article') # 일반적인 article 태그

        if content_div:
            all_paragraphs = content_div.find_all('p')
            filtered_paragraphs = []
            for p in all_paragraphs:
                text = p.get_text().strip()
                # 불필요한 문구를 포함하는 단락 필터링
                if text and not any(keyword in text for keyword in ["Posts from this topic", "Follow topics and authors", "MOST POPULAR", "THE VERGE DAILY", "MORE IN NEWS", "TOP STORIES", "Email (required)", "Sign Up", "By submitting your email", "Advertiser Content From", "THIS IS THE TITLE FOR THE NATIVE AD", "MORE IN NEWS", "TOP STORIES", "Comments Drawer", "Close", "PlusFollow", "See All", "by Jay Peters", "News Editor", "Image: The Verge", "Jay Peters is a news editor covering technology, gaming, and more."]):
                    filtered_paragraphs.append(text)
            article_text = '\n'.join(filtered_paragraphs)
            return article_text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching article content from {url}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while parsing {url}: {e}")
        return None

def main():
    for news_url in NEWS_URLS:
        print(f"Fetching news from {news_url}...")
        feed = feedparser.parse(news_url)

    # 현재 시간(UTC)
    now = datetime.now(timezone.utc)

    for entry in feed.entries:
        # 게시 시간을 파싱하여 UTC 시간으로 변환
        try:
            published_time = datetime.strptime(entry.published, '%Y-%m-%dT%H:%M:%S%z').astimezone(timezone.utc)
        except ValueError:
            # 다른 시간 포맷 시도 (예시: RSS 피드에 따라 다를 수 있음)
            try:
                published_time = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z').astimezone(timezone.utc)
            except ValueError:
                print(f"게시 시간 파싱 실패: {entry.published}")
                continue

        # 24시간 이내의 기사인지 확인
        if now - published_time <= timedelta(days=1):
            title = entry.title if hasattr(entry, 'title') else "No Title"
            link = entry.link if hasattr(entry, 'link') else "No Link"
            published = entry.published if hasattr(entry, 'published') else "No Date"
            summary = entry.summary if hasattr(entry, 'summary') else "No Summary"

            print(f"Processing: {title}")
            print(f"Link: {link}")

            # 기사 본문 내용 추출
            full_content = fetch_article_content(link)

            # 요청 사이에 딜레이 추가
            time.sleep(1) # 1초 딜레이

            # Supabase에 데이터 삽입
            try:
                # 데이터베이스에 이미 있는 링크인지 확인
                response = supabase.table('articles').select('link').eq('link', link).execute()
                
                # response.data가 비어있지 않다면, 이미 존재하는 데이터
                if not response.data:
                    data, count = supabase.table('articles').insert({
                        "title": title,
                        "link": link,
                        "published_at": published,
                        "summary": summary,
                        "full_content": full_content or summary,
                        "source": "The Verge"
                    }).execute()
                    print(f"Inserted: {title}")
                else:
                    print(f"Already exists: {title}")
            except Exception as e:
                print(f"Error inserting {title} into Supabase: {e}")
        else:
            print(f"Skipping old article: {entry.title}")

if __name__ == "__main__":
    main()
