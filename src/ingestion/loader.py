from datasets import load_dataset, concatenate_datasets

DEFAULT_SPLITS = ["2026", "2023", "2021"]

def load_legal_documents(max_docs: int = None, splits: list[str] = None) -> list[dict]:
    if splits is None:
        splits = DEFAULT_SPLITS

    all_splits = []
    for split in splits:
        try:
            all_splits.append(load_dataset("undertheseanlp/UTS_VLC", split=split))
        except Exception:
            pass

    dataset = concatenate_datasets(all_splits) if len(all_splits) > 1 else all_splits[0]

    if max_docs:
        dataset = dataset.select(range(min(max_docs, len(dataset))))

    docs = []
    for i, row in enumerate(dataset):
        docs.append({
            "id": str(row.get("id", i)),
            "title": row.get("title", ""),
            "content": row.get("content", ""),
            "law_type": row.get("type", "unknown"),
        })
    return docs
