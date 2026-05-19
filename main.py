from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import psycopg2
import os
import json
import base64
import nats
import ccxt
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
        
        # Puxar todos os trades fechados para calcular os dados reais em dinheiro
        cur.execute("""
            SELECT symbol, pnl_pct, entry_price, quantity, updated_at 
            FROM trade_log 
            WHERE status = 'CLOSED'
            ORDER BY updated_at ASC;
        """)
        rows = cur.fetchall()
        
        total_closed = len(rows)
        wins = 0
        losses = 0
        total_pnl_money = 0
        
        curve_data = []
        coin_stats = {}
        
        for row in rows:
            symbol = row[0]
            pnl_pct = row[1]
            entry_price = row[2]
            quantity = row[3]
            date = row[4]
            
            if pnl_pct is not None and entry_price is not None and quantity is not None:
                # Calcular dinheiro ganho/perdido
                invested = entry_price * quantity
                pnl_money = (pnl_pct / 100) * invested
                total_pnl_money += pnl_money
                
                # Win/Loss
                if pnl_pct > 0:
                    wins += 1
                else:
                    losses += 1
                    
                # Acumular para a curva (em dinheiro!)
                curve_data.append({
                    "date": date.strftime("%d/%m") if date else "",
                    "pnl": round(total_pnl_money, 2)
                })
                
                # Estatísticas por moeda
                if symbol not in coin_stats:
                    coin_stats[symbol] = {"symbol": symbol, "pnl": 0, "wins": 0, "losses": 0, "total": 0}
                    
                coin_stats[symbol]["pnl"] += pnl_money
                coin_stats[symbol]["total"] += 1
                if pnl_pct > 0:
                    coin_stats[symbol]["wins"] += 1
                else:
                    coin_stats[symbol]["losses"] += 1
                    
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        
        # Formatar Rankings
        # Melhores moedas por PnL em dinheiro
        best_coins = sorted(coin_stats.values(), key=lambda x: x["pnl"], reverse=True)[:5]
        worst_coins = sorted(coin_stats.values(), key=lambda x: x["pnl"])[:5]
        
        # Mais operadas
        most_traded = sorted(coin_stats.values(), key=lambda x: x["total"], reverse=True)[:5]
        
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
        
        # Buscar saldo real na Binance
        real_patrimony = 97.38 # Fallback
        try:
            exchange = ccxt.binance({
                'apiKey': os.getenv("BINANCE_API_KEY"),
                'secret': os.getenv("BINANCE_API_SECRET"),
                'enableRateLimit': True,
            })
            balance = exchange.fetch_balance()
            total_val_usdt = balance['total'].get('USDT', 0)
            
            # Somar o valor de outras moedas (se houver)
            for asset, amount in balance['total'].items():
                if amount > 0 and asset != 'USDT' and asset != 'BNB':
                    try:
                        ticker = exchange.fetch_ticker(f"{asset}/USDT")
                        total_val_usdt += amount * ticker['last']
                    except:
                        pass
            real_patrimony = round(total_val_usdt, 2)
        except Exception as e:
            print(f"Erro ao buscar saldo na Binance: {e}")
            
        return {
            "total_pnl_money": round(total_pnl_money, 2),
            "win_rate": round(win_rate, 1),
            "total_closed": total_closed,
            "wins": wins,
            "losses": losses,
            "active_positions": active_positions,
            "patrimony": real_patrimony,
            "rankings": {
                "best": [{"symbol": x["symbol"], "pnl": round(x["pnl"], 2)} for x in best_coins],
                "worst": [{"symbol": x["symbol"], "pnl": round(x["pnl"], 2)} for x in worst_coins],
                "most_traded": [{"symbol": x["symbol"], "wins": x["wins"], "losses": x["losses"], "total": x["total"]} for x in most_traded]
            },
            "curve": curve_data
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
        
        # Buscar SL/TP do KV (NATS) e preços atuais da Binance
        kv_data = {}
        current_prices = {}
        try:
            nc = await nats.connect(NATS_URL)
            js = nc.jetstream()
            kv = await js.key_value("active_positions")
            keys = await kv.keys()
            for k in keys:
                entry = await kv.get(k)
                pos = json.loads(entry.value.decode())
                sym = pos.get("symbol", "")
                kv_data[sym] = {
                    "sl_price": pos.get("sl_price"),
                    "tp_price": pos.get("tp_price")
                }
            await nc.close()
            
            # Buscar preços atuais para todas as moedas abertas
            exchange = ccxt.binance({
                'apiKey': os.getenv("BINANCE_API_KEY"),
                'secret': os.getenv("BINANCE_API_SECRET"),
                'enableRateLimit': True,
            })
            for row in rows:
                if row[2] == "OPEN":
                    try:
                        ticker = exchange.fetch_ticker(row[1])
                        current_prices[row[1]] = ticker["last"]
                    except:
                        current_prices[row[1]] = None
        except Exception as e:
            print(f"Erro ao buscar KV/preços: {e}")
        
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
                # Adicionar SL/TP do KV
                kv_info = kv_data.get(row[1], {})
                order["sl_price"] = kv_info.get("sl_price")
                order["tp_price"] = kv_info.get("tp_price")
                order["current_price"] = current_prices.get(row[1])
                open_orders.append(order)
            else:
                closed_orders.append(order)
                
        cur.close()
        conn.close()
        
        return {
            "open": open_orders,
            "closed": closed_orders,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/shadow")
async def get_shadow_metrics():
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        cur.execute("SELECT simulations FROM shadow_metrics")
        rows = cur.fetchall()
        
        aggregated = {}
        
        for row in rows:
            sims = row[0]
            if isinstance(sims, str):
                import json
                sims = json.loads(sims)
                
            for sim in sims:
                key = f"SL={sim.get('sl') or 'Nulo'} | TP={sim.get('tp') or 'Nulo'}"
                if key not in aggregated:
                    aggregated[key] = {"config": key, "pnl": 0, "count": 0}
                aggregated[key]["pnl"] += float(sim.get('pnl', 0))
                aggregated[key]["count"] += 1
                
        # Converter para lista e ordenar por PnL
        strategies = list(aggregated.values())
        for strat in strategies:
            strat["pnl"] = round(strat["pnl"], 2)
            
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
