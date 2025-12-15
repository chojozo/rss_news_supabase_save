import feedparser
import os
from supabase import create_client, Client
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import time
import sys
from datetime import datetime, timedelta, timezone
from dateutil import parser
sys.stdout.reconfigure(encoding='utf-8')

# .env 파일에서 환경 변수 로드
load_dotenv()

# Supabase 설정
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# AITimes RSS 피드 URL
NEWS_URL = "https://www.aitimes.com/rss/allArticle.xml"

def fetch_article_content(url):
    """기사 URL에서 본문 내용을 추출합니다."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # AITimes 사이트의 본문 구조를 일반적인 선택자들로 시도
        content_div = soup.find('div', class_='article-body')
        if not content_div:
            content_div = soup.find('div', class_='content')
        if not content_div:
            content_div = soup.find('article')
        if not content_div:
            content_div = soup.find('div', class_='entry-content')

        if content_div:
            all_paragraphs = content_div.find_all('p')
            filtered_paragraphs = []
            exclude_keywords = ["댓글", "무단전재", "이 기사를", "저작권", "All rights reserved", "광고"]

            for p in all_paragraphs:
                text = p.get_text().strip()
                if not text:
                    continue
                if any(keyword in text for keyword in exclude_keywords):
                    continue
                if len(text) < 40:
                    continue
                filtered_paragraphs.append(text)
            article_text = '\n'.join(filtered_paragraphs)
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

    # 현재 시간(UTC)
    now = datetime.now(timezone.utc)

    for entry in feed.entries:
        # 게시 시간을 파싱하여 UTC 시간으로 변환 (dateutil 사용)
        try:
            if hasattr(entry, 'published') and entry.published:
                published_time = parser.parse(entry.published).astimezone(timezone.utc)
            else:
                # published 정보가 없으면 현재 시간으로 간주
                published_time = now
        except Exception:
            print(f"게시 시간 파싱 실패: {getattr(entry, 'published', 'NoPublished')}")
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
            time.sleep(1)

            # Supabase에 데이터 삽입
            try:
                response = supabase.table('articles').select('link').eq('link', link).execute()

                if not response.data:
                    supabase.table('articles').insert({
                        "title": title,
                        "link": link,
                        "published_at": published,
                        "summary": summary,
                        "full_content": full_content or summary,
                        "source": "AITimes"
                    }).execute()
                    print(f"Inserted: {title}")
                else:
                    print(f"Already exists: {title}")
            except Exception as e:
                print(f"Error inserting {title} into Supabase: {e}")
        else:
            print(f"Skipping old article: {getattr(entry, 'title', 'No Title')}")

if __name__ == "__main__":
    main()
