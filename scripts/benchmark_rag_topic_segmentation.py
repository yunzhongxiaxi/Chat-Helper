import sys
from pathlib import Path
from statistics import mean
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.parser_agent import parser_agent
from backend.services.rag_service import RAGService


SAMPLE_FILE = PROJECT_ROOT / 'chat_history_sample.xlsx'
WINDOW_SIZE = 40
SAMPLE_COUNT = 6
PREVIEW_MESSAGES = 3


def pick_sample_starts(records: list[dict], window_size: int, sample_count: int) -> list[int]:
    if len(records) <= window_size:
        return [0]

    anchors = [
        index for index, record in enumerate(records)
        if record['message'].strip() and not record['message'].startswith('[表情')
    ]
    if not anchors:
        return [0]

    max_start = len(records) - window_size
    step = max(len(anchors) // sample_count, 1)
    starts = []
    for anchor in anchors[::step]:
        start = min(anchor, max_start)
        if not starts or abs(start - starts[-1]) >= window_size:
            starts.append(start)
        if len(starts) >= sample_count:
            break
    return starts


def print_topic_preview(service: RAGService, window_index: int, topics: list[list[dict]]):
    print(f'\n窗口 {window_index}: topic_count={len(topics)}, sizes={[len(topic) for topic in topics]}')
    for topic_index, topic in enumerate(topics, 1):
        keywords = service._top_terms(' '.join(record['message'] for record in topic), 8)
        print(
            f'  topic {topic_index}: messages={len(topic)}, '
            f'time={topic[0]["timestamp"]}~{topic[-1]["timestamp"]}, keywords={keywords}'
        )
        for record in topic[:PREVIEW_MESSAGES]:
            message = record['message'].replace('\n', ' ')[:100]
            print(f'    - {record["sender"]}: {message}')


def main():
    parsed = parser_agent.parse_xlsx(SAMPLE_FILE.read_bytes())
    records = parsed['records']
    starts = pick_sample_starts(records, WINDOW_SIZE, SAMPLE_COUNT)
    service = RAGService()
    service.topic_segmentation_enabled = True
    service.topic_segmentation_window_size = WINDOW_SIZE

    elapsed_times = []
    topic_counts = []
    topic_sizes = []
    total_messages = 0

    print('RAG LLM topic segmentation 小样本 benchmark')
    print(f'样例文件: {SAMPLE_FILE.resolve()}')
    print(f'总记录数: {len(records)}')
    print(f'窗口大小: {WINDOW_SIZE}')
    print(f'样本窗口数: {len(starts)}')

    total_begin = perf_counter()
    for window_index, start in enumerate(starts, 1):
        window = records[start:start + WINDOW_SIZE]
        begin = perf_counter()
        topics = service._split_topics(window)
        elapsed = perf_counter() - begin

        elapsed_times.append(elapsed)
        topic_counts.append(len(topics))
        topic_sizes.extend(len(topic) for topic in topics)
        total_messages += len(window)

        print(f'\n窗口 {window_index}: start={start}, elapsed={elapsed:.2f}s')
        print_topic_preview(service, window_index, topics)

    total_elapsed = perf_counter() - total_begin
    print('\n汇总:')
    print(f'  样本窗口数: {len(starts)}')
    print(f'  总消息数: {total_messages}')
    print(f'  总耗时: {total_elapsed:.2f}s')
    print(f'  平均每窗口耗时: {mean(elapsed_times):.2f}s')
    print(f'  topic 总数: {sum(topic_counts)}')
    print(f'  平均每窗口 topic 数: {mean(topic_counts):.2f}')
    print(f'  平均 topic 消息数: {mean(topic_sizes):.2f}')
    print(f'  每窗口 topic 数分布: {topic_counts}')


if __name__ == '__main__':
    main()
