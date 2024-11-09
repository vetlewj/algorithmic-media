#todo: filter content for the main part of the articles and not the headers that link to their own content (done!)
#todo: id (doi) and name datascraping  (done!)
#todo: make the scraper work for the top ten sites in the notion, sometimes they have the doi in the link os just use that (done!)
import csv
import requests
from bs4 import BeautifulSoup
from collections import Counter
from urllib.parse import urljoin, urlparse
import re

def extract_doi(url, text, soup):
    """Enhanced DOI extraction from multiple sources"""
    dois = set()
    
    # Common DOI patterns
    patterns = [
        r'10\.\d{4,9}/[-._;()/:\w]+',
        r'10\.\d{4,9}/\S+?(?=\s|$)',
        r'doi:\s*(10\.\d{4,9}/[-._;()/:\w]+)',
        r'doi\.org/(10\.\d{4,9}/[-._;()/:\w]+)'
    ]
    
    # 1. Check URL for DOI
    for pattern in patterns:
        url_match = re.search(pattern, url)
        if url_match:
            dois.add(url_match.group(1) if 'doi:' in pattern or 'doi.org' in pattern else url_match.group())
    
    # 2. Check meta tags
    meta_selectors = {
        'citation_doi': ['meta[name="citation_doi"]', 'meta[name="dc.Identifier"]', 'meta[property="citation_doi"]'],
        'dc_doi': ['meta[name="dc.identifier"]', 'meta[name="DC.identifier"]'],
        'prism_doi': ['meta[name="prism.doi"]', 'meta[name="prism.DOI"]']
    }
    
    for selector_group in meta_selectors.values():
        for selector in selector_group:
            meta_tag = soup.select_one(selector)
            if meta_tag and meta_tag.get('content'):
                content = meta_tag['content']
                for pattern in patterns:
                    meta_match = re.search(pattern, content)
                    if meta_match:
                        dois.add(meta_match.group(1) if 'doi:' in pattern or 'doi.org' in pattern else meta_match.group())
    
    # 3. Check common DOI locations in HTML
    doi_containers = soup.select('.doi, .article-doi, #doi-value, .citation-doi, .article-identifier')
    for container in doi_containers:
        text_content = container.get_text()
        for pattern in patterns:
            container_match = re.search(pattern, text_content)
            if container_match:
                dois.add(container_match.group(1) if 'doi:' in pattern or 'doi.org' in pattern else container_match.group())
    
    # 4. Check main text content
    for pattern in patterns:
        text_matches = re.finditer(pattern, text)
        for match in text_matches:
            dois.add(match.group(1) if 'doi:' in pattern or 'doi.org' in pattern else match.group())
    
    # 5. Special cases for specific domains
    domain = urlparse(url).netloc.lower()
    
    if 'sciencedirect.com' in domain:
        pii = soup.select_one('meta[name="citation_pii"]')
        if pii and pii.get('content'):
            dois.add(f"10.1016/{pii['content']}")
    
    elif 'springer.com' in domain or 'link.springer.com' in domain:
        chapter_doi = soup.select_one('.chapter-doi')
        if chapter_doi:
            doi_match = re.search(r'10\.\d{4}/[^\s]+', chapter_doi.get_text())
            if doi_match:
                dois.add(doi_match.group())
    
    elif 'wiley.com' in domain:
        doi_div = soup.select_one('.doi-access')
        if doi_div:
            doi_match = re.search(r'10\.\d{4}/[^\s]+', doi_div.get_text())
            if doi_match:
                dois.add(doi_match.group())
    
    return list(dois)[0] if dois else None

def get_most_frequent_link(url):
    """Get most frequent link and DOI from a webpage"""
    parsed_url = urlparse(url)
    netloc = parsed_url.netloc.lower()
    
    skip_domains = ['youtube.com', 'youtu.be']
    if any(domain in netloc for domain in skip_domains):
        return {
            'most_frequent_link': 'Skipped (Video platform)',
            'doi': None
        }
        
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; MyScraper/1.0)'}
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
    except requests.HTTPError as e:
        print(f"HTTP error fetching {url}: {e}")
        return {
            'most_frequent_link': f'HTTP error: {e}',
            'doi': None
        }
    except requests.ConnectionError as e:
        print(f"Connection error fetching {url}: {e}")
        return {
            'most_frequent_link': f'Connection error: {e}',
            'doi': None
        }
    except requests.Timeout as e:
        print(f"Timeout error fetching {url}: {e}")
        return {
            'most_frequent_link': f'Timeout error: {e}',
            'doi': None
        }
    except requests.RequestException as e:
        print(f"General error fetching {url}: {e}")
        return {
            'most_frequent_link': f'Error: {e}',
            'doi': None
        }
        
    soup = BeautifulSoup(response.content, 'html.parser')
    base_url = response.url  # Handle redirects
    
    # Extract and normalize links
    links = []
    for a_tag in soup.find_all('a', href=True):
        href = a_tag.get('href')
        if not href or href.strip() == '':
            continue
        full_url = urljoin(base_url, href)
        links.append(full_url)
        
    if not links:
        return {
            'most_frequent_link': 'No links found',
            'doi': None
        }
        
    link_counts = Counter(links)
    most_common_links = link_counts.most_common()
    highest_frequency = most_common_links[0][1]
    most_frequent_links = [link for link, count in most_common_links if count == highest_frequency]
    
    # Extract DOI from content
    main_text = soup.get_text()
    doi = extract_doi(url, main_text, soup)
    
    return {
        'most_frequent_link': most_frequent_links[0],
        'doi': doi
    }

# Main processing code
input_csv = 'original_data.csv'
rows = []
with open(input_csv, 'r', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile, delimiter=',')
    for row in reader:
        rows.append(row)

# Process each row
for row in rows:
    url = row['url']
    print(f"Processing URL: {url}")
    result = get_most_frequent_link(url)
    
    if isinstance(result, dict):
        row['most_frequent_link'] = result['most_frequent_link']
        row['doi'] = result['doi']
    else:
        row['most_frequent_link'] = result
        row['doi'] = None

# Write the updated data to new CSV test
output_csv = 'updated_data.csv'
fieldnames = list(rows[0].keys())
with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=',', quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)