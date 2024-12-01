import re
import pandas as pd
import sys
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from datetime import datetime
from urllib.parse import urlparse

class Logger:
    def __init__(self):
        self.terminal = sys.stdout
        self.log_file = open(f"specific_scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", "a")

    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.log_file.flush()  # Ensure immediate write to file
        
    def flush(self):
        self.terminal.flush()
        self.log_file.flush()
        
    def __getattr__(self, attr):
        return getattr(self.terminal, attr)

# Redirect stdout and stderr to our Logger
sys.stdout = Logger()
sys.stderr = sys.stdout

def nature_scraper(url):
    """Scrape Nature articles for DOI, title and abstract.
    
    Args:
        url (str): URL to Nature article
        
    Returns:
        dict: Article metadata containing DOI, title and abstract
    """
    result = {"url": url, "doi": None, "title": None, "abstract": None}
    
    try:
        # Get the page content
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract DOI - try multiple patterns
        doi = None
        
        # Pattern 1: DOI in bibliographic info with specific HTML structure
        doi_item = soup.find('li', class_='c-bibliographic-information__list-item--full-width')
        if doi_item:
            # Try multiple DOI patterns in bibliographic info
            doi_patterns = [
                r'https://doi.org/[\w\.-]+/?',
                r'doi.org/[\w\.-]+/?',
                r'10\.\d{4,}/[\w\.-]+/?'
            ]
            for pattern in doi_patterns:
                doi_match = re.search(pattern, doi_item.text)
                if doi_match:
                    doi = doi_match.group(0)
                    break
        
        # Pattern 2: Check cite-as section
        if not doi:
            cite_section = soup.find('div', id='citeas')
            if cite_section:
                # Try multiple DOI patterns in cite-as section
                for pattern in [
                    r'https://doi.org/[\w\.-]+/?',
                    r'doi.org/[\w\.-]+/?',
                    r'10\.\d{4,}/[\w\.-]+/?',
                    r'DOI:\s*(10\.\d{4,}/[\w\.-]+/?)'
                ]:
                    doi_match = re.search(pattern, cite_section.text)
                    if doi_match:
                        doi = doi_match.group(0) if not 'DOI:' in pattern else doi_match.group(1)
                        break
        
        # Pattern 3: DOI in italics
        if not doi:
            doi_elem = soup.find('em', string=re.compile(r'doi:', re.I))
            if doi_elem:
                for pattern in [
                    r'https://doi.org/[\w\.-]+/?',
                    r'doi.org/[\w\.-]+/?',
                    r'10\.\d{4,}/[\w\.-]+/?'
                ]:
                    doi_match = re.search(pattern, doi_elem.text)
                    if doi_match:
                        doi = doi_match.group(0)
                        break
                    
        # Pattern 4: DOI in URL
        if not doi:
            url_patterns = [
                r'doi/(?:full/|abs/)?(\d+\.\d+/[^/\s]+)',
                r'articles/(\d+\.\d+/[^/\s]+)',
                r'articles/doi/(\d+\.\d+/[^/\s]+)'
            ]
            for pattern in url_patterns:
                doi_match = re.search(pattern, url)
                if doi_match:
                    doi = doi_match.group(1)
                    break
        
        if doi:
            # Clean up DOI by removing any prefixes
            doi = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', doi)
            result['doi'] = doi.rstrip('/')
            
            # Try getting metadata from Semantic Scholar
            try:
                ss_url = f"https://api.semanticscholar.org/v1/paper/DOI:{result['doi']}"
                ss_response = requests.get(ss_url)
                if ss_response.status_code == 200:
                    paper_data = ss_response.json()
                    result['title'] = paper_data.get('title')
                    result['abstract'] = paper_data.get('abstract')
            except Exception as e:
                print(f"Failed to get Semantic Scholar data: {str(e)}")
        
        # If Semantic Scholar failed, try parsing from HTML
        if not result['title']:
            # Try finding title in HTML
            title_elem = soup.find(['h1', 'h2'], class_=re.compile(r'article.*title', re.I))
            if title_elem:
                result['title'] = title_elem.text.strip()
            else:
                # Try finding title in article header
                article_header = soup.find('div', class_='c-article-header')
                if article_header:
                    title_elem = article_header.find('h1', class_='c-article-title')
                    if title_elem:
                        result['title'] = title_elem.text.strip()
        
        if not result['abstract']:
            # Try finding abstract in HTML
            abstract_section = soup.find('div', id='Abs1-content')
            if abstract_section:
                abstract_p = abstract_section.find('p')
                if abstract_p:
                    result['abstract'] = abstract_p.text.strip()
            
            # Try alternate abstract pattern
            if not result['abstract']:
                alt_abstract_section = soup.find('section', attrs={'data-title': 'Abstract'})
                if alt_abstract_section:
                    abstract_content = alt_abstract_section.find('div', id=lambda x: x and x.endswith('-content'))
                    if abstract_content:
                        abstract_p = abstract_content.find('p')
                        if abstract_p:
                            result['abstract'] = abstract_p.text.strip()
        return result
        
    except Exception as e:
        print(f"Error scraping Nature article {url}: {str(e)}")
        return result
    
