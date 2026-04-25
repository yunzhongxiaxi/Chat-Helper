from typing import Optional
import requests
from bs4 import BeautifulSoup
import json

class WebSearchTool:
    def __init__(self):
        self.search_api_key = None  # 可配置搜索 API（如 SerpAPI、Google Custom Search）

    def search(self, query: str, num_results: int = 3) -> str:
        """搜索实时信息

        Args:
            query: 搜索关键词
            num_results: 返回结果数量

        Returns:
            搜索结果摘要
        """
        try:
            if self.search_api_key:
                return self._search_with_api(query, num_results)
            else:
                return self._search_with_duckduckgo(query, num_results)
        except Exception as e:
            return f"搜索失败: {str(e)}"

    def _search_with_duckduckgo(self, query: str, num_results: int) -> str:
        """使用 DuckDuckGo 搜索（无需 API key）"""
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.post(url, data=params, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        for result in soup.find_all('div', class_='result')[:num_results]:
            title_elem = result.find('a', class_='result__a')
            snippet_elem = result.find('a', class_='result__snippet')

            if title_elem and snippet_elem:
                results.append({
                    "title": title_elem.get_text(strip=True),
                    "snippet": snippet_elem.get_text(strip=True),
                    "url": title_elem.get('href', '')
                })

        if not results:
            return "未找到相关信息"

        summary = "搜索结果：\n"
        for i, r in enumerate(results, 1):
            summary += f"{i}. {r['title']}\n   {r['snippet']}\n"

        return summary

    def _search_with_api(self, query: str, num_results: int) -> str:
        """使用搜索 API（需要配置 API key）"""
        # 可扩展支持 SerpAPI、Google Custom Search 等
        pass

def get_search_tool_definition() -> dict:
    """返回 Function Calling 的 Tool 定义"""
    return {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "搜索互联网获取实时信息。当对话涉及最新事件、新闻、天气、实时数据等需要最新信息时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，例如：'今天北京天气'、'最新科技新闻'"
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "返回结果数量，默认 3",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    }

web_search_tool = WebSearchTool()
