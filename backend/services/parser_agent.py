from typing import List, Dict, Optional
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from io import BytesIO
from backend.services.ai_client import ai_client

class ParserAgent:
    def __init__(self):
        self.ai_client = ai_client
        self.parsers_cache_dir = Path("./data/parsers")
        self.parsers_cache_dir.mkdir(parents=True, exist_ok=True)

    def parse_xlsx_records(self, file_content: bytes, contact_id: str) -> List[Dict]:
        rows = self._read_xlsx_rows(file_content)
        header_index = self._find_xlsx_header(rows)
        if header_index is None:
            raise ValueError("未找到 XLSX 聊天记录表头")

        headers = {value.strip(): index for index, value in enumerate(rows[header_index]) if value.strip()}
        time_col = headers.get('时间')
        sender_col = headers.get('发送者身份')
        message_col = headers.get('内容')

        if time_col is None or sender_col is None or message_col is None:
            raise ValueError("XLSX 缺少必要列：时间、发送者身份、内容")

        records = []
        for row in rows[header_index + 1:]:
            timestamp = self._xlsx_cell(row, time_col)
            sender_name = self._xlsx_cell(row, sender_col)
            message = self._xlsx_cell(row, message_col)

            if not timestamp or not sender_name or not message:
                continue

            records.append({
                "timestamp": timestamp,
                "sender": "user" if sender_name.strip() in ["我", "Me", "user", "User"] else "contact",
                "message": message.strip()
            })

        if not records:
            raise ValueError("XLSX 中未解析出聊天记录")

        print(f"✓ 使用内置 XLSX 解析器成功解析 {len(records)} 条记录（零 LLM 调用）")
        return records

    def _read_xlsx_rows(self, file_content: bytes) -> List[List[str]]:
        namespace = {'a': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

        with zipfile.ZipFile(BytesIO(file_content)) as workbook:
            shared_strings = self._read_shared_strings(workbook, namespace)
            sheet_path = self._first_sheet_path(workbook)
            sheet = ET.fromstring(workbook.read(sheet_path))

        rows = []
        for row_node in sheet.findall('.//a:sheetData/a:row', namespace):
            values = []
            for cell in row_node.findall('a:c', namespace):
                column_index = self._xlsx_column_index(cell.attrib.get('r', 'A'))
                while len(values) <= column_index:
                    values.append('')
                values[column_index] = self._xlsx_cell_text(cell, shared_strings, namespace)
            rows.append(values)
        return rows

    def _read_shared_strings(self, workbook: zipfile.ZipFile, namespace: Dict[str, str]) -> List[str]:
        if 'xl/sharedStrings.xml' not in workbook.namelist():
            return []

        root = ET.fromstring(workbook.read('xl/sharedStrings.xml'))
        strings = []
        for item in root.findall('a:si', namespace):
            strings.append(''.join(text.text or '' for text in item.findall('.//a:t', namespace)))
        return strings

    def _first_sheet_path(self, workbook: zipfile.ZipFile) -> str:
        if 'xl/worksheets/sheet1.xml' in workbook.namelist():
            return 'xl/worksheets/sheet1.xml'
        for name in workbook.namelist():
            if name.startswith('xl/worksheets/') and name.endswith('.xml'):
                return name
        raise ValueError("XLSX 中未找到工作表")

    def _xlsx_cell_text(self, cell: ET.Element, shared_strings: List[str], namespace: Dict[str, str]) -> str:
        value = cell.find('a:v', namespace)
        if value is not None:
            text = value.text or ''
            if cell.attrib.get('t') == 's' and text:
                return shared_strings[int(text)]
            return text

        inline_string = cell.find('a:is', namespace)
        if inline_string is not None:
            return ''.join(text.text or '' for text in inline_string.findall('.//a:t', namespace))
        return ''

    def _xlsx_column_index(self, cell_ref: str) -> int:
        column_name = re.match(r'[A-Z]+', cell_ref).group(0)
        index = 0
        for char in column_name:
            index = index * 26 + ord(char) - ord('A') + 1
        return index - 1

    def _find_xlsx_header(self, rows: List[List[str]]) -> Optional[int]:
        required_headers = {'时间', '发送者身份', '内容'}
        for index, row in enumerate(rows):
            if required_headers.issubset({cell.strip() for cell in row}):
                return index
        return None

    def _xlsx_cell(self, row: List[str], index: int) -> str:
        return row[index].strip() if index < len(row) else ''

    def parse_records(self, file_content: str, contact_id: str) -> List[Dict]:
        """解析聊天记录，优先使用硬编码规则，失败时回退到 LLM"""

        # 1. 尝试使用已缓存的解析器
        cached_parser = self._try_cached_parsers(file_content)
        if cached_parser:
            try:
                records = self._parse_with_code(file_content, cached_parser)
                if records:
                    print(f"✓ 使用缓存解析器成功解析 {len(records)} 条记录（零 LLM 调用）")
                    return records
            except Exception as e:
                print(f"缓存解析器失败: {e}，尝试其他方法")

        # 2. 尝试常见格式的内置解析器
        builtin_records = self._try_builtin_parsers(file_content)
        if builtin_records:
            print(f"✓ 使用内置解析器成功解析 {len(builtin_records)} 条记录（零 LLM 调用）")
            return builtin_records

        # 3. 让 LLM 生成新的硬编码解析器
        print("未识别格式，请求 LLM 生成解析器...")
        generated_parser = self._generate_parser_with_llm(file_content)

        if generated_parser:
            try:
                records = self._parse_with_code(file_content, generated_parser)
                if records:
                    self._cache_parser(generated_parser)
                    print(f"✓ 使用生成的解析器成功解析 {len(records)} 条记录")
                    return records
            except Exception as e:
                print(f"生成的解析器失败: {e}，回退到 LLM 直接解析")

        # 4. 最后回退：让 LLM 直接解析内容
        print("回退到 LLM 直接解析...")
        return self._parse_with_llm(file_content)

    def _try_builtin_parsers(self, content: str) -> Optional[List[Dict]]:
        """尝试常见格式的内置解析器"""
        parsers = [
            self._parse_wechat_txt,
            self._parse_wechat_html,
            self._parse_csv,
            self._parse_json
        ]

        for parser in parsers:
            try:
                records = parser(content)
                if records and len(records) > 0:
                    return records
            except:
                continue
        return None

    def _parse_wechat_txt(self, content: str) -> Optional[List[Dict]]:
        """解析微信 TXT 导出格式

        常见格式：
        2024-01-15 10:30:25 张三
        你好

        2024-01-15 10:31:00 我
        你好啊
        """
        pattern = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(.+?)\n(.+?)(?=\n\d{4}-\d{2}-\d{2}|\Z)'
        matches = re.findall(pattern, content, re.DOTALL)

        if not matches:
            return None

        records = []
        for timestamp_str, sender_name, message in matches:
            sender = "user" if sender_name.strip() in ["我", "Me"] else "contact"
            records.append({
                "timestamp": timestamp_str.strip(),
                "sender": sender,
                "message": message.strip()
            })

        return records if len(records) > 0 else None

    def _parse_wechat_html(self, content: str) -> Optional[List[Dict]]:
        """解析微信 HTML 导出格式"""
        # 简化的 HTML 解析，实际可能需要 BeautifulSoup
        pattern = r'<div class="message">.*?<span class="time">(.+?)</span>.*?<span class="sender">(.+?)</span>.*?<div class="content">(.+?)</div>'
        matches = re.findall(pattern, content, re.DOTALL)

        if not matches:
            return None

        records = []
        for timestamp_str, sender_name, message in matches:
            sender = "user" if "我" in sender_name else "contact"
            records.append({
                "timestamp": timestamp_str.strip(),
                "sender": sender,
                "message": message.strip()
            })

        return records if len(records) > 0 else None

    def _parse_csv(self, content: str) -> Optional[List[Dict]]:
        """解析 CSV 格式"""
        lines = content.strip().split('\n')
        if len(lines) < 2:
            return None

        # 检查是否有标题行
        header = lines[0].lower()
        if not any(k in header for k in ['time', 'sender', 'message', '时间', '发送者', '消息']):
            return None

        records = []
        for line in lines[1:]:
            parts = line.split(',')
            if len(parts) >= 3:
                records.append({
                    "timestamp": parts[0].strip(),
                    "sender": "user" if parts[1].strip() in ["我", "user", "me"] else "contact",
                    "message": ','.join(parts[2:]).strip()
                })

        return records if len(records) > 0 else None

    def _parse_json(self, content: str) -> Optional[List[Dict]]:
        """解析 JSON 格式"""
        try:
            data = json.loads(content)
            if isinstance(data, list) and len(data) > 0:
                # 检查是否已经是目标格式
                first = data[0]
                if all(k in first for k in ['timestamp', 'sender', 'message']):
                    return data
        except:
            pass
        return None

    def _generate_parser_with_llm(self, file_content: str) -> Optional[Dict]:
        """让 LLM 生成硬编码解析器"""
        system_prompt = """你是一个代码生成专家。分析聊天记录格式，生成 Python 解析代码。

返回 JSON 格式：
{
    "format_name": "格式名称（如 wechat_txt_v2）",
    "description": "格式描述",
    "regex_pattern": "正则表达式（用于提取消息）",
    "sample_code": "完整的 Python 解析函数代码"
}

要求：
1. regex_pattern 必须能提取 timestamp、sender、message
2. sample_code 必须是可执行的 Python 函数，函数名为 parse_custom
3. 函数签名：def parse_custom(content: str) -> List[Dict]
4. 返回格式：[{"timestamp": "...", "sender": "user/contact", "message": "..."}]"""

        prompt = f"""分析以下聊天记录格式（前 1000 字符）：

```
{file_content[:1000]}
```

请生成解析代码。"""

        response = self.ai_client.generate(prompt, 'entity_extraction', system_prompt)

        try:
            parser_def = json.loads(response)
            if 'regex_pattern' in parser_def and 'sample_code' in parser_def:
                return parser_def
        except:
            pass
        return None

    def _parse_with_code(self, content: str, parser_def: Dict) -> Optional[List[Dict]]:
        """使用生成的代码解析"""
        try:
            # 执行生成的代码
            exec_globals = {"re": re, "json": json, "List": List, "Dict": Dict}
            exec(parser_def['sample_code'], exec_globals)

            parse_func = exec_globals.get('parse_custom')
            if parse_func:
                records = parse_func(content)
                if records and len(records) > 0:
                    return records
        except Exception as e:
            raise ValueError(f"代码执行失败: {e}")
        return None

    def _cache_parser(self, parser_def: Dict):
        """缓存解析器定义"""
        cache_file = self.parsers_cache_dir / f"{parser_def.get('format_name', 'custom')}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(parser_def, f, ensure_ascii=False, indent=2)

    def _try_cached_parsers(self, content: str) -> Optional[Dict]:
        """尝试使用缓存的解析器"""
        if not self.parsers_cache_dir.exists():
            return None

        for cache_file in self.parsers_cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    parser_def = json.load(f)

                # 简单匹配：检查正则是否能匹配
                pattern = parser_def.get('regex_pattern')
                if pattern and re.search(pattern, content[:500]):
                    return parser_def
            except:
                continue
        return None

    def _parse_with_llm(self, file_content: str) -> List[Dict]:
        """最后的回退方案：让 LLM 直接解析内容"""
        system_prompt = """你是一个聊天记录解析专家。将聊天记录解析为统一的 JSON 格式。

每条消息返回格式：
{
    "timestamp": "YYYY-MM-DD HH:MM:SS",
    "sender": "user 或 contact",
    "message": "消息内容"
}

返回 JSON 数组。"""

        prompt = f"""聊天记录内容：
```
{file_content}
```

请解析为统一格式的 JSON 数组。注意：
1. sender 只能是 "user" 或 "contact"
2. 如果无法确定发送者，根据上下文推断
3. timestamp 必须是有效的日期时间格式"""

        response = self.ai_client.generate(prompt, 'entity_extraction', system_prompt)

        try:
            records = json.loads(response)
            for record in records:
                if 'timestamp' not in record or 'sender' not in record or 'message' not in record:
                    raise ValueError("解析结果缺少必要字段")
            return records
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"LLM 解析失败: {str(e)}")

parser_agent = ParserAgent()
