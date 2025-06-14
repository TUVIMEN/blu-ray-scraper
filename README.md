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

```
usage: blu-ray.py [-h] [-d DIR] [-f] [-t NUM] [-w TIME] [-W MILISECONDS]
                  [-r NUM] [--retry-wait TIME] [--force-retry] [-m TIME] [-k]
                  [-L] [-A UA] [-x DICT] [-H HEADER] [-b COOKIE] [-B BROWSER]
                  [--proxy PROXY]
                  [URL ...]

Tool for scraping blu-ray.com. If no URLs provided scrapes the whole site

positional arguments:
  URL                   urls

options:
  -h, --help            Show this help message and exit
  -d, --directory DIR   Use DIR as working directory
  -f, --force           Overwrite existing files
  -t, --threads NUM     run tasks using NUM of threads

Request settings:
  -w, --wait TIME       Sets waiting time for each request
  -W, --wait-random MILISECONDS
                        Sets random waiting time for each request to be at max
                        MILISECONDS
  -r, --retries NUM     Sets number of retries for failed request to NUM
  --retry-wait TIME     Sets interval between each retry
  --force-retry         Retry no matter the error
  -m, --timeout TIME    Sets request timeout
  -k, --insecure        Ignore ssl errors
  -L, --location        Allow for redirections, can be dangerous if
                        credentials are passed in headers
  -A, --user-agent UA   Sets custom user agent
  -x DICT               Set requests proxies dictionary, e.g. -x
                        '{"http":"127.0.0.1:8080","ftp":"0.0.0.0"}'
  -H, --header HEADER   Set curl style header, can be used multiple times e.g.
                        -H 'User: Admin' -H 'Pass: 12345'
  -b, --cookie COOKIE   Set curl style cookie, can be used multiple times e.g.
                        -b 'auth=8f82ab' -b 'PHPSESSID=qw3r8an829'
  -B, --browser BROWSER
                        Get cookies from specified browser e.g. -B firefox
  --proxy PROXY         add proxy to list
```

# Protection

`blu-ray.com` will block you if you make requests too fast, it also sets periodic limit per ip (i did not confirm if it was limited to a day) after which you'll get banned. If done correctly you can expect about 4000 pages scraped every day.

If you want to scrape the whole site you should use a lot of proxies, they don't require residential proxies pretty much anything will do. Although the site is extremely inefficient and their html pages take about 300KB-400KB, so 1170773 entries will take at least 390GB of transfer.

For getting the whole site i recommend running

```bash
while :
do
    ./blu-ray --wait 22 --wait-random 14000 --threads 3 --proxy PROXY1 --proxy PROXY2 --proxy PROXY3
    sleep 1m
done
```
