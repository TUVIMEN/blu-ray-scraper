# blu-ray-scraper

A scraper for [blu-ray.com](https://www.blu-ray.com/).

# Output examples

Can be found in [examples](examples/). Files under `digital`, `dvd`, `itunes`, `ma`, `movies`, `prime` and `uv` have the same format, different to `main` - [dvd/101447](examples/dvd/101447) [main/31864](examples/main/31864).

# Usage

If called with urls to resources, only they will be scraped

```bash
./blu-ray.py 'https://www.blu-ray.com/movies/Tarantino-XX-8-Film-Collection-Blu-ray/55782/' 'https://www.blu-ray.com/digital/Tarantino-6-Film-Collection-Digital/26486/?retailerid=20'
```

If no urls are passed then sitemap urls will be scraped and saved to `links` file (around 1170773 urls) and then scraped for contents.

Saved data is categorized into directories `digital`, `dvd`, `itunes`, `ma`, `main`, `movies`, `prime` and saved in json files named by it's id in them e.g. `digital/5`, `dvd/272457`.

Running with `--help` option will print available options.

    ./blu-ray.py --help

# Protection

`blu-ray.com` will block you if you make requests too fast, it also sets periodic limit per ip (i did not confirm if it was limited to a day) after which you'll get banned. If done correctly you can expect about 4000 pages scraped every day.

If you want to scrape the whole site you should use a lot of proxies, they don't require residential proxies pretty much anything will do. Although the site is extremely inefficient and their html pages take about 300KB-400KB, so 1170773 entries will take at least 390GB of transfer.

For getting the whole site i recommend running

```bash
while :
do
    ./blu-ray --wait 22 --wait-random 14000 --proxies '{"https": "YOUR ROTATED PROXY"}'
    sleep 1m
done
```