def sciencealert_scraper(url):
    """Scrape ScienceAlert articles for DOI, title and abstract.
    
    Args:
        url (str): URL to ScienceAlert article
        
    Returns:
        dict: Article metadata containing DOI, title and abstract
    """
    result = {"url": url, "doi": None, "title": None, "abstract": None}
    
    try:
        # Get the page content
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the article content div
        article_content = soup.find('div', class_='post-content')
        
        if article_content:
            # Get the last link in the article content
            links = article_content.find_all('a')
            if links:
                last_link = links[-1]['href']
                
                # Try multiple patterns to extract DOI from URL
                doi_patterns = [
                    r'10\.\d{4,9}/[-._;()/:a-z0-9A-Z]+',  # Standard CrossRef pattern
                    r'doi\.org/10\.\d{4,9}/[-._;()/:a-z0-9A-Z]+',
                    r'dx\.doi\.org/10\.\d{4,9}/[-._;()/:a-z0-9A-Z]+',
                    r'doi:10\.\d{4,9}/[-._;()/:a-z0-9A-Z]+'
                ]
                
                for pattern in doi_patterns:
                    doi_match = re.search(pattern, last_link)
                    if doi_match:
                        result['doi'] = doi_match.group().replace('doi.org/', '').replace('dx.doi.org/', '').replace('doi:', '').rstrip('/')
                        break
                    
                if result['doi']:
                    # Try getting metadata from Semantic Scholar
                    try:
                        ss_url = f"https://api.semanticscholar.org/v1/paper/DOI:{result['doi']}"
                        ss_response = requests.get(ss_url)
                        if ss_response.status_code == 200:
                            paper_data = ss_response.json()
                            result['title'] = paper_data.get('title')
                            result['abstract'] = paper_data.get('abstract')
                    except Exception as e:
                        print(f"Failed to get Semantic Scholar data: {str(e)}")
                
                # If Semantic Scholar failed, try parsing from paper HTML
                if not result['title'] or not result['abstract']:
                    paper_response = requests.get(last_link)
                    paper_soup = BeautifulSoup(paper_response.text, 'html.parser')
                    
                    if paper_soup:
                        # Try multiple patterns for title
                        if not result['title']:
                            title_elem = (
                                paper_soup.find('h1', class_=re.compile(r'article.*title', re.I)) or
                                paper_soup.find('h1', {'id': 'title'}) or
                                paper_soup.find('h1', class_='title') or
                                paper_soup.find('div', class_='article-title') or
                                paper_soup.find('h1')
                            )
                            if title_elem:
                                result['title'] = title_elem.text.strip()
                        
                        # Try multiple patterns for abstract
                        if not result['abstract']:
                            abstract_elem = (
                                paper_soup.find('div', {'id': 'abstract'}) or
                                paper_soup.find('section', {'id': 'abstract'}) or
                                paper_soup.find('div', class_='abstract') or
                                paper_soup.find('div', class_=re.compile(r'article.*abstract', re.I)) or
                                paper_soup.find('section', attrs={'data-title': 'Abstract'})
                            )
                            if abstract_elem:
                                # Try to find paragraph within abstract section
                                abstract_p = abstract_elem.find('p')
                                result['abstract'] = (abstract_p.text if abstract_p else abstract_elem.text).strip()
                
                        # Try multiple patterns to find DOI in HTML if not found in URL
                        if not result['doi']:
                            for pattern in doi_patterns:
                                doi_elem = paper_soup.find(string=re.compile(pattern))
                                if doi_elem:
                                    doi_match = re.search(pattern, doi_elem)
                                    if doi_match:
                                        result['doi'] = doi_match.group().replace('doi.org/', '').replace('dx.doi.org/', '').replace('doi:', '').rstrip('/')
                                        break
                
        return result
                
    except Exception as e:
        print(f"Error scraping ScienceAlert article {url}: {str(e)}")
        return result
    
