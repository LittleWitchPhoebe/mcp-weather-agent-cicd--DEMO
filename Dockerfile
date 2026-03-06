# 构建 project/ 下的 Python 应用，用于 CI/CD 部署
FROM python:3.11-slim

WORKDIR /app

# 先只复制依赖，利用镜像缓存
COPY project/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 再复制应用代码
COPY project/ .

# 无缓冲输出，便于看日志
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
