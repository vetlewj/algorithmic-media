# =====================================
# CONFIGURATION SETTINGS
# =====================================
TESTING = True  # Set to False for full run
TEST_INTERVAL = 1  # Process every Nth link
TOP_N_DOMAINS = 50  # Number of top domains to process per category
INPUT_FILE = 'original_data.csv'
RESULTS_DIR = 'scraping_results'
USER_AGENT = 'Mozilla/5.0 (compatible; ResearchScraper/1.0)'
TIMEOUT = 30  # Increased timeout for reliability

# Academic Publisher Domains
ACADEMIC_DOMAINS = {
    'nature': ['nature.com'],
    'science_direct': ['sciencedirect.com'],
    'pnas': ['pnas.org'],
    'wiley': ['onlinelibrary.wiley.com'],
    'pubmed': ['ncbi.nlm.nih.gov'],
    'plos': ['journals.plos.org'],
    'cell': ['cell.com'],
    'science': ['science.sciencemag.org', 'science.org', 'advances.sciencemag.org'],
    'oxford': ['academic.oup.com'],
    'jama': ['jamanetwork.com'],
    'springer': ['link.springer.com'],
    'sage': ['journals.sagepub.com'],
    'researchgate': ['researchgate.net'],
    'mdpi': ['mdpi.com'],
    'lancet': ['thelancet.com'],
    'frontiers': ['frontiersin.org'],
    'taylor_francis': ['tandfonline.com'],
    'acs': ['pubs.acs.org'],
    'nejm': ['nejm.org']
}

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
        'ssrn.com', 'nature.com/articles', 'science.org/doi',
        'pnas.org', 'cell.com', 'academic.oup.com', 'jamanetwork.com',
        'mdpi.com', 'thelancet.com', 'frontiersin.org', 'tandfonline.com',
        'pubs.acs.org', 'nejm.org'
    ],
    'news': [
        'news', 'times', 'bbc', 'cnn', 'reuters', 'ap.org', 
        'bloomberg.com', 'nytimes.com', 'washingtonpost.com',
        'theguardian.com', 'sciencenews.org', 'scientificamerican.com'
    ],
    'scientific': [
        'science', 'nature.com', 'scientific', 'edu',
        'acs.org', 'ieee.org', 'cell.com', 'pnas.org',
        'frontiersin.org', 'plos.org', 'royalsociety.org',
        'academic.oup.com', 'mdpi.com'
    ],
    'scam': [
        'bit.ly', 'goo.gl', 'tinyurl.com', 'ow.ly', 
        't.co', 'tr.im', 'is.gd', 'cli.gs', 'yourls.org'
    ]
}

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
import time
from typing import Dict, Optional, Tuple, Union, Any

# Create results directory if it doesn't exist
os.makedirs(RESULTS_DIR, exist_ok=True)

