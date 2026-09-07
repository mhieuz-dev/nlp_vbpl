# Bản chạy trên HuggingFace Spaces (SDK docker). Space không có GPU nên dùng
# torch bản CPU: 1,6 GB thay vì 5,9 GB, và build nhanh hơn nhiều.
FROM python:3.10-slim

# HF Spaces chạy container dưới UID 1000, không phải root.
RUN useradd -m -u 1000 user
USER user
ENV PATH=/home/user/.local/bin:$PATH \
    HOME=/home/user \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

COPY --chown=user requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

# Nướng sẵn model vào ảnh. Tải e5-base lúc chạy tốn ~60s mỗi lần Space thức
# dậy sau khi ngủ; nướng vào ảnh thì trả giá đúng một lần lúc build.
ENV HF_HOME=/home/user/.cache/huggingface
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('intfloat/multilingual-e5-base')"

COPY --chown=user . .

# KHÔNG nướng kho Chroma vào ảnh: nó đổi mỗi đêm và nặng 612 MB. Kho được tải
# từ HuggingFace Dataset lúc khởi động (src/vectorstore/bootstrap.py), nên chỉ
# cần restart Space là có dữ liệu mới, không phải build lại ảnh.
EXPOSE 7860
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]
