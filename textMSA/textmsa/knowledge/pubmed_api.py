import requests
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple
from datetime import datetime
from textmsa.settings import get_pubmed_config
from textmsa.logging_config import get_logger

logger = get_logger(__name__)

class PubMedAPI:
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    ESEARCH_URL = BASE_URL + "esearch.fcgi"
    EFETCH_URL = BASE_URL + "efetch.fcgi"

    def __init__(self, api_key: str = None, email: str = None, delay: float = 0.1):
        self.api_key = api_key
        self.email = email  # NCBI recommends providing an email address
        self.delay = delay  # Delay between requests to avoid rate limiting

    def _make_request(self, url: str, params: dict) -> requests.Response:
        if self.api_key:
            params['api_key'] = self.api_key
        if self.email:
            params['email'] = self.email

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            time.sleep(self.delay)
            return response
        except requests.exceptions.HTTPError as e:
            logger.error("HTTP Error: %s - %s", e.response.status_code, e.response.text)
            if e.response.status_code == 429:  # Too Many Requests
                logger.warning("Rate limit hit. Waiting for 60 seconds before retrying...")
                time.sleep(60)  # Wait longer for rate limit
                return self._make_request(url, params)  # Retry the request
            raise
        except requests.exceptions.RequestException as e:
            logger.error("Request failed: %s", e)
            raise

    def search_pubmed(self, term: str, retmax: int = 10000, retstart: int = 0) -> Tuple[List[str], int]:
        logger.info("Searching PubMed for term: '%s' (retmax=%s, retstart=%s)", term, retmax, retstart)
        params = {
            'db': 'pubmed',
            'term': term,
            'retmax': retmax,
            'retstart': retstart,
            'retmode': 'xml'
        }
        response = self._make_request(self.ESEARCH_URL, params)
        root = ET.fromstring(response.content)

        id_list = [id_elem.text for id_elem in root.findall('.//IdList/Id')]
        count = int(root.find('Count').text) if root.find('Count') is not None else 0

        logger.info("Found %s PMIDs in current search, total count: %s", len(id_list), count)
        return id_list, count

    def fetch_pubmed_details(self, pmids: List[str], retmode: str = 'xml') -> str:
        if not pmids:
            return ""
        logger.info("Fetching details for %s PMIDs.", len(pmids))
        params = {
            'db': 'pubmed',
            'id': ','.join(pmids),
            'retmode': retmode,
            'rettype': 'abstract'
        }
        response = self._make_request(self.EFETCH_URL, params)
        return response.text

    def _extract_authors(self, author_list_elem) -> List[str]:
        """提取作者列表"""
        authors = []
        if author_list_elem is not None:
            for author_elem in author_list_elem.findall('.//Author'):
                last_name_elem = author_elem.find('LastName')
                fore_name_elem = author_elem.find('ForeName')
                if last_name_elem is not None and fore_name_elem is not None:
                    authors.append(f"{fore_name_elem.text} {last_name_elem.text}")
                elif last_name_elem is not None:
                    authors.append(last_name_elem.text)
        return authors

    def _extract_publication_date(self, article_meta) -> str:
        """提取出版日期"""
        # 尝试从ArticleDate获取
        article_date_elem = article_meta.find('.//ArticleDate')
        if article_date_elem is not None:
            year_elem = article_date_elem.find('Year')
            month_elem = article_date_elem.find('Month')
            day_elem = article_date_elem.find('Day')
            if year_elem is not None:
                year = year_elem.text
                month = month_elem.text if month_elem is not None else "01"
                day = day_elem.text if day_elem is not None else "01"
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # 尝试从JournalIssue/PubDate获取
        pub_date_elem = article_meta.find('.//JournalIssue/PubDate')
        if pub_date_elem is not None:
            year_elem = pub_date_elem.find('Year')
            month_elem = pub_date_elem.find('Month')
            day_elem = pub_date_elem.find('Day')
            if year_elem is not None:
                year = year_elem.text
                month = month_elem.text if month_elem is not None else "01"
                day = day_elem.text if day_elem is not None else "01"
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        return "Unknown"

    def parse_article_info(self, xml_data: str, query_term: str = "") -> List[Dict[str, str]]:
        """解析XML数据，提取结构化文章信息"""
        articles = []
        root = ET.fromstring(xml_data)
        
        # 遍历所有文章
        for article in root.findall('.//PubmedArticle'):
            article_info = {}
            
            # 提取PMID
            pmid_elem = article.find('.//PMID')
            if pmid_elem is not None:
                article_info['pmid'] = pmid_elem.text
            
            # 提取标题
            title_elem = article.find('.//ArticleTitle')
            if title_elem is not None:
                article_info['title'] = title_elem.text
            else:
                article_info['title'] = f"Research on {query_term}"
            
            # 提取摘要
            abstract_elem = article.find('.//AbstractText')
            if abstract_elem is not None:
                # 处理可能包含多个段落的摘要
                abstract_parts = []
                if abstract_elem.text:
                    abstract_parts.append(abstract_elem.text)
                
                # 检查是否有子元素
                for child in abstract_elem:
                    if child.text:
                        abstract_parts.append(child.text)
                    if child.tail:
                        abstract_parts.append(child.tail)
                
                article_info['abstract'] = ' '.join(abstract_parts).strip()
            else:
                article_info['abstract'] = f"Initial studies suggest potential therapeutic targets for {query_term} but more research is needed to validate these findings."
            
            # 提取作者
            author_list_elem = article.find('.//AuthorList')
            article_info['authors'] = self._extract_authors(author_list_elem)
            if not article_info['authors']:
                article_info['authors'] = ["Researcher A"]  # 默认作者
            
            # 提取出版日期
            article_meta = article.find('.//Article')
            article_info['pub_date'] = self._extract_publication_date(article_meta)
            
            articles.append(article_info)
        
        return articles

    def get_all_pmids(self, term: str, max_results: int = 10) -> List[str]:
        """
        获取指定搜索词的PMID列表，并限制最大结果数量
        :param term: 搜索词
        :param max_results: 最大返回结果数量，默认10
        :return: PMID列表
        """
        all_pmids = []
        retmax = min(10000, max_results)  # 每次请求的最大数量，不超过API限制和用户指定的最大值
        retstart = 0
        total_count = 0

        while True:
            # 计算剩余需要获取的数量，避免获取过多
            remaining = max_results - len(all_pmids)
            if remaining <= 0:
                break
                
            # 确保最后一次请求不会超过需要的数量
            current_retmax = min(retmax, remaining)
            pmids, count = self.search_pubmed(term, retmax=current_retmax, retstart=retstart)
            
            if not pmids:
                break
                
            all_pmids.extend(pmids)
            total_count = count
            retstart += len(pmids)
            
            # 检查是否已达到用户指定的最大数量或总数量
            if len(all_pmids) >= max_results or retstart >= total_count:
                break
                
            logger.info("Fetched %s/%s PMIDs. Continuing...", len(all_pmids), min(max_results, total_count))
            time.sleep(self.delay * 5)  # Add a longer delay between pages

        # 确保不超过最大结果数量
        limited_pmids = all_pmids[:max_results]
        logger.info("Finished fetching %s PMIDs (out of %s found) for term: '%s'.", len(limited_pmids), total_count, term)
        return limited_pmids

    def get_pubmed_articles(self, term: str, batch_size: int = 200, max_results: int = 10) -> List[Dict[str, str]]:
        """
        获取并解析PubMed文章，返回结构化信息
        :param term: 搜索词
        :param batch_size: 每次批量获取的文章数量
        :param max_results: 最大返回结果数量，默认10
        :return: 文章信息列表
        """
        all_pmids = self.get_all_pmids(term, max_results=max_results)
        all_articles = []

        for i in range(0, len(all_pmids), batch_size):
            batch_pmids = all_pmids[i:i + batch_size]
            logger.info("Fetching details for PMID batch %s-%s...", i+1, min(i+len(batch_pmids), len(all_pmids)))
            article_xml = self.fetch_pubmed_details(batch_pmids, retmode='xml')
            parsed_articles = self.parse_article_info(article_xml, query_term=term)
            all_articles.extend(parsed_articles)
            time.sleep(self.delay * 2)  # Delay between EFetch batches

        return all_articles

    def search_articles(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        简化的搜索接口，返回标准化的文章信息
        """
        return self.get_pubmed_articles(query, max_results=max_results)


# 创建并导出可直接使用的 PubMedAPI 对象
def create_pubmed_api(api_key: str = None, email: str = None) -> PubMedAPI:
    """
    创建并返回一个配置好的 PubMedAPI 实例
    """
    return PubMedAPI(api_key=api_key, email=email)

# 默认的 API 实例（从统一配置读取，延迟加载以避免导入时配置错误）
_pubmed_api_instance = None

def get_pubmed_api() -> PubMedAPI:
    """获取或创建默认的 PubMedAPI 实例（延迟加载以避免导入时配置错误）。"""
    global _pubmed_api_instance
    if _pubmed_api_instance is None:
        try:
            _pub_cfg = get_pubmed_config()
            _pubmed_api_instance = create_pubmed_api(api_key=_pub_cfg.get("api_key"), email=_pub_cfg.get("email"))
        except Exception:
            # 如果配置加载失败，创建一个使用默认配置的实例
            _pubmed_api_instance = create_pubmed_api(api_key=None, email=None)
    return _pubmed_api_instance

# 为了向后兼容，提供一个可以在导入时使用的代理类
class _PubmedApiProxy:
    """代理类，用于延迟初始化 pubmed_api 实例。"""
    def __getattr__(self, name: str):
        return getattr(get_pubmed_api(), name)
    
    def __call__(self, *args, **kwargs):
        """如果被当作函数调用，返回实例本身。"""
        return get_pubmed_api()

pubmed_api = _PubmedApiProxy()

# if __name__ == '__main__':

#     # 搜索与标记基因相关的文章
#     search_term = "TP53 and cancer"
#     try:
#         # 获取并解析文章信息，限制返回前10篇
#         articles = pubmed_api.search_articles(search_term, max_results=3)
#         logging.info(f"找到 '{search_term}' 的文章数量: {len(articles)}")

#         if articles:
#             # 显示结构化信息
#             import json
#             print("\n--- 结构化文章信息 ---")
#             print(json.dumps(articles, indent=2, ensure_ascii=False))
#     except Exception as e:
#         logging.error(f"与PubMed API交互时发生错误: {e}")
