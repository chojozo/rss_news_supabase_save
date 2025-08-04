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

# TechCrunch RSS 피드 URL
NEWS_URL = "https://techcrunch.com/feed/"

def fetch_article_content(url):
    """기사 URL에서 본문 내용을 추출합니다."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # TechCrunch 기사 본문 내용을 포함하는 요소를 찾습니다.
        content_div = soup.find('div', class_='article-content') # TechCrunch의 본문 클래스

        if content_div:
            all_paragraphs = content_div.find_all('p')
            article_text = '\n'.join([p.get_text().strip() for p in all_paragraphs])
            return article_text
        else:
            print(f"Warning: Could not find article content for {url}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching article content from {url}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while parsing {url}: {e}")
        return None

def main():
    print(f"Fetching news from {NEWS_URL}...")
    feed = feedparser.parse(NEWS_URL)

    now = datetime.now(timezone.utc)

    for entry in feed.entries:
        try:
            # TechCrunch는 'published_parsed'를 사용하는 것이 더 안정적일 수 있습니다.
            if hasattr(entry, 'published_parsed'):
                # feedparser가 제공하는 UTC 시간을 직접 사용하여 datetime 객체 생성
                published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            else:
                # 'published' 문자열에 타임존 정보가 포함되어 있으므로, 이를 파싱하여 UTC로 변환
                published_time = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z').astimezone(timezone.utc)
        except (ValueError, TypeError):
            print(f"게시 시간 파싱 실패: {entry.published if hasattr(entry, 'published') else 'No publish time'}")
            continue

        if now - published_time <= timedelta(days=1):
            title = entry.title if hasattr(entry, 'title') else "No Title"
            link = entry.link if hasattr(entry, 'link') else "No Link"
            published = entry.published if hasattr(entry, 'published') else "No Date"
            summary = entry.summary if hasattr(entry, 'summary') else "No Summary"

            print(f"Processing: {title}")
            print(f"Link: {link}")

            full_content = fetch_article_content(link)
            time.sleep(1)

            try:
                response = supabase.table('articles').select('link').eq('link', link).execute()
                
                if not response.data:
                    data, count = supabase.table('articles').insert({
                        "title": title,
                        "link": link,
                        "published_at": published,
                        "summary": summary,
                        "full_content": full_content or summary,
                        "source": "TechCrunch"
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
