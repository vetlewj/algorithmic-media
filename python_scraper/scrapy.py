# =====================================
# CONFIGURATION SETTINGS
# =====================================
TESTING = True  # Set to False for full run
TEST_INTERVAL = 1 # Process every Nth link (e.g., 50 means every 50th link)
TOP_N_DOMAINS = 50  # Number of top domains to process per category
INPUT_FILE = 'original_data.csv'  # Your input file name
RESULTS_DIR = 'scraping_results'  # Directory for results
USER_AGENT = 'Mozilla/5.0 (compatible; ResearchScraper/1.0)'
TIMEOUT = 10  # Seconds for request timeout

# Domain Classifications
DOMAINS = {
    'social_media': [
        'youtube.com', 'youtu.be', 'twitter.com', 'x.com', 
        'facebook.com', 'fb.com', 'instagram.com', 'pinterest.com',
        'reddit.com', 'linkedin.com', 'tiktok.com'
    ],
    'repo': [
        'arxiv.org', 'doi.org', 'pubmed.gov', 'ncbi.nlm.nih.gov',
        'researchgate.net', 'academia.edu', 'sciencedirect.com',
        'springer.com', 'wiley.com', 'bioarxiv.org', 'medrxiv.org',
        'ssrn.com', 'nature.com/articles', 'science.org/doi'
    ],
    'news': [
        'news', 'times', 'bbc', 'cnn', 'reuters', 'ap.org', 
        'bloomberg.com', 'nytimes.com', 'washingtonpost.com',
        'theguardian.com', 'sciencenews.org', 'scientificamerican.com'
    ],
    'scientific': [
        'science', 'nature.com', 'scientific', 'edu',
        'acs.org', 'ieee.org', 'cell.com', 'pnas.org',
        'frontiersin.org', 'plos.org', 'royalsociety.org'
    ],
    'scam': [
        'bit.ly', 'goo.gl', 'tinyurl.com', 'ow.ly', 
        't.co', 'tr.im', 'is.gd', 'cli.gs', 'yourls.org'
    ]
}
# =====================================

import csv
import requests
from bs4 import BeautifulSoup
from collections import Counter, defaultdict
from urllib.parse import urljoin, urlparse
import re
import os
from datetime import datetime
import logging
import pandas as pd
from tqdm import tqdm

# Create results directory if it doesn't exist
os.makedirs(RESULTS_DIR, exist_ok=True)

