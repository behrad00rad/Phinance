# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim
WORKDIR /app
COPY package*.json ./
RUN --network=host npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]
