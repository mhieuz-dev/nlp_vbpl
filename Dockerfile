# Ảnh cho Google Cloud Run. Hai tầng: tầng builder cài và dọn thư viện, tầng
# chạy chỉ nhận /opt/venv sạch, không dính pip cache hay apt lists.
#
# Vì sao ép nhỏ: Cloud Run chạy scale-to-zero, nên thời gian KÉO ẢNH cộng thẳng
# vào mỗi lần khởi động nguội mà khách phải ngồi chờ. Bản đầu 4,12 GB.

# ---------- tầng 1: cài và dọn ----------
FROM python:3.10-slim AS builder

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements-deploy.txt .
RUN pip install -r requirements-deploy.txt

# Gỡ những thứ pip kéo về vì phụ thuộc khai báo, nhưng đường phục vụ không bao
# giờ chạm tới. Smoke test ngay dưới sẽ nổ nếu gỡ nhầm.
#   kubernetes    - chromadb chỉ dùng cho chế độ server/HA, ta dùng PersistentClient
#   onnxruntime   - hàm nhúng mặc định của chromadb, ta luôn truyền embedding sẵn
#   torch/include, torch/test - header C++ và test, không dùng lúc chạy
#
# scipy và sklearn ĐÃ THỬ GỠ VÀ PHẢI GIỮ LẠI: sentence_transformers/util/
# similarity.py import `from sklearn.metrics import pairwise_distances` ngay lúc
# load module chứ không phải import muộn, gỡ là không import nổi thư viện.
# Mất ~180 MB tiết kiệm nhưng không có cách nào khác.
ARG SP=/opt/venv/lib/python3.10/site-packages
RUN rm -rf $SP/kubernetes $SP/onnxruntime \
           $SP/torch/include $SP/torch/test \
    && find $SP -name "__pycache__" -type d -prune -exec rm -rf {} + \
    && find $SP -name "tests" -maxdepth 2 -type d -prune -exec rm -rf {} +

# Nướng model vào ảnh: tải e5-base lúc chạy tốn ~60s mỗi lần khởi động nguội,
# nướng vào thì trả giá đúng một lần lúc build.
ENV HF_HOME=/opt/hf
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('intfloat/multilingual-e5-base')"

# Chạy thật đúng đường mà server sẽ đi: nhúng một câu, ghi vào Chroma, truy vấn
# lại. Gỡ nhầm gói nào ở trên thì build chết ở đây chứ không chết trên Cloud Run.
RUN python -c "\
import fastapi, uvicorn, openai, requests, pydantic, dotenv; \
from sentence_transformers import SentenceTransformer; \
import chromadb; \
m = SentenceTransformer('intfloat/multilingual-e5-base'); \
v = m.encode(['query: vượt đèn đỏ'], normalize_embeddings=True).tolist(); \
c = chromadb.EphemeralClient().get_or_create_collection('smoke', metadata={'hnsw:space': 'cosine'}); \
c.upsert(ids=['1'], embeddings=v, documents=['Điều 6.'], metadatas=[{'doc_id': 'x'}]); \
assert c.query(query_embeddings=v, n_results=1)['ids'][0] == ['1']; \
import torch; assert not torch.cuda.is_available(); \
print('SMOKE OK', len(v[0]), torch.__version__)"

# ---------- tầng 2: ảnh chạy ----------
FROM python:3.10-slim

RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app

COPY --from=builder --chown=user /opt/venv /opt/venv
COPY --from=builder --chown=user /opt/hf /home/user/.cache/huggingface

ENV PATH=/opt/venv/bin:$PATH \
    HOME=/home/user \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface \
    # torch đọc số nhân của MÁY CHỦ chứ không đọc quota cgroup: để mặc định là
    # nó đẻ 8-16 luồng, tranh nhau trong 2 vCPU và phình RSS. MALLOC_ARENA_MAX
    # thường tiết kiệm 100-300 MB RSS với torch đa luồng.
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    MALLOC_ARENA_MAX=2 \
    TOKENIZERS_PARALLELISM=false \
    # sentence-transformers gọi về huggingface.co lúc nạp model. Model đã nướng
    # sẵn trong ảnh, không nên để khởi động nguội phụ thuộc uptime của HF.
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY --chown=user . .

# KHÔNG nướng kho Chroma vào ảnh: nó đổi mỗi đêm và nặng 620 MB. Kho tải từ
# GCS lúc khởi động (src/vectorstore/bootstrap.py, biến CORPUS_URL), nên cập
# nhật luật hằng đêm không cần build lại ảnh.
#
# KHÔNG dùng --workers: mỗi worker là thêm một bản model 1,5 GB trong RAM.
EXPOSE 8080
CMD exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}
