import requests
import os

DANBOORU_API = "https://danbooru.donmai.us/posts.json"

def fetch_danbooru(tags, limit=20, out_dir="downloads/danbooru"):
    os.makedirs(out_dir, exist_ok=True)

    params = {
        "tags": tags,
        "limit": limit
    }

    r = requests.get(DANBOORU_API, params=params)
    r.raise_for_status()

    posts = r.json()

    for post in posts:
        url = post.get("file_url")
        if not url:
            continue

        filename = os.path.join(out_dir, url.split("/")[-1])
        if os.path.exists(filename):
            continue

        print(f"⬇️  {filename}")
        img = requests.get(url)
        with open(filename, "wb") as f:
            f.write(img.content)