def pubmed_scraper(url):
    """Scrape PubMed/PMC articles for DOI, title and abstract.
    
    Args:
        url (str): URL to PubMed/PMC article
        
    Returns:
        dict: Article metadata containing DOI, title and abstract
    """
    result = {"url": url, "doi": None, "title": None, "abstract": None, "pmid": None, "pmcid": None}
    
    try:
        # Extract PMID or PMCID from URL
        identifier = None
        if 'pubmed/' in url:
            identifier = url.split('pubmed/')[1].split('/')[0]
            id_type = 'pmid'
            result['pmid'] = identifier
        elif 'pmc/articles/' in url:
            identifier = url.split('pmc/articles/')[1].split('/')[0]
            id_type = 'pmcid'
            result['pmcid'] = identifier
        
        if identifier:
            # Use NCBI ID converter API
            api_url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={identifier}&format=json"
            response = requests.get(api_url)
            
            if response.status_code == 200:
                data = response.json()
                if 'records' in data and len(data['records']) > 0:
                    record = data['records'][0]
                    
                    # Get DOI if available
                    if 'doi' in record:
                        result['doi'] = record['doi']
                    
                    # Store both PMID and PMCID if available from API
                    if 'pmid' in record:
                        result['pmid'] = record['pmid']
                    if 'pmcid' in record:
                        result['pmcid'] = record['pmcid']
                    
                    # Try getting metadata from Semantic Scholar using PMID
                    pmid = record.get('pmid')
                    if pmid:
                        try:
                            ss_url = f"https://api.semanticscholar.org/v1/paper/PMID:{pmid}"
                            ss_response = requests.get(ss_url)
                            if ss_response.status_code == 200:
                                paper_data = ss_response.json()
                                result['title'] = paper_data.get('title')
                                result['abstract'] = paper_data.get('abstract')
                        except Exception as e:
                            print(f"Failed to get Semantic Scholar data: {str(e)}")
        
        # If semantic scholar didn't find title or abstract, try HTML parsing
        if not result['title'] or not result['abstract']:
            try:
                response = requests.get(url)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try to find title if missing
                if not result['title']:
                    # Look for title in h1 tag
                    title_tag = soup.find('h1')
                    if title_tag:
                        result['title'] = title_tag.get_text().strip()
                
                # Try to find abstract if missing
                if not result['abstract']:
                    # Look for abstract section
                    abstract_section = soup.find('section', class_='abstract')
                    if abstract_section:
                        # Get the paragraph text, excluding the "Abstract" heading
                        abstract_p = abstract_section.find('p')
                        if abstract_p:
                            result['abstract'] = abstract_p.get_text().strip()
            except Exception as e:
                print(f"Error parsing HTML for {url}: {str(e)}")
        
        return result
        
    except Exception as e:
        print(f"Error scraping PubMed article {url}: {str(e)}")
        return result

