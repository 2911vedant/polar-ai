# Build stage
FROM node:20-alpine AS builder

ARG VITE_API_URL=http://localhost:8000
ARG VITE_APP_NAME=POLAR-AI

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_APP_NAME=$VITE_APP_NAME

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
