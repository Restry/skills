FROM node:20-alpine AS build
WORKDIR /w
COPY web/package.json web/
RUN cd web && npm install --no-audit --no-fund
COPY web /w/web
RUN cd web && npm run build

FROM nginx:alpine
COPY --from=build /w/web/dist /usr/share/nginx/html
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