def main():
    skipped_lines = []
    try:
        encodings_to_try = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'mac_roman']
        
        for encoding in encodings_to_try:
            try:
                df = pd.read_csv('urls.csv', 
                        encoding=encoding,
                        on_bad_lines='skip',
                        engine='python'
                        )
                print(f"Successfully loaded CSV using {encoding} encoding")
                break
            except UnicodeDecodeError:
                continue
            except pd.errors.ParserError as e:
                skipped_lines.extend([f"Line {i}: {str(e)}" for i in e.args[0].split('\n') if 'Skipping line' in i])
                continue
        else:
            raise Exception("Failed to read CSV with any of the attempted encodings")

    except Exception as e:
        print(f"Failed to read original CSV: {str(e)}")
        sys.exit(1)
        
    news_lines = df[df['label_voting_manual'] == 'news']
    science_lines = df[df['label_voting_manual'] == 'scientific']
    repo_lines = df[df['label_voting_manual'] == 'repo']

    print(f"Number of news lines: {len(news_lines)}")
    print(f"Number of science lines: {len(science_lines)}")
    print(f"Number of repo lines: {len(repo_lines)}")
    print(f"Total lines: {len(news_lines) + len(science_lines) + len(repo_lines)}")

    # Extract domain from URL and filter for specific labels
    df['domain'] = df['url'].apply(lambda x: urlparse(x).netloc)
    filtered_df = df[df['label_voting_manual'].isin(['news', 'repo', 'scientific'])]

    # Get domain counts for each category
    domain_counts = filtered_df.groupby(['label_voting_manual', 'domain']).size().unstack(fill_value=0)

    # Get top domain for each category
    print("\nDomain counts by category:")
    print("-" * 50)

    # Filter to keep only rows with the most common domain for each category
    filtered_domains_df = pd.DataFrame()
    for category in ['news', 'scientific', 'repo']:
        category_df = filtered_df[filtered_df['label_voting_manual'] == category]
        
        if category == 'news':
            # Get second most common domain for news
            top_domain = category_df['domain'].value_counts().index[3]
            top_count = category_df['domain'].value_counts().iloc[3]
        else:
            # Get most common domain for other categories
            top_domain = category_df['domain'].value_counts().index[0]
            top_count = category_df['domain'].value_counts().iloc[0]
            
        print(f"\nMost common {category} domain: {top_domain} ({top_count} occurrences)")
        
        # Filter for just the rows with top domain
        category_top_domain = category_df[category_df['domain'] == top_domain]
        filtered_domains_df = pd.concat([filtered_domains_df, category_top_domain])
    filtered_df = filtered_domains_df

    # Save filtered dataset with top domains for each category
    filtered_df.to_csv('domain_filtered.csv', index=False)
    print(f"\nSaved domain filtered CSV with {len(filtered_df)} rows")

    # Print unique domains and categories
    print("\nUnique domains in filtered dataset:")
    print(set(filtered_df['domain']))

    print("\nUnique categories in filtered dataset:")
    print(set(filtered_df['label_voting_manual']))

    # science_df = pd.DataFrame(columns=['id', 'category', 'title', 'url', 'identifier', 'sem_scholar_title', 'sem_scholar_abstract'])
    # pb = tqdm(total=len(filtered_df[filtered_df['label_voting_manual'] == 'scientific']), desc="Scraping science articles")
    # for idx, row in filtered_df[filtered_df['label_voting_manual'] == 'scientific'].iterrows():
    #     metadata = nature_scraper(row['url'])
        
    #     if not metadata['doi']:
    #         print(f"No identifier found for {row['url']}")
        
    #     if not metadata['title']:
    #         print(f"No title found for {row['url']}")
        
    #     if not metadata['abstract']:
    #         print(f"No abstract found for {row['url']}")
        
    #     science_row = {
    #         'id': row['id'],
    #         'category': row['label_voting_manual'],
    #         'title': row['title'],
    #         'url': row['url'],
    #         'identifier': f"DOI:{metadata['doi']}" if metadata['doi'] else '',
    #         'sem_scholar_title': metadata['title'] if metadata['title'] else '',
    #         'sem_scholar_abstract': metadata['abstract'] if metadata['abstract'] else ''
    #     }
        
    #     science_df = pd.concat([science_df, pd.DataFrame([science_row])], ignore_index=True)
    #     pb.update(1)
        
    # science_df.to_csv('scientific.csv', index=False)
    # print(f"Saved science articles CSV with {len(science_df)} rows")


    news_df = pd.DataFrame(columns=['id', 'category', 'title', 'url', 'identifier', 'sem_scholar_title', 'sem_scholar_abstract'])
    pb = tqdm(total=len(filtered_df[filtered_df['label_voting_manual'] == 'news']), desc="Scraping news articles")
    for idx, row in filtered_df[filtered_df['label_voting_manual'] == 'news'].iterrows():
        metadata = sciencealert_scraper(row['url'])
        
        if not metadata['doi']:
            print(f"No identifier found for {row['url']}")
        
        if not metadata['title']:
            print(f"No title found for {row['url']}")
        
        if not metadata['abstract']:
            print(f"No abstract found for {row['url']}")
        
        news_row = {
            'id': row['id'],
            'category': row['label_voting_manual'],
            'title': row['title'],
            'url': row['url'],
            'identifier': f"DOI:{metadata['doi']}" if metadata['doi'] else '',
            'sem_scholar_title': metadata['title'] if metadata['title'] else '',
            'sem_scholar_abstract': metadata['abstract'] if metadata['abstract'] else ''
        }
        
        news_df = pd.concat([news_df, pd.DataFrame([news_row])], ignore_index=True)
        news_df.to_csv('news.csv', index=False)
        pb.update(1)
        
    news_df.to_csv('news.csv', index=False)
    print(f"Saved news articles CSV with {len(news_df)} rows")

    repo_df = pd.DataFrame(columns=['id', 'category', 'title', 'url', 'identifier', 'sem_scholar_title', 'sem_scholar_abstract'])
    pb = tqdm(total=len(filtered_df[filtered_df['label_voting_manual'] == 'repo']), desc="Scraping repo articles")
    for idx, row in filtered_df[filtered_df['label_voting_manual'] == 'repo'].iterrows():
        metadata = pubmed_scraper(row['url'])
        
        if not metadata['doi'] and not metadata['pmid'] and not metadata['pmcid']:
            print(f"No identifier found for {row['url']}")
        
        if not metadata['title']:
            print(f"No title found for {row['url']}")
        
        if not metadata['abstract']:
            print(f"No abstract found for {row['url']}")
        
        repo_row = {
            'id': row['id'],
            'category': row['label_voting_manual'],
            'title': row['title'],
            'url': row['url'],
            'identifier': f"DOI:{metadata['doi']}" if metadata['doi'] else 
                          f"PMID:{metadata['pmid']}" if metadata['pmid'] else 
                          f"PMCID:{metadata['pmcid']}" if metadata['pmcid'] else '',
            'sem_scholar_title': metadata['title'] if metadata['title'] else '',
            'sem_scholar_abstract': metadata['abstract'] if metadata['abstract'] else ''
        }
        
        repo_df = pd.concat([repo_df, pd.DataFrame([repo_row])], ignore_index=True)
        pb.update(1)
        
    repo_df.to_csv('repo.csv', index=False)
    print(f"Saved repo articles CSV with {len(repo_df)} rows")


    # Combine dataframes
    combined_df = pd.concat([news_df, repo_df, science_df], ignore_index=True)

    # Save combined results
    combined_df.to_csv('site_specific_output.csv', index=False)
    print(f"Saved combined CSV with {len(combined_df)} rows")

if __name__ == "__main__":
    main()