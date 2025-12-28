import requests
import os

RULE34_API = "https://api.rule34.xxx/index.php"

def fetch_rule34(tags, limit=50, out_dir="downloads/rule34"):
    os.makedirs(out_dir, exist_ok=True)

    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "json": 1,
        "tags": tags,
        "limit": limit
    }

    r = requests.get(RULE34_API, params=params)
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