# Set up logging
logging.basicConfig(
    filename=f'{RESULTS_DIR}/scraping_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class PublisherHandler:
    """Base class for publisher-specific extraction logic"""
    
    @staticmethod
    def get_handler(domain: str) -> 'PublisherHandler':
        """Factory method to get appropriate handler for domain"""
        domain = domain.lower()
        for publisher, domains in ACADEMIC_DOMAINS.items():
            if any(d in domain for d in domains):
                handler_class = globals().get(f"{publisher.title()}Handler")
                if handler_class:
                    return handler_class()
        return GenericHandler()

    def extract_doi_and_abstract(self, soup: BeautifulSoup, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract DOI and abstract using publisher-specific methods"""
        raise NotImplementedError

class GenericHandler(PublisherHandler):
    """Handler for unknown or generic academic sites"""
    
    def extract_doi_and_abstract(self, soup: BeautifulSoup, url: str) -> Tuple[Optional[str], Optional[str]]:
        doi = self._extract_doi(soup, url)
        abstract = self._extract_abstract(soup)
        return doi, abstract

    def _extract_doi(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        # Try common DOI patterns
        doi_patterns = [
            r'10\.\d{4,9}/[-._;()/:\w]+',
            r'doi:\s*(10\.\d{4,9}/[-._;()/:\w]+)',
            r'doi\.org/(10\.\d{4,9}/[-._;()/:\w]+)'
        ]
        
        # Check meta tags
        meta_tags = [
            ('citation_doi', soup.find('meta', {'name': 'citation_doi'})),
            ('DC.Identifier', soup.find('meta', {'name': 'DC.Identifier'})),
            ('dc.identifier', soup.find('meta', {'name': 'dc.identifier'})),
            ('prism.doi', soup.find('meta', {'name': 'prism.doi'}))
        ]
        
        for tag_name, tag in meta_tags:
            if tag and tag.get('content'):
                content = tag.get('content')
                for pattern in doi_patterns:
                    match = re.search(pattern, content)
                    if match:
                        return match.group(1) if 'doi:' in pattern else match.group(0)
        
        # Check URL
        for pattern in doi_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1) if 'doi:' in pattern else match.group(0)
        
        return None

    def _extract_abstract(self, soup: BeautifulSoup) -> Optional[str]:
        # Try common abstract locations
        abstract_selectors = [
            'meta[name="description"]',
            'meta[name="dc.description"]',
            'div[class*="abstract"]',
            'section[class*="abstract"]',
            'p[class*="abstract"]',
            '#abstract'
        ]
        
        for selector in abstract_selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    return element.get('content')
                else:
                    return element.get_text(strip=True)
        
        return None

class NatureHandler(PublisherHandler):
    """Handler for Nature.com articles"""
    
    def extract_doi_and_abstract(self, soup: BeautifulSoup, url: str) -> Tuple[Optional[str], Optional[str]]:
        doi = self._extract_doi(soup, url)
        abstract = self._extract_abstract(soup)
        return doi, abstract

    # In GenericHandler, update the DOI patterns:
def _extract_doi(self, soup: BeautifulSoup, url: str) -> Optional[str]:
    # Expanded DOI patterns to catch more variations
    doi_patterns = [
        r'10\.\d{2,9}/[-\._()/:A-Za-z0-9]+',  # More permissive
        r'doi:?\s*(10\.\d{2,9}/[-\._()/:A-Za-z0-9]+)',
        r'(?:dx\.)?doi\.org/(10\.\d{2,9}/[-\._()/:A-Za-z0-9]+)',
        r'citation_doi" content="(10\.\d{2,9}/[-\._()/:A-Za-z0-9]+)"'
    ]
    
    logging.debug(f"Attempting to extract DOI from URL: {url}")
    
    # Check text content for DOIs
    for element in soup.find_all(['p', 'div', 'span', 'a']):
        text = element.get_text()
        if 'doi' in text.lower():
            for pattern in doi_patterns:
                match = re.search(pattern, text)
                if match:
                    doi = match.group(1) if 'doi' in pattern.lower() else match.group(0)
                    logging.debug(f"Found DOI in text: {doi}")
                    return doi

    # Check meta tags
    meta_tags = [
        ('citation_doi', soup.find('meta', {'name': 'citation_doi'})),
        ('DC.Identifier', soup.find('meta', {'name': 'DC.Identifier'})),
        ('dc.identifier', soup.find('meta', {'name': 'dc.identifier'})),
        ('prism.doi', soup.find('meta', {'name': 'prism.doi'})),
        ('doi', soup.find('meta', {'name': 'doi'})),
        ('citation_doi', soup.find('meta', {'name': 'citation_doi'}))
    ]
    
    for tag_name, tag in meta_tags:
        if tag and tag.get('content'):
            content = tag.get('content').strip()
            if content.startswith('doi:'):
                content = content[4:]
            if content.startswith('https://doi.org/'):
                content = content[16:]
            for pattern in doi_patterns:
                match = re.search(pattern, content)
                if match:
                    doi = match.group(1) if 'doi' in pattern.lower() else match.group(0)
                    logging.debug(f"Found DOI in meta tag {tag_name}: {doi}")
                    return doi
    
    # Check URL last
    for pattern in doi_patterns:
        match = re.search(pattern, url)
        if match:
            doi = match.group(1) if 'doi' in pattern.lower() else match.group(0)
            logging.debug(f"Found DOI in URL: {doi}")
            return doi
            
    logging.debug("No DOI found")
    return None

# Update process_url function to handle redirects and SSL:
def process_url(url: str, category: str, comment: Optional[str] = None) -> Dict[str, Any]:
    result = {
        'url': url,
        'success': False,
        'doi_found': False,
        'abstract_found': False,
        'doi': None,
        'abstract': None,
        'extraction_method': None,
        'error': None,
        'source': 'main_url'
    }
    
    try:
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        # Configure session for redirects and SSL
        session = requests.Session()
        session.verify = False  # Handle SSL issues
        session.max_redirects = 5
        
        response = session.get(
            url, 
            timeout=TIMEOUT, 
            headers=headers,
            allow_redirects=True
        )
        response.raise_for_status()
        
        # Update URL after redirects
        final_url = response.url
        logging.debug(f"Final URL after redirects: {final_url}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        handler = get_publisher_handler(final_url)  # Use final URL for handler selection
        doi, abstract = handler.extract_doi_and_abstract(soup, final_url)
        
        if doi:
            logging.debug(f"DOI found: {doi}")
        else:
            logging.debug("No DOI found")
            
        result.update({
            'success': True,
            'doi_found': bool(doi),
            'abstract_found': bool(abstract),
            'doi': doi,
            'abstract': abstract,
            'extraction_method': handler.__class__.__name__,
            'final_url': final_url
        })
        
    except requests.exceptions.RequestException as e:
        result.update({
            'error': str(e)
        })
        logging.error(f"Error processing URL {url}: {str(e)}")
    
    return result
class WileyHandler(PublisherHandler):
    """Handler for Wiley Online Library articles"""
    
    def extract_doi_and_abstract(self, soup: BeautifulSoup, url: str) -> Tuple[Optional[str], Optional[str]]:
        doi = self._extract_doi(soup, url)
        abstract = self._extract_abstract(soup)
        return doi, abstract

    def _extract_doi(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        # Method 1: DOI access div
        doi_div = soup.select_one('.doi-access')
        if doi_div:
            match = re.search(r'10\.\d{4}/[^\s]+', doi_div.get_text())
            if match:
                return match.group(0)
        
        # Method 2: Meta tags
        doi_tag = soup.find('meta', {'name': 'citation_doi'})
        if doi_tag:
            return doi_tag.get('content')
        
        return None

    def _extract_abstract(self, soup: BeautifulSoup) -> Optional[str]:
        abstract_sections = [
            soup.find('div', {'class': 'article-section__content'}),
            soup.find('section', {'class': 'article-section__abstract'}),
            soup.find('div', {'class': 'abstract-group'})
        ]
        
        for section in abstract_sections:
            if section:
                return section.get_text(strip=True)
        
        return None

class PubMedHandler(PublisherHandler):
    """Handler for PubMed/NCBI articles"""
    
    def extract_doi_and_abstract(self, soup: BeautifulSoup, url: str) -> Tuple[Optional[str], Optional[str]]:
        doi = self._extract_doi(soup, url)
        abstract = self._extract_abstract(soup)
        return doi, abstract

    def _extract_doi(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        # Method 1: Identifier section
        doi_elem = soup.select_one('.identifier.doi')
        if doi_elem:
            match = re.search(r'10\.\d{4}/[^\s]+', doi_elem.get_text())
            if match:
                return match.group(0)
        
        # Method 2: Citation section
        citation = soup.find('div', {'class': 'cite-this'})
        if citation:
            match = re.search(r'10\.\d{4}/[^\s]+', citation.get_text())
            if match:
                return match.group(0)
                
        return None

    def _extract_abstract(self, soup: BeautifulSoup) -> Optional[str]:
        abstract_div = soup.find('div', {'class': 'abstract'})
        if abstract_div:
            # Remove labels like "Background:", "Methods:", etc.
            paragraphs = abstract_div.find_all(['p', 'div'], {'class': 'abstract-content'})
            if paragraphs:
                return ' '.join(p.get_text(strip=True) for p in paragraphs)
        return None

class PlosHandler(PublisherHandler):
    """Handler for PLOS journals"""
    
    def extract_doi_and_abstract(self, soup: BeautifulSoup, url: str) -> Tuple[Optional[str], Optional[str]]:
        doi = self._extract_doi(soup, url)
        abstract = self._extract_abstract(soup)
        return doi, abstract

    def _extract_doi(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        # PLOS typically has DOI in meta tags
        doi_tag = soup.find('meta', {'name': 'citation_doi'})
        if doi_tag:
            return doi_tag.get('content')
        
        # Backup: Look in article info section
        article_info = soup.find('div', {'class': 'articleinfo'})
        if article_info:
            match = re.search(r'10\.\d{4}/[^\s]+', article_info.get_text())
            if match:
                return match.group(0)
        
        return None

    def _extract_abstract(self, soup: BeautifulSoup) -> Optional[str]:
        abstract_section = soup.find('div', {'id': 'abstract'})
        if abstract_section:
            # Remove section labels if present
            for label in abstract_section.find_all('strong'):
                label.decompose()
            return abstract_section.get_text(strip=True)
        return None

class CellHandler(PublisherHandler):
    """Handler for Cell Press journals"""
    
    def extract_doi_and_abstract(self, soup: BeautifulSoup, url: str) -> Tuple[Optional[str], Optional[str]]:
        doi = self._extract_doi(soup, url)
        abstract = self._extract_abstract(soup)
        return doi, abstract

    def _extract_doi(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        # Method 1: Meta tags
        doi_tag = soup.find('meta', {'name': 'citation_doi'})
        if doi_tag:
            return doi_tag.get('content')
        
        # Method 2: DOI text
        doi_div = soup.find('div', {'class': 'doi'})
        if doi_div:
            match = re.search(r'10\.\d{4}/[^\s]+', doi_div.get_text())
            if match:
                return match.group(0)
        
        return None

    def _extract_abstract(self, soup: BeautifulSoup) -> Optional[str]:
        sections = [
            soup.find('div', {'class': 'abstract'}),
            soup.find('section', {'class': 'abstract'}),
            soup.find('div', {'id': 'abstracts'})
        ]
        
        for section in sections:
            if section:
                # Remove any summary/highlight boxes
                for highlights in section.find_all('div', {'class': 'highlights'}):
                    highlights.decompose()
                return section.get_text(strip=True)
        
        return None

class ScienceHandler(PublisherHandler):
    """Handler for Science family journals"""
    
    def extract_doi_and_abstract(self, soup: BeautifulSoup, url: str) -> Tuple[Optional[str], Optional[str]]:
        doi = self._extract_doi(soup, url)
        abstract = self._extract_abstract(soup)
        return doi, abstract

    def _extract_doi(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        # Method 1: Meta tags
        for name in ['citation_doi', 'dc.Identifier', 'dc.identifier']:
            tag = soup.find('meta', {'name': name})
            if tag and tag.get('content'):
                return tag.get('content')
        
        # Method 2: DOI in article info
        article_info = soup.find('div', {'class': 'article__info'})
        if article_info:
            match = re.search(r'10\.\d{4}/[^\s]+', article_info.get_text())
            if match:
                return match.group(0)
        
        return None

    def _extract_abstract(self, soup: BeautifulSoup) -> Optional[str]:
        abstract_sections = [
            soup.find('div', {'class': 'abstract'}),
            soup.find('div', {'class': 'section abstract'}),
            soup.find('section', {'class': 'abstract'})
        ]
        
        for section in abstract_sections:
            if section:
                # Remove any article impact statement
                impact = section.find('div', {'class': 'article-impact'})
                if impact:
                    impact.decompose()
                return section.get_text(strip=True)
        
        return None

class OxfordHandler(PublisherHandler):
    """Handler for Oxford Academic journals"""
    
    def extract_doi_and_abstract(self, soup: BeautifulSoup, url: str) -> Tuple[Optional[str], Optional[str]]:
        doi = self._extract_doi(soup, url)
        abstract = self._extract_abstract(soup)
        return doi, abstract

    def _extract_doi(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        # Method 1: Meta tags
        doi_tag = soup.find('meta', {'name': 'citation_doi'})
        if doi_tag:
            return doi_tag.get('content')
        
        # Method 2: Article header
        header = soup.find('header', {'class': 'article-header'})
        if header:
            match = re.search(r'10\.\d{4}/[^\s]+', header.get_text())
            if match:
                return match.group(0)
        
        return None

    def _extract_abstract(self, soup: BeautifulSoup) -> Optional[str]:
        sections = [
            soup.find('section', {'class': 'abstract'}),
            soup.find('div', {'class': 'abstract'}),
            soup.find('div', {'class': 'article-abstract'})
        ]
        
        for section in sections:
            if section:
                return section.get_text(strip=True)
        
        return None

class JamaHandler(PublisherHandler):
    """Handler for JAMA Network journals"""
    
    def extract_doi_and_abstract(self, soup: BeautifulSoup, url: str) -> Tuple[Optional[str], Optional[str]]:
        doi = self._extract_doi(soup, url)
        abstract = self._extract_abstract(soup)
        return doi, abstract

    def _extract_doi(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        # Method 1: Citation info
        citation = soup.find('div', {'class': 'citation-doi'})
        if citation:
            match = re.search(r'10\.\d{4}/[^\s]+', citation.get_text())
            if match:
                return match.group(0)
        
        # Method 2: Meta tags
        doi_tag = soup.find('meta', {'name': 'citation_doi'})
        if doi_tag:
            return doi_tag.get('content')
        
        return None

    def _extract_abstract(self, soup: BeautifulSoup) -> Optional[str]:
        sections = [
            soup.find('div', {'class': 'abstract-content'}),
            soup.find('div', {'class': 'article-full-text'}),
            soup.find('div', {'class': 'abstract'})
        ]
        
        for section in sections:
            if section:
                # Remove sub-headers if present
                for header in section.find_all(['h3', 'h4']):
                    header.decompose()
                return section.get_text(strip=True)
        
        return None
class ScienceDirectHandler(PublisherHandler):
    """Handler for ScienceDirect articles"""
    
    def extract_doi_and_abstract(self, soup: BeautifulSoup, url: str) -> Tuple[Optional[str], Optional[str]]:
        doi = self._extract_doi(soup, url)
        abstract = self._extract_abstract(soup)
        return doi, abstract

    def _extract_doi(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        doi_tag = soup.find('meta', {'name': 'citation_doi'})
        if doi_tag:
            return doi_tag.get('content')
        
        pii = soup.select_one('meta[name="citation_pii"]')
        if pii and pii.get('content'):
            return f"10.1016/{pii['content']}"
        
        return None

    def _extract_abstract(self, soup: BeautifulSoup) -> Optional[str]:
        abstract_sections = [
            soup.find('div', {'class': 'abstract author'}),
            soup.find('div', {'id': 'abs0010'}),
            soup.find('section', {'class': 'abstract'}),
            soup.find('div', {'class': 'abstract'})
        ]
        
        for section in abstract_sections:
            if section:
                text = section.get_text(strip=True)
                return re.sub(r'^Abstract\s*', '', text)
        
        return None

class PnasHandler(PublisherHandler):
    """Handler for PNAS articles"""
    
    def extract_doi_and_abstract(self, soup: BeautifulSoup, url: str) -> Tuple[Optional[str], Optional[str]]:
        doi = self._extract_doi(soup, url)
        abstract = self._extract_abstract(soup)
        return doi, abstract

    def _extract_doi(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        doi_link = soup.find('a', {'class': 'doi'})
        if doi_link:
            match = re.search(r'10\.\d{4}/[-._;()/:\w]+', doi_link.text)
            if match:
                return match.group(0)
        
        doi_tag = soup.find('meta', {'name': 'citation_doi'})
        if doi_tag:
            return doi_tag.get('content')
        
        return None

    def _extract_abstract(self, soup: BeautifulSoup) -> Optional[str]:
        abstract_section = soup.find('div', {'id': ['abstract', 'executive-summary-abstract']})
        if abstract_section:
            abstract_text = abstract_section.find('div', {'role': 'paragraph'})
            if abstract_text:
                return abstract_text.get_text(strip=True)
        return None

def extract_url_from_comment(comment):
    """Extract URLs from comment text"""
    if not comment or pd.isna(comment):
        return None
        
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

def get_publisher_handler(url: str) -> PublisherHandler:
    """Get appropriate handler for the given URL"""
    domain = urlparse(url).netloc.lower()
    return PublisherHandler.get_handler(domain)

def process_url(url: str, category: str, comment: Optional[str] = None) -> Dict[str, Any]:
    """Process single URL with error handling and result tracking"""
    result = {
        'url': url,
        'success': False,
        'doi_found': False,
        'abstract_found': False,
        'doi': None,
        'abstract': None,
        'extraction_method': None,
        'error': None,
        'source': 'main_url'
    }
    
    # Add rate limiting
    time.sleep(1)
    
    # First try comment URL if available
    if comment:
        comment_url = extract_url_from_comment(comment)
        if comment_url:
            try:
                headers = {'User-Agent': USER_AGENT}
                response = requests.get(comment_url, timeout=TIMEOUT, headers=headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                handler = get_publisher_handler(comment_url)
                doi, abstract = handler.extract_doi_and_abstract(soup, comment_url)
                
                if doi or abstract:
                    return {
                        'url': comment_url,
                        'success': True,
                        'doi_found': bool(doi),
                        'abstract_found': bool(abstract),
                        'doi': doi,
                        'abstract': abstract,
                        'extraction_method': handler.__class__.__name__,
                        'error': None,
                        'source': 'comment_url'
                    }
            except requests.exceptions.RequestException as e:
                logging.warning(f"Failed to process comment URL {comment_url}: {str(e)}")
    
    # Try main URL
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, timeout=TIMEOUT, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        handler = get_publisher_handler(url)
        doi, abstract = handler.extract_doi_and_abstract(soup, url)
        
        result.update({
            'success': True,
            'doi_found': bool(doi),
            'abstract_found': bool(abstract),
            'doi': doi,
            'abstract': abstract,
            'extraction_method': handler.__class__.__name__
        })
        
    except requests.exceptions.RequestException as e:
        result.update({
            'error': str(e)
        })
    
    return result

def categorize_url(row):
    """Categorize URLs into predefined categories based on domain patterns"""
    domain = str(row.get('domain', '')).lower()
    
    for category, domains in DOMAINS.items():
        if any(d in domain for d in domains):
            return category
    
    return 'unknown'

def analyze_domains(input_file: str) -> Dict[str, Any]:
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
                'abstract_found': 0,
                'comment_urls_used': 0,
                'errors': defaultdict(int),
                'publisher_stats': defaultdict(int)
            })
        }
        
        # Process each category
        for category in ['repo', 'scientific', 'news']:
            category_df = df[df['category'] == category]
            
            # Get top N domains
            top_domains = category_df['domain'].value_counts().head(TOP_N_DOMAINS).index
            category_urls = category_df[category_df['domain'].isin(top_domains)]
            
            logging.info(f"Processing {len(category_urls)} URLs for category: {category}")
            
            # Apply testing interval if in testing mode
            if TESTING:
                category_urls = category_urls.iloc[::TEST_INTERVAL]
            
            # Process URLs with progress bar
            with tqdm(total=len(category_urls), desc=f"Processing {category}") as pbar:
                for _, row in category_urls.iterrows():
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
                    if result['abstract_found']:
                        stats['abstract_found'] += 1
                    if result['source'] == 'comment_url':
                        stats['comment_urls_used'] += 1
                    if result['error']:
                        stats['errors'][type(result['error']).__name__] += 1
                    if result['extraction_method']:
                        stats['publisher_stats'][result['extraction_method']] += 1
                    
                    pbar.update(1)
        
        # Generate detailed reports
        _generate_reports(results)
        
        return results
        
    except Exception as e:
        logging.error(f"Error in analyze_domains: {str(e)}")
        raise

def _generate_reports(results: Dict[str, Any]) -> None:
    """Generate detailed analysis reports"""
    # Process results into DataFrames
    processed_df = pd.DataFrame(results['processed'])
    
    # Generate category statistics
    stats_df = pd.DataFrame([
        {
            'category': cat,
            'total_urls': stats['total'],
            'successful_scrapes': stats['successful'],
            'doi_found': stats['doi_found'],
            'abstract_found': stats['abstract_found'],
            'comment_urls_used': stats['comment_urls_used'],
            'success_rate': stats['successful'] / stats['total'] if stats['total'] > 0 else 0,
            'doi_rate': stats['doi_found'] / stats['successful'] if stats['successful'] > 0 else 0,
            'abstract_rate': stats['abstract_found'] / stats['successful'] if stats['successful'] > 0 else 0,
            'most_common_error': max(stats['errors'].items(), key=lambda x: x[1])[0] if stats['errors'] else None,
            'top_publisher': max(stats['publisher_stats'].items(), key=lambda x: x[1])[0] if stats['publisher_stats'] else None
        }
        for cat, stats in results['stats'].items()
    ])
    
    # Save detailed results
    processed_df.to_csv(f'{RESULTS_DIR}/processed_urls.csv', index=False)
    stats_df.to_csv(f'{RESULTS_DIR}/scraping_statistics.csv', index=False)
    
    # Save category-specific results
    for category in ['repo', 'scientific', 'news']:
        category_results = processed_df[processed_df['category'] == category]
        category_results.to_csv(f'{RESULTS_DIR}/{category}_results.csv', index=False)
    
    # Generate publisher performance report
    publisher_stats = defaultdict(lambda: {
        'total_attempts': 0,
        'successful_dois': 0,
        'successful_abstracts': 0
    })
    
    for result in results['processed']:
        if result['extraction_method']:
            stats = publisher_stats[result['extraction_method']]
            stats['total_attempts'] += 1
            if result['doi_found']:
                stats['successful_dois'] += 1
            if result['abstract_found']:
                stats['successful_abstracts'] += 1
    
    publisher_df = pd.DataFrame([
        {
            'publisher': publisher,
            'total_attempts': stats['total_attempts'],
            'doi_success_rate': stats['successful_dois'] / stats['total_attempts'] if stats['total_attempts'] > 0 else 0,
            'abstract_success_rate': stats['successful_abstracts'] / stats['total_attempts'] if stats['total_attempts'] > 0 else 0
        }
        for publisher, stats in publisher_stats.items()
    ])
    
    publisher_df.to_csv(f'{RESULTS_DIR}/publisher_performance.csv', index=False)

def main():
    """Main execution function"""
    logging.info("Starting academic paper scraping analysis")
    if TESTING:
        logging.info(f"Running in TEST mode - processing every {TEST_INTERVAL}th link")
        logging.info(f"Analyzing top {TOP_N_DOMAINS} domains per category")
    
    try:
        results = analyze_domains(INPUT_FILE)
        logging.info("Analysis complete - check scraping_results directory for reports")
        
        # Print summary statistics
        total_processed = len(results['processed'])
        successful_dois = sum(1 for r in results['processed'] if r['doi_found'])
        successful_abstracts = sum(1 for r in results['processed'] if r['abstract_found'])
        
        print(f"\nProcessing Summary:")
        print(f"Total URLs processed: {total_processed}")
        print(f"DOIs found: {successful_dois} ({successful_dois/total_processed*100:.1f}%)")
        print(f"Abstracts found: {successful_abstracts} ({successful_abstracts/total_processed*100:.1f}%)")
        
    except Exception as e:
        logging.error(f"Fatal error during analysis: {str(e)}")
        raise

if __name__ == "__main__":
    main()