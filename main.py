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

# Conexão NATS reutilizável (evita leak de file descriptors)
_nats_client = None
async def get_nats():
    global _nats_client
    if _nats_client is None or _nats_client.is_closed:
        _nats_client = await nats.connect(NATS_URL)
    return _nats_client

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
        real_patrimony = 0
        bnb_usd = 0
        try:
            exchange = ccxt.binance({
                'apiKey': os.getenv("BINANCE_API_KEY"),
                'secret': os.getenv("BINANCE_API_SECRET"),
                'enableRateLimit': True,
            })
            balance = exchange.fetch_balance()
            total_val_usdt = balance['total'].get('USDT', 0)
            
            # Somar o valor de outras moedas (incluindo BNB)
            for asset, amount in balance['total'].items():
                if amount > 0 and asset != 'USDT':
                    try:
                        if asset == 'BNB':
                            total_val_usdt += amount * exchange.fetch_ticker("BNB/USDT")['last']
                        else:
                            ticker = exchange.fetch_ticker(f"{asset}/USDT")
                            total_val_usdt += amount * ticker['last']
                    except:
                        pass
            real_patrimony = round(total_val_usdt, 2)
            # Saldo BNB separado
            bnb_amount = balance['total'].get('BNB', 0)
            if bnb_amount > 0:
                try:
                    bnb_usd = round(bnb_amount * exchange.fetch_ticker("BNB/USDT")['last'], 2)
                except:
                    pass
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
            "bnb_balance": bnb_usd,
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
async def get_operations(page: int = 1, limit: int = 50):
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        # Contagem total
        cur.execute("SELECT COUNT(*) FROM trade_log WHERE status = 'CLOSED'")
        total_closed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM trade_log WHERE status = 'OPEN'")
        total_open = cur.fetchone()[0]
        
        offset = (page - 1) * limit
        
        cur.execute("""
            SELECT id, symbol, status, entry_price, exit_price, quantity, 
                   exit_reason, pnl_pct, created_at, updated_at
            FROM trade_log 
            ORDER BY created_at DESC LIMIT %s OFFSET %s;
        """, (limit, offset))
        rows = cur.fetchall()
        
        # W/L por moeda
        cur.execute("""
            SELECT symbol, COUNT(*) as total, 
                   SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN pnl_pct < 0 THEN 1 ELSE 0 END) as losses
            FROM trade_log WHERE status = 'CLOSED'
            GROUP BY symbol
        """)
        coin_wl = {r[0]: {"total": r[1], "wins": r[2] or 0, "losses": r[3] or 0} for r in cur.fetchall()}
        
        # Total PnL real (todos os fechados)
        cur.execute("""
            SELECT COALESCE(SUM((pnl_pct/100) * entry_price * quantity), 0)
            FROM trade_log WHERE status = 'CLOSED' AND entry_price IS NOT NULL AND quantity IS NOT NULL
        """)
        total_pnl = round(cur.fetchone()[0], 2)
        
        # Buscar SL/TP do KV (NATS) e preços atuais da Binance
        kv_data = {}
        current_prices = {}
        try:
            nc = await get_nats()
            js = nc.jetstream()
            kv = await asyncio.wait_for(js.key_value("active_positions"), timeout=3.0)
            keys = await kv.keys()
            for k in keys:
                entry = await kv.get(k)
                pos = json.loads(entry.value.decode())
                sym = pos.get("symbol", "")
                kv_data[sym] = {
                    "sl_price": pos.get("sl_price"),
                    "tp_price": pos.get("tp_price")
                }
            # nc mantido aberto (singleton)
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
                # W/L histórico
                wl = coin_wl.get(row[1], {})
                order["coin_wins"] = wl.get("wins", 0)
                order["coin_losses"] = wl.get("losses", 0)
                order["coin_total"] = wl.get("total", 0)
                open_orders.append(order)
            else:
                closed_orders.append(order)
                
        cur.close()
        conn.close()
        
        return {
            "open": open_orders,
            "closed": closed_orders,
            "total_open": total_open,
            "total_closed": total_closed,
            "total_pnl": total_pnl,
            "page": page,
            "limit": limit,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/shadow")
async def get_shadow_metrics():
    try:
        conn = get_db_conn()
        cur = conn.cursor()

        cur.execute("SELECT simulations, tier, rsi_entry, hour_entry FROM shadow_metrics")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return {
                "total_simulations": 0,
                "ranking_sltp": [],
                "ranking_tier": [],
                "ranking_rsi": [],
                "ranking_hour": [],
                "best_combo": None,
            }

        # --- Agregação geral SL/TP ---
        sltp_agg = {}
        # --- Por Tier ---
        tier_agg = {}
        # --- Por Faixa RSI ---
        rsi_buckets = {
            "<25": {"label": "< 25", "pnls": []},
            "25-30": {"label": "25–30", "pnls": []},
            "30-35": {"label": "30–35", "pnls": []},
            "35-38": {"label": "35–38", "pnls": []},
        }
        # --- Por Hora (UTC) ---
        hour_agg = {h: {"pnls": []} for h in range(24)}
        # --- Combinações para best_combo ---
        combo_agg = {}

        for row in rows:
            sims_raw, tier, rsi_entry, hour_entry = row
            if isinstance(sims_raw, str):
                sims = json.loads(sims_raw)
            else:
                sims = sims_raw or []

            tier = tier or "Desconhecido"
            rsi_entry = float(rsi_entry) if rsi_entry else None
            hour_entry = int(hour_entry) if hour_entry is not None else None

            # Determinar faixa RSI
            rsi_label = None
            if rsi_entry is not None:
                if rsi_entry < 25:
                    rsi_label = "<25"
                elif rsi_entry < 30:
                    rsi_label = "25-30"
                elif rsi_entry < 35:
                    rsi_label = "30-35"
                else:
                    rsi_label = "35-38"

            # Determinar janela horária
            hour_window = None
            if hour_entry is not None:
                if 0 <= hour_entry < 6:
                    hour_window = "Madrugada (0–6h)"
                elif 6 <= hour_entry < 12:
                    hour_window = "Manhã (6–12h)"
                elif 12 <= hour_entry < 18:
                    hour_window = "Tarde (12–18h)"
                else:
                    hour_window = "Noite (18–24h)"

            for sim in sims:
                pnl = float(sim.get("pnl", 0))
                sl = sim.get("sl")
                tp = sim.get("tp")
                key = f"SL={sl or 'Nulo'} | TP={tp or 'Nulo'}"

                # SL/TP agregado
                if key not in sltp_agg:
                    sltp_agg[key] = {"config": key, "sl": sl, "tp": tp, "pnls": []}
                sltp_agg[key]["pnls"].append(pnl)

                # Por Tier
                if tier not in tier_agg:
                    tier_agg[tier] = {"pnls": []}
                tier_agg[tier]["pnls"].append(pnl)

                # Por RSI
                if rsi_label and rsi_label in rsi_buckets:
                    rsi_buckets[rsi_label]["pnls"].append(pnl)

                # Por Hora
                if hour_entry is not None:
                    hour_agg[hour_entry]["pnls"].append(pnl)

                # Combinações multi-dimensionais
                if tier and rsi_label and hour_window:
                    combo_key = f"{tier} | RSI {rsi_buckets[rsi_label]['label']} | {hour_window}"
                    if combo_key not in combo_agg:
                        combo_agg[combo_key] = {"label": combo_key, "pnls": []}
                    combo_agg[combo_key]["pnls"].append(pnl)

        # --- Formatar ranking SL/TP ---
        def fmt_sltp(agg_dict, limit=15):
            out = []
            for v in agg_dict.values():
                pnls = v["pnls"]
                n = len(pnls)
                if n == 0:
                    continue
                avg = sum(pnls) / n
                wins = sum(1 for p in pnls if p > 0)
                out.append({
                    "config": v["config"],
                    "sl": v.get("sl"),
                    "tp": v.get("tp"),
                    "avg_pnl": round(avg, 3),
                    "win_rate": round(wins / n * 100, 1),
                    "count": n,
                })
            out.sort(key=lambda x: x["avg_pnl"], reverse=True)
            return out[:limit]

        ranking_sltp = fmt_sltp(sltp_agg)

        # --- Formatar Tier ---
        ranking_tier = []
        for tier_name, v in tier_agg.items():
            pnls = v["pnls"]
            n = len(pnls)
            if n == 0:
                continue
            avg = sum(pnls) / n
            wins = sum(1 for p in pnls if p > 0)
            ranking_tier.append({
                "tier": tier_name,
                "avg_pnl": round(avg, 3),
                "win_rate": round(wins / n * 100, 1),
                "count": n,
            })
        ranking_tier.sort(key=lambda x: x["avg_pnl"], reverse=True)

        # --- Formatar RSI ---
        ranking_rsi = []
        for bucket_key in ["<25", "25-30", "30-35", "35-38"]:
            v = rsi_buckets[bucket_key]
            pnls = v["pnls"]
            n = len(pnls)
            avg = (sum(pnls) / n) if n > 0 else 0
            wins = sum(1 for p in pnls if p > 0) if n > 0 else 0
            ranking_rsi.append({
                "range": v["label"],
                "avg_pnl": round(avg, 3),
                "win_rate": round(wins / n * 100, 1) if n > 0 else 0,
                "count": n,
            })

        # --- Formatar Hora ---
        window_agg = {}
        for h, v in hour_agg.items():
            pnls = v["pnls"]
            if not pnls:
                continue
            if 0 <= h < 6:
                win_label = "Madrugada (0–6h)"
            elif 6 <= h < 12:
                win_label = "Manhã (6–12h)"
            elif 12 <= h < 18:
                win_label = "Tarde (12–18h)"
            else:
                win_label = "Noite (18–24h)"
            if win_label not in window_agg:
                window_agg[win_label] = {"pnls": []}
            window_agg[win_label]["pnls"].extend(pnls)

        # Também retornar hora por hora para o heatmap
        ranking_hour_raw = []
        for h in range(24):
            pnls = hour_agg[h]["pnls"]
            n = len(pnls)
            avg = (sum(pnls) / n) if n > 0 else None
            ranking_hour_raw.append({
                "hour": h,
                "avg_pnl": round(avg, 3) if avg is not None else None,
                "count": n,
            })

        ranking_hour_windows = []
        for wlabel in ["Madrugada (0–6h)", "Manhã (6–12h)", "Tarde (12–18h)", "Noite (18–24h)"]:
            v = window_agg.get(wlabel, {"pnls": []})
            pnls = v["pnls"]
            n = len(pnls)
            avg = (sum(pnls) / n) if n > 0 else 0
            wins = sum(1 for p in pnls if p > 0) if n > 0 else 0
            ranking_hour_windows.append({
                "window": wlabel,
                "avg_pnl": round(avg, 3),
                "win_rate": round(wins / n * 100, 1) if n > 0 else 0,
                "count": n,
            })

        # --- Best Combo ---
        best_combo = None
        if combo_agg:
            best_candidates = []
            for v in combo_agg.values():
                pnls = v["pnls"]
                n = len(pnls)
                if n < 3:  # Mínimo de 3 amostras para ser significativo
                    continue
                avg = sum(pnls) / n
                wins = sum(1 for p in pnls if p > 0)
                best_candidates.append({
                    "label": v["label"],
                    "avg_pnl": round(avg, 3),
                    "win_rate": round(wins / n * 100, 1),
                    "count": n,
                })
            if best_candidates:
                best_candidates.sort(key=lambda x: x["avg_pnl"], reverse=True)
                best_combo = best_candidates[0]

        total_simulations = sum(len(v["pnls"]) for v in sltp_agg.values())

        return {
            "total_simulations": total_simulations,
            "ranking_sltp": ranking_sltp,
            "ranking_tier": ranking_tier,
            "ranking_rsi": ranking_rsi,
            "ranking_hour": ranking_hour_raw,
            "ranking_hour_windows": ranking_hour_windows,
            "best_combo": best_combo,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/live-flow")
async def get_live_flow():
    """Retorna as últimas ações do pipeline (logs dos containers)."""
    import docker as dk
    try:
        client = dk.from_env()
        logs = {}
        containers = {
            "market": "fb-market-selection",
            "strategy": "fb-strategy-ml",
            "decision": "fb-decision-engine",
            "trade": "fb-trade-decision",
            "exec": "fb-execution",
        }
        for key, name in containers.items():
            try:
                c = client.containers.get(name)
                output = c.logs(tail=8).decode()
                lines = [l.strip() for l in output.split('\n') if l.strip()]
                logs[key] = lines[-8:]
            except:
                logs[key] = []
        return {"logs": logs}
    except Exception as e:
        return {"logs": {}, "error": str(e)}

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
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

if os.path.exists("./dist"):
    app.mount("/assets", StaticFiles(directory="./dist/assets"), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Se é rota da API, deixa passar (as rotas acima capturam primeiro)
        file_path = f"./dist/{full_path}" if full_path else "./dist/index.html"
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse("./dist/index.html")
else:
    @app.get("/")
    def read_root():
        return {"message": "API rodando. Frontend não buildado ainda (rode npm run build)."}
