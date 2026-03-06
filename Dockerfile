# 使用 nginx 提供静态文件
FROM nginx:alpine

# 删除默认页面，使用我们自己的
RUN rm -rf /usr/share/nginx/html/*

# 复制静态资源到 nginx 目录
COPY . /usr/share/nginx/html/

# 暴露 80 端口（nginx 默认）
EXPOSE 87

CMD ["nginx", "-g", "daemon off;"]
