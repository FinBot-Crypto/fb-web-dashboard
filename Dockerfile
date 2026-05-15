# Stage 1: Build React Frontend
FROM node:20-slim as build

WORKDIR /app

# Copia os arquivos de dependências
COPY package*.json ./

# Instala as dependências
RUN npm install

# Copia o restante do código do frontend
COPY . .

# Builda o frontend (gera a pasta dist)
RUN npm run build

# Stage 2: Serve with Python FastAPI
FROM python:3.10-slim

WORKDIR /app

# Instala dependências do Python
RUN pip install fastapi uvicorn psycopg2-binary nats-py ccxt

# Copia o arquivo principal do backend
COPY main.py .

# Copia a pasta buildada do frontend do Stage 1
COPY --from=build /app/dist ./dist

# Expõe a porta que o FastAPI vai rodar
EXPOSE 8000

# Comando para rodar a aplicação
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
