from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import psycopg2
import os
import json
import base64
import nats
from nats.js.api import ConsumerConfig

app = FastAPI(title="Crypto Bot Dashboard API")

# Configurações do ambiente
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://crypto_admin:ZNG5z43LaSrk7FEmwu6CPtRUB2IVKdvY@crypto-postgres:5432/crypto_bot")
NATS_URL = os.getenv("NATS_URL", "nats://crypto-nats:4222")

# Helpers
def get_db_conn():
    return psycopg2.connect(DATABASE_URL)

# Endpoints da API

@app.get("/api/dashboard")
async def get_dashboard_data():
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        # Lucro líquido (DB)
        cur.execute("SELECT SUM(pnl_pct) FROM trade_log WHERE status = 'CLOSED'")
        total_pnl = cur.fetchone()[0] or 0
        
        # Win Rate
        cur.execute("SELECT COUNT(*) FROM trade_log WHERE status = 'CLOSED' AND pnl_pct > 0")
        wins = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM trade_log WHERE status = 'CLOSED'")
        total_closed = cur.fetchone()[0] or 0
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        
        # Posições ativas
        cur.execute("SELECT symbol, entry_price, quantity, created_at FROM trade_log WHERE status = 'OPEN'")
        active_rows = cur.fetchall()
        active_positions = []
        for row in active_rows:
            active_positions.append({
                "symbol": row[0],
                "entry_price": row[1],
                "quantity": row[2],
                "created_at": row[3].strftime("%d/%m %H:%M") if row[3] else ""
            })
            
        cur.close()
        conn.close()
        
        return {
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(win_rate, 1),
            "total_closed": total_closed,
            "wins": wins,
            "losses": total_closed - wins,
            "active_positions": active_positions,
            "patrimony": 97.38  # Mockado por enquanto, precisaria somar saldos da Binance
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/operations")
async def get_operations():
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, symbol, status, entry_price, exit_price, quantity, 
                   exit_reason, pnl_pct, created_at, updated_at
            FROM trade_log 
            ORDER BY created_at DESC LIMIT 50;
        """)
        rows = cur.fetchall()
        
        open_orders = []
        closed_orders = []
        
        for row in rows:
            order = {
                "id": row[0],
                "symbol": row[1],
                "status": row[2],
                "entry_price": row[3],
                "exit_price": row[4],
                "quantity": row[5],
                "exit_reason": row[6],
                "pnl_pct": row[7],
                "created_at": row[8].strftime("%d/%m %H:%M") if row[8] else "",
                "updated_at": row[9].strftime("%d/%m %H:%M") if row[9] else ""
            }
            if row[2] == "OPEN":
                open_orders.append(order)
            else:
                closed_orders.append(order)
                
        cur.close()
        conn.close()
        
        return {
            "open": open_orders,
            "closed": closed_orders,
            "balance": 80.38  # Mockado por enquanto
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/shadow")
async def get_shadow_metrics():
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT simulations, created_at 
            FROM shadow_metrics 
            ORDER BY created_at DESC LIMIT 1;
        """)
        row = cur.fetchone()
        
        strategies = []
        if row:
            sims = row[0]
            for sim in sims:
                strategies.append({
                    "config": f"SL={sim.get('sl') or 'Nulo'} | TP={sim.get('tp') or 'Nulo'}",
                    "pnl": round(float(sim.get('pnl', 0)), 2),
                    "count": sim.get('count', 0)
                })
                
        # Ordenar por PnL
        strategies.sort(key=lambda x: x["pnl"], reverse=True)
        
        cur.close()
        conn.close()
        
        return {"strategies": strategies[:10]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def get_status():
    # Aqui poderíamos pingar o NATS ou verificar containers
    # Por enquanto retorna que está tudo online se o DB conectar
    try:
        conn = get_db_conn()
        conn.close()
        return {
            "services": [
                {"name": "fb-trade-decision", "status": "Online"},
                {"name": "fb-position-management", "status": "Online"},
                {"name": "fb-execution", "status": "Online"},
                {"name": "fb-analytics", "status": "Online"},
                {"name": "crypto-nats", "status": "Online"},
                {"name": "crypto-postgres", "status": "Online"}
            ]
        }
    except Exception:
        return {
            "services": [
                {"name": "crypto-postgres", "status": "Offline"}
            ]
        }

# Servir arquivos estáticos do Frontend (React)
# Isso deve ficar por último para não interceptar as rotas da API
if os.path.exists("./dist"):
    app.mount("/", StaticFiles(directory="./dist", html=True), name="static")
else:
    @app.get("/")
    def read_root():
        return {"message": "API rodando. Frontend não buildado ainda (rode npm run build)."}