# Set up logging
logging.basicConfig(
    filename=f'{RESULTS_DIR}/scraping_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def extract_url_from_comment(comment):
    """Extract URLs from comment text"""
    if not comment or pd.isna(comment):
        return None
        
    # Common URL patterns
    url_patterns = [
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        r'doi\.org/[^\s<>"]+',
        r'arxiv\.org/[^\s<>"]+',
        r'pubmed\.gov/[^\s<>"]+',
    ]
    
    for pattern in url_patterns:
        matches = re.findall(pattern, str(comment))
        if matches:
            return matches[0]
    
    return None

def extract_doi(url, text, soup):
    """Enhanced DOI extraction from multiple sources with tracking"""
    dois = set()
    extraction_info = {
        'method': None,
        'pattern': None,
        'success': False
    }
    
    # Define DOI patterns
    patterns = [
        r'10\.\d{4,9}/[-._;()/:\w]+',
        r'10\.\d{4,9}/\S+?(?=\s|$)',
        r'doi:\s*(10\.\d{4,9}/[-._;()/:\w]+)',
        r'doi\.org/(10\.\d{4,9}/[-._;()/:\w]+)'
    ]
    
    # METHOD 1: URL Check
    for pattern in patterns:
        url_match = re.search(pattern, url)
        if url_match:
            doi = url_match.group(1) if 'doi:' in pattern or 'doi.org' in pattern else url_match.group()
            dois.add(doi)
            extraction_info['method'] = 'url'
            extraction_info['pattern'] = pattern
            break

    # METHOD 2: Meta Tags Check
    if not dois:
        meta_selectors = {
            'citation_doi': ['meta[name="citation_doi"]', 'meta[name="dc.Identifier"]', 'meta[property="citation_doi"]'],
            'dc_doi': ['meta[name="dc.identifier"]', 'meta[name="DC.identifier"]'],
            'prism_doi': ['meta[name="prism.doi"]', 'meta[name="prism.DOI"]']
        }
        
        for selector_type, selectors in meta_selectors.items():
            for selector in selectors:
                meta_tag = soup.select_one(selector)
                if meta_tag and meta_tag.get('content'):
                    content = meta_tag['content']
                    for pattern in patterns:
                        meta_match = re.search(pattern, content)
                        if meta_match:
                            doi = meta_match.group(1) if 'doi:' in pattern or 'doi.org' in pattern else meta_match.group()
                            dois.add(doi)
                            extraction_info['method'] = f'meta_{selector_type}'
                            extraction_info['pattern'] = pattern
                            break
                    if dois:
                        break
            if dois:
                break

    # METHOD 3: HTML Container Check
    if not dois:
        doi_containers = soup.select('.doi, .article-doi, #doi-value, .citation-doi, .article-identifier')
        for container in doi_containers:
            text_content = container.get_text()
            for pattern in patterns:
                container_match = re.search(pattern, text_content)
                if container_match:
                    doi = container_match.group(1) if 'doi:' in pattern or 'doi.org' in pattern else container_match.group()
                    dois.add(doi)
                    extraction_info['method'] = 'html_container'
                    extraction_info['pattern'] = pattern
                    break
            if dois:
                break

    # METHOD 4: Full Text Search
    if not dois:
        for pattern in patterns:
            text_matches = re.finditer(pattern, text)
            for match in text_matches:
                doi = match.group(1) if 'doi:' in pattern or 'doi.org' in pattern else match.group()
                dois.add(doi)
                extraction_info['method'] = 'text_content'
                extraction_info['pattern'] = pattern
                break
            if dois:
                break

    # METHOD 5: Publisher-Specific Cases
    if not dois:
        domain = urlparse(url).netloc.lower()
        
        if 'sciencedirect.com' in domain:
            pii = soup.select_one('meta[name="citation_pii"]')
            if pii and pii.get('content'):
                dois.add(f"10.1016/{pii['content']}")
                extraction_info['method'] = 'sciencedirect_pii'
        
        elif 'springer.com' in domain or 'link.springer.com' in domain:
            chapter_doi = soup.select_one('.chapter-doi')
            if chapter_doi:
                doi_match = re.search(r'10\.\d{4}/[^\s]+', chapter_doi.get_text())
                if doi_match:
                    dois.add(doi_match.group())
                    extraction_info['method'] = 'springer_specific'
        
        elif 'wiley.com' in domain:
            doi_div = soup.select_one('.doi-access')
            if doi_div:
                doi_match = re.search(r'10\.\d{4}/[^\s]+', doi_div.get_text())
                if doi_match:
                    dois.add(doi_match.group())
                    extraction_info['method'] = 'wiley_specific'

    extraction_info['success'] = len(dois) > 0
    return list(dois)[0] if dois else None, extraction_info

def categorize_url(row):
    """Categorize URLs into predefined categories based on domain patterns"""
    domain = str(row.get('domain', '')).lower()
    url = str(row.get('url', '')).lower()
    
    for category, domains in DOMAINS.items():
        if any(d in domain for d in domains):
            return category
    
    return 'unknown'

def process_url(url, category, comment=None):
    """Process single URL with error handling and result tracking"""
    result = {
        'url': url,
        'success': False,
        'doi_found': False,
        'doi': None,
        'extraction_method': None,
        'pattern_matched': None,
        'error': None,
        'source': 'main_url'
    }
    
    # First try comment URL if available
    if comment:
        comment_url = extract_url_from_comment(comment)
        if comment_url:
            try:
                headers = {'User-Agent': USER_AGENT}
                response = requests.get(comment_url, timeout=TIMEOUT, headers=headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                main_text = soup.get_text()
                doi, extraction_info = extract_doi(comment_url, main_text, soup)
                
                if doi:
                    return {
                        'url': comment_url,
                        'success': True,
                        'doi_found': True,
                        'doi': doi,
                        'extraction_method': extraction_info['method'],
                        'pattern_matched': extraction_info['pattern'],
                        'error': None,
                        'source': 'comment_url'
                    }
            except requests.exceptions.RequestException:
                # If comment URL fails, continue with main URL
                pass
    
    # Try main URL
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, timeout=TIMEOUT, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        main_text = soup.get_text()
        doi, extraction_info = extract_doi(url, main_text, soup)
        
        result.update({
            'success': True,
            'doi_found': bool(doi),
            'doi': doi,
            'extraction_method': extraction_info['method'],
            'pattern_matched': extraction_info['pattern']
        })
        
    except requests.exceptions.RequestException as e:
        result.update({
            'error': str(e)
        })
    
    return result

def analyze_domains(input_file):
    """Main analysis pipeline with testing mode support"""
    try:
        # Read and prepare data
        df = pd.read_csv(input_file)
        df['category'] = df.apply(categorize_url, axis=1)
        
        # Initialize results tracking
        results = {
            'processed': [],
            'stats': defaultdict(lambda: {
                'total': 0,
                'successful': 0,
                'doi_found': 0,
                'comment_urls_used': 0,
                'errors': defaultdict(int)
            })
        }
        
        # Process each category
        for category in ['news', 'scientific', 'repo']:
            category_df = df[df['category'] == category]
            
            # Get top N domains
            top_domains = category_df['domain'].value_counts().head(TOP_N_DOMAINS).index
            category_urls = category_df[category_df['domain'].isin(top_domains)]
            
            logging.info(f"Processing {len(category_urls)} URLs for category: {category}")
            
            # Apply testing interval if in testing mode
            if TESTING:
                category_urls = category_urls.iloc[::TEST_INTERVAL]
            
            # Process URLs
            for _, row in tqdm(category_urls.iterrows(), desc=f"Processing {category}"):
                if pd.isna(row.get('url', None)):
                    continue
                
                result = process_url(row['url'], category, row.get('comment', None))
                result['category'] = category
                result['domain'] = row['domain']
                
                results['processed'].append(result)
                
                # Update statistics
                stats = results['stats'][category]
                stats['total'] += 1
                if result['success']:
                    stats['successful'] += 1
                if result['doi_found']:
                    stats['doi_found'] += 1
                if result['source'] == 'comment_url':
                    stats['comment_urls_used'] += 1
                if result['error']:
                    stats['errors'][type(result['error']).__name__] += 1
        
        # Generate reports
        processed_df = pd.DataFrame(results['processed'])
        stats_df = pd.DataFrame([
            {
                'category': cat,
                'total_urls': stats['total'],
                'successful_scrapes': stats['successful'],
                'doi_found': stats['doi_found'],
                'comment_urls_used': stats['comment_urls_used'],
                'success_rate': stats['successful'] / stats['total'] if stats['total'] > 0 else 0,
                'doi_rate': stats['doi_found'] / stats['successful'] if stats['successful'] > 0 else 0,
                'most_common_error': max(stats['errors'].items(), key=lambda x: x[1])[0] if stats['errors'] else None
            }
            for cat, stats in results['stats'].items()
        ])
        
        # Save all results
        processed_df.to_csv(f'{RESULTS_DIR}/processed_urls.csv', index=False)
        stats_df.to_csv(f'{RESULTS_DIR}/scraping_statistics.csv', index=False)
        
        # Save category-specific results
        for category in ['news', 'scientific', 'repo']:
            category_results = processed_df[processed_df['category'] == category]
            category_results.to_csv(f'{RESULTS_DIR}/{category}_results.csv', index=False)
        
        return results
    
    except Exception as e:
        logging.error(f"Error in analyze_domains: {str(e)}")
        raise

if __name__ == "__main__":
    logging.info("Starting scraping analysis")
    if TESTING:
        logging.info(f"Running in TEST mode - processing every {TEST_INTERVAL}th link")
        logging.info(f"Analyzing top {TOP_N_DOMAINS} domains per category")
    
    try:
        results = analyze_domains(INPUT_FILE)
        logging.info("Analysis complete - check scraping_results directory for reports")
    except Exception as e:
        logging.error(f"Fatal error during analysis: {str(e)}")
        raise