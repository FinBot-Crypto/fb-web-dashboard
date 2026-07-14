from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import psycopg2
import os
import json
import base64
import nats
import ccxt
import asyncio
import time as _time
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

# Instâncias de exchange Binance reutilizáveis (evita recrear + load_markets a cada request)
_cached_spot_ex = None
_cached_futures_ex = None

def _get_spot_ex():
    global _cached_spot_ex
    if _cached_spot_ex is None:
        api_key = os.getenv("BINANCE_API_KEY")
        secret = os.getenv("BINANCE_API_SECRET")
        config = {
            'enableRateLimit': True,
            'timeout': 15000,
        }
        if api_key and api_key not in ("your_api_key", ""):
            config['apiKey'] = api_key
        if secret and secret not in ("your_api_secret", ""):
            config['secret'] = secret
        _cached_spot_ex = ccxt.binance(config)
    return _cached_spot_ex

def _get_futures_ex():
    global _cached_futures_ex
    if _cached_futures_ex is None:
        api_key = os.getenv("BINANCE_API_KEY")
        secret = os.getenv("BINANCE_API_SECRET")
        config = {
            'enableRateLimit': True,
            'timeout': 15000,
            'options': {'defaultType': 'future'}
        }
        if api_key and api_key not in ("your_api_key", ""):
            config['apiKey'] = api_key
        if secret and secret not in ("your_api_secret", ""):
            config['secret'] = secret
        _cached_futures_ex = ccxt.binance(config)
    return _cached_futures_ex

def _get_binance_balances(spot_ex, futures_ex):
    spot_total, spot_free, spot_used, bnb_usd = 0.0, 0.0, 0.0, 0.0
    futures_total, futures_free, futures_used = 0.0, 0.0, 0.0
    try:
        spot_bal = spot_ex.fetch_balance()
        spot_free = float(spot_bal.get('USDT', {}).get('free', 0.0))
        total_val_usdt = spot_bal['total'].get('USDT', 0.0)
        for asset, amount in spot_bal['total'].items():
            if amount > 0 and asset != 'USDT':
                try:
                    if asset == 'BNB':
                        total_val_usdt += amount * spot_ex.fetch_ticker("BNB/USDT")['last']
                    else:
                        ticker = spot_ex.fetch_ticker(f"{asset}/USDT")
                        total_val_usdt += amount * ticker['last']
                except:
                    pass
        spot_total = round(total_val_usdt, 2)
        
        # Saldo BNB separado
        bnb_amount = spot_bal['total'].get('BNB', 0.0)
        if bnb_amount > 0:
            try:
                bnb_usd = round(bnb_amount * spot_ex.fetch_ticker("BNB/USDT")['last'], 2)
            except:
                pass
                
        spot_used = round(spot_total - spot_free - bnb_usd, 2)
        if spot_used < 0:
            spot_used = 0.0
    except Exception as e:
        print(f"[PERF] ERRO ao buscar saldos Spot: {e}")

    try:
        f_bal = futures_ex.fetch_balance()
        usdt_info = f_bal.get('USDT', {})
        futures_total = float(usdt_info.get('total', 0.0))
        futures_free = float(usdt_info.get('free', 0.0))
        futures_used = float(usdt_info.get('used', 0.0))
    except Exception as e:
        print(f"[PERF] ERRO ao buscar saldos Futures: {e}")

    return {
        "total": spot_total,
        "free": spot_free,
        "used": spot_used,
        "bnb_usd": bnb_usd
    }, {
        "total": futures_total,
        "free": futures_free,
        "used": futures_used
    }

def _fetch_all_binance_data(symbols_to_fetch):
    """Busca tickers + saldos Spot/Futures. Roda em thread separada via asyncio.to_thread."""
    import time as t
    current_prices = {}
    t0 = t.time()
    if symbols_to_fetch:
        try:
            tickers = _get_spot_ex().fetch_tickers(symbols_to_fetch)
            for sym in symbols_to_fetch:
                if sym in tickers:
                    current_prices[sym] = tickers[sym].get("last")
        except Exception as e:
            print(f"[PERF] ERRO fetch_tickers: {e}")

    spot_balances, futures_balances = _get_binance_balances(_get_spot_ex(), _get_futures_ex())
    print(f"[PERF] _fetch_all_binance_data TOTAL: {(t.time()-t0)*1000:.0f}ms")
    return current_prices, spot_balances, futures_balances

def _fetch_dashboard_binance_data():
    """Busca saldo real na Binance (Spot + Futures) + saldo BNB. Roda em thread separada."""
    import time as t
    t0 = t.time()
    spot_balances, futures_balances = _get_binance_balances(_get_spot_ex(), _get_futures_ex())
    print(f"[PERF] _fetch_dashboard_binance_data TOTAL: {(t.time()-t0)*1000:.0f}ms")
    return spot_balances["total"], spot_balances, futures_balances, spot_balances["bnb_usd"]

# Endpoints da API

@app.get("/api/dashboard")
async def get_dashboard_data():
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        # Puxar todos os trades fechados para calcular os dados reais em dinheiro
        cur.execute("""
            SELECT symbol, pnl_pct, entry_price, quantity, 
                   updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo'
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
        best_coins = sorted(coin_stats.values(), key=lambda x: x["pnl"], reverse=True)[:5]
        worst_coins = sorted(coin_stats.values(), key=lambda x: x["pnl"])[:5]
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

    # Buscar saldo real na Binance (Spot + Futures) em thread (não bloqueia event loop)
    real_patrimony, spot_balances, futures_balances, bnb_usd = await asyncio.to_thread(
        _fetch_dashboard_binance_data
    )
        
    return {
        "total_pnl_money": round(total_pnl_money, 2),
        "win_rate": round(win_rate, 1),
        "total_closed": total_closed,
        "wins": wins,
        "losses": losses,
        "active_positions": active_positions,
        "patrimony": round(spot_balances["total"] + futures_balances["total"], 2),
        "spot_balance": round(spot_balances["total"], 2),
        "spot_balance_free": round(spot_balances["free"], 2),
        "spot_balance_used": round(spot_balances["used"], 2),
        "futures_balance": round(futures_balances["total"], 2),
        "futures_balance_free": round(futures_balances["free"], 2),
        "futures_balance_used": round(futures_balances["used"], 2),
        "bnb_balance": bnb_usd,
        "rankings": {
            "best": [{"symbol": x["symbol"], "pnl": round(x["pnl"], 2)} for x in best_coins],
            "worst": [{"symbol": x["symbol"], "pnl": round(x["pnl"], 2)} for x in worst_coins],
            "most_traded": [{"symbol": x["symbol"], "wins": x["wins"], "losses": x["losses"], "total": x["total"]} for x in most_traded]
        },
        "curve": curve_data
    }



@app.get("/api/operations")
async def get_operations(page: int = 1, limit: int = 50):
    t_start = _time.time()
    conn = None
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
                   exit_reason, pnl_pct, 
                   created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo', 
                   updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo', 
                   is_futures, leverage, score, rsi, direction, tier
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

        # PnL por tier por dia (para breakdown no histórico)
        cur.execute("""
            SELECT 
                tier,
                date(updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo') as day,
                COUNT(*) as total,
                SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl_pct <= 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM((pnl_pct/100) * entry_price * quantity), 0) as pnl_money
            FROM trade_log 
            WHERE status = 'CLOSED' AND entry_price IS NOT NULL AND quantity IS NOT NULL
            GROUP BY tier, day
            ORDER BY day DESC, tier
        """)
        tier_day_rows = cur.fetchall()
        # Build dict: {"13/07": [{tier, wins, losses, pnl_money}]}
        tier_by_day = {}
        for r in tier_day_rows:
            tier_name = r[0] or "Desconhecido"
            day_str = r[1].strftime("%d/%m") if r[1] else ""
            if day_str not in tier_by_day:
                tier_by_day[day_str] = []
            tier_by_day[day_str].append({
                "tier": tier_name,
                "total": r[2],
                "wins": r[3] or 0,
                "losses": r[4] or 0,
                "pnl_money": round(float(r[5]), 4)
            })
        
        cur.close()
    except Exception as e:
        import traceback
        print(f"[PERF] /api/operations ERRO DB: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()
            
    t_db = _time.time()
    print(f"[PERF] DB queries: {(t_db - t_start)*1000:.0f}ms")

    # Buscar SL/TP do KV (NATS)
    kv_data = {}
    current_prices = {}
    symbols_to_fetch = []
    try:
        nc = await get_nats()
        js = nc.jetstream()
        kv = await asyncio.wait_for(js.key_value("active_positions"), timeout=2.0)
        keys = await kv.keys()
        
        for k in keys:
            try:
                entry = await kv.get(k)
                if entry:
                    pos = json.loads(entry.value.decode())
                    sym = pos.get("symbol", "")
                    if sym:
                        symbols_to_fetch.append(sym)
                        kv_data[sym] = {
                            "sl_price": pos.get("sl_price"),
                            "tp_price": pos.get("tp_price"),
                            "entry_time": pos.get("entry_time"),
                            "is_futures": pos.get("is_futures", False),
                            "leverage": pos.get("leverage", 1),
                            "score": pos.get("score"),
                            "rsi": pos.get("rsi")
                        }
            except Exception as entry_err:
                print(f"[PERF] Erro KV key: {entry_err}")
    except Exception as e:
        print(f"[PERF] Erro KV: {e}")

    t_kv = _time.time()
    print(f"[PERF] NATS KV: {(t_kv - t_db)*1000:.0f}ms ({len(symbols_to_fetch)} symbols: {symbols_to_fetch})")

    # Busca tickers + saldos Binance em thread separada (não bloqueia event loop)
    binance_prices, spot_balances, futures_balances = await asyncio.to_thread(
        _fetch_all_binance_data, symbols_to_fetch
    )
    current_prices.update(binance_prices)

    t_api = _time.time()
    print(f"[PERF] Binance API (thread): {(t_api - t_kv)*1000:.0f}ms")
    
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
            "updated_at": row[9].strftime("%d/%m %H:%M") if row[9] else "",
            "is_futures": row[10] if len(row) > 10 else False,
            "leverage": row[11] if len(row) > 11 else 1,
            "score": row[12] if len(row) > 12 else None,
            "rsi": row[13] if len(row) > 13 else None,
            "direction": row[14] if len(row) > 14 else "LONG",
            "tier": row[15] if len(row) > 15 else None
        }
        if row[2] == "OPEN":
            # Adicionar SL/TP do KV
            kv_info = kv_data.get(row[1], {})
            order["sl_price"] = kv_info.get("sl_price")
            order["tp_price"] = kv_info.get("tp_price")
            order["entry_time"] = kv_info.get("entry_time")
            order["is_futures"] = kv_info.get("is_futures", order.get("is_futures", False))
            order["leverage"] = kv_info.get("leverage", order.get("leverage", 1))
            # Fallback para o valor retornado do banco caso não exista no KV
            order["score"] = kv_info.get("score") if kv_info.get("score") is not None else order.get("score")
            order["rsi"] = kv_info.get("rsi") if kv_info.get("rsi") is not None else order.get("rsi")
            price = current_prices.get(row[1])
            if price is None and "/" not in row[1]:
                price = current_prices.get(row[1] + "/USDT")
            order["current_price"] = price
            # W/L histórico
            wl = coin_wl.get(row[1], {})
            order["coin_wins"] = wl.get("wins", 0)
            order["coin_losses"] = wl.get("losses", 0)
            order["coin_total"] = wl.get("total", 0)
            open_orders.append(order)
        else:
            closed_orders.append(order)
            
    max_hold_hours = float(os.getenv("MAX_HOLD_HOURS", "12"))

    t_total = _time.time()
    print(f"[PERF] /api/operations TOTAL: {(t_total - t_start)*1000:.0f}ms (open={len(open_orders)}, closed={len(closed_orders)}, prices={len(current_prices)})")

    return {
        "open": open_orders,
        "closed": closed_orders,
        "total_open": total_open,
        "total_closed": total_closed,
        "total_pnl": total_pnl,
        "page": page,
        "limit": limit,
        "max_hold_hours": max_hold_hours,
        "tier_by_day": tier_by_day,
        "spot_balance": round(spot_balances["total"], 2),
        "spot_balance_free": round(spot_balances["free"], 2),
        "spot_balance_used": round(spot_balances["used"], 2),
        "futures_balance": round(futures_balances["total"], 2),
        "futures_balance_free": round(futures_balances["free"], 2),
        "futures_balance_used": round(futures_balances["used"], 2),
        "bnb_balance": round(spot_balances["bnb_usd"], 2)
    }

def aggregate_shadow_simulations(rows, direction="LONG"):
    if not rows:
        return {
            "total_simulations": 0,
            "ranking_sltp": [],
            "ranking_rsi": [],
            "ranking_hour": [],
            "ranking_symbol": [],
            "ranking_tier": [],
            "ranking_trend": [],
            "best_combo": None,
            "best_scores": []
        }

    sltp_agg = {}
    rsi_agg = {}
    hour_agg = {h: {"pnls": []} for h in range(24)}
    symbol_agg = {}
    combo_agg = {}
    tier_agg = {}
    trend_agg = {}
    window_agg = {
        "Madrugada (0–6h)": {"window": "Madrugada (0–6h)", "pnls": []},
        "Manhã (6–12h)": {"window": "Manhã (6–12h)", "pnls": []},
        "Tarde (12–18h)": {"window": "Tarde (12–18h)", "pnls": []},
        "Noite (18–24h)": {"window": "Noite (18–24h)", "pnls": []}
    }
    score_details = []

    for row in rows:
        symbol, tier, rsi_e, hour_e, entry_price, sl, tp, pnl, reason, minutes, ms, bt = row
        
        tier = tier or "Desconhecido"
        hour_e = int(hour_e) if hour_e is not None else None
        rsi_e = float(rsi_e) if rsi_e else None
        pnl = float(pnl) if pnl else 0
        model_score = float(ms) if ms is not None else None
        btc_trend = bt or "neutral"
        
        sltp_key = f"SL={sl or 'Nulo'} | TP={tp or 'Nulo'}"
        if sltp_key not in sltp_agg:
            sltp_agg[sltp_key] = {"config": sltp_key, "sl": sl, "tp": tp, "pnls": []}
        sltp_agg[sltp_key]["pnls"].append(pnl)

        if rsi_e is not None:
            if direction == "SHORT":
                if rsi_e >= 75: rl = ">=75"
                elif rsi_e >= 70: rl = "70-75"
                else: rl = "65-70"
            else:
                if rsi_e < 25: rl = "<25"
                elif rsi_e < 30: rl = "25-30"
                elif rsi_e < 35: rl = "30-35"
                else: rl = "35+"
            if rl not in rsi_agg:
                rsi_agg[rl] = {"pnls": []}
            rsi_agg[rl]["pnls"].append(pnl)

        if hour_e is not None:
            hour_agg[hour_e]["pnls"].append(pnl)
            if 0 <= hour_e < 6:
                wl = "Madrugada (0–6h)"
            elif 6 <= hour_e < 12:
                wl = "Manhã (6–12h)"
            elif 12 <= hour_e < 18:
                wl = "Tarde (12–18h)"
            else:
                wl = "Noite (18–24h)"
            window_agg[wl]["pnls"].append(pnl)

        if symbol not in symbol_agg:
            symbol_agg[symbol] = {"pnls": [], "count": 0}
        symbol_agg[symbol]["pnls"].append(pnl)
        symbol_agg[symbol]["count"] += 1

        if rsi_e is not None and hour_e is not None:
            win = "Madrugada" if 0 <= hour_e < 6 else "Manha" if 6 <= hour_e < 12 else "Tarde" if 12 <= hour_e < 18 else "Noite"
            combo_key = f"RSI {rl} | {win}"
            if combo_key not in combo_agg:
                combo_agg[combo_key] = {"label": combo_key, "pnls": []}
            combo_agg[combo_key]["pnls"].append(pnl)

        if tier not in tier_agg:
            tier_agg[tier] = {"tier": tier, "pnls": []}
        tier_agg[tier]["pnls"].append(pnl)

        if btc_trend not in trend_agg:
            trend_agg[btc_trend] = {"trend": btc_trend, "pnls": []}
        trend_agg[btc_trend]["pnls"].append(pnl)

        if model_score is not None:
            score_details.append({
                "symbol": symbol,
                "score": model_score,
                "rsi": rsi_e,
                "hour": hour_e,
                "pnl": pnl,
                "sl": sl,
                "tp": tp,
                "reason": reason
            })

    def fmt_agg(agg_dict, label_key, limit=15):
        out = []
        for v in agg_dict.values():
            pnls = v["pnls"]
            n = len(pnls)
            if n < 5:
                continue
            avg = sum(pnls) / n
            wins = sum(1 for p in pnls if p > 0)
            item = {"avg_pnl": round(avg, 3), "win_rate": round(wins / n * 100, 1), "count": n}
            if label_key in v:
                item[label_key] = v[label_key]
            out.append(item)
        out.sort(key=lambda x: x["avg_pnl"], reverse=True)
        return out[:limit]

    ranking_sltp = fmt_agg(sltp_agg, "config")

    ranking_rsi = []
    rsi_keys = [">=75", "70-75", "65-70"] if direction == "SHORT" else ["<25", "25-30", "30-35", "35+"]
    for key in rsi_keys:
        if key in rsi_agg:
            pnls = rsi_agg[key]["pnls"]
            n = len(pnls)
            if n > 0:
                avg = sum(pnls) / n
                wins = sum(1 for p in pnls if p > 0)
                ranking_rsi.append({"range": key, "avg_pnl": round(avg, 3), "win_rate": round(wins / n * 100, 1), "count": n})
        else:
            ranking_rsi.append({"range": key, "avg_pnl": 0, "win_rate": 0, "count": 0})

    ranking_hour = []
    for h in range(24):
        ps = hour_agg[h]["pnls"]
        avg = round(sum(ps) / len(ps), 3) if ps else None
        ranking_hour.append({"hour": h, "avg_pnl": avg, "count": len(ps)})

    ranking_hour_windows = []
    for wl in ["Madrugada (0–6h)", "Manhã (6–12h)", "Tarde (12–18h)", "Noite (18–24h)"]:
        ps = window_agg[wl]["pnls"]
        n = len(ps)
        if n > 0:
            avg = sum(ps) / n
            wins = sum(1 for p in ps if p > 0)
            ranking_hour_windows.append({
                "window": wl,
                "avg_pnl": round(avg, 3),
                "win_rate": round(wins / n * 100, 1),
                "count": n
            })
        else:
            ranking_hour_windows.append({
                "window": wl,
                "avg_pnl": 0,
                "win_rate": 0,
                "count": 0
            })

    ranking_symbol = fmt_agg(symbol_agg, "symbol")
    ranking_tier = fmt_agg(tier_agg, "tier")
    ranking_trend = fmt_agg(trend_agg, "trend")

    best_combo = None
    candidates = []
    for v in combo_agg.values():
        pnls = v["pnls"]
        n = len(pnls)
        if n < 3:
            continue
        avg = sum(pnls) / n
        wins = sum(1 for p in pnls if p > 0)
        candidates.append({"label": v["label"], "avg_pnl": round(avg, 3), "win_rate": round(wins / n * 100, 1), "count": n})
    if candidates:
        candidates.sort(key=lambda x: x["avg_pnl"], reverse=True)
        best_combo = candidates[0]

    score_details.sort(key=lambda x: x["score"], reverse=True)
    seen = set()
    best_scores = []
    for sd in score_details:
        key = (sd["symbol"], round(sd["score"], 4))
        if key not in seen:
            seen.add(key)
            best_scores.append(sd)
            if len(best_scores) >= 10:
                break

    return {
        "total_simulations": len(rows),
        "ranking_sltp": ranking_sltp,
        "ranking_rsi": ranking_rsi,
        "ranking_hour": ranking_hour,
        "ranking_hour_windows": ranking_hour_windows,
        "ranking_symbol": ranking_symbol,
        "ranking_tier": ranking_tier,
        "ranking_trend": ranking_trend,
        "best_combo": best_combo,
        "best_scores": best_scores
    }

@app.get("/api/shadow-short")
async def get_shadow_short_metrics(min_model_score: float = 0):
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()

        if min_model_score > 0:
            cur.execute("""
                SELECT symbol, tier, rsi_entry, hour_entry, entry_price, sl, tp, pnl, exit_reason, minutes, model_score, btc_trend
                FROM shadow_short_metrics
                WHERE model_score IS NOT NULL AND model_score >= %s
                ORDER BY entry_ts DESC
            """, (min_model_score,))
        else:
            cur.execute("""
                SELECT symbol, tier, rsi_entry, hour_entry, entry_price, sl, tp, pnl, exit_reason, minutes, model_score, btc_trend
                FROM shadow_short_metrics
                ORDER BY entry_ts DESC
            """)
        rows = cur.fetchall()
        cur.close()

        if not rows:
            return {
                "total_simulations": 0, "ranking_sltp": [], "ranking_rsi": [], "ranking_hour": [], "ranking_tier": [], "ranking_symbol": [], "ranking_trend": [], "best_combo": None, "best_scores": [],
                "tiers": {
                    "Major": {"total_simulations": 0, "ranking_sltp": [], "ranking_rsi": [], "ranking_hour": [], "ranking_symbol": [], "best_combo": None, "best_scores": []},
                    "Strong Alt": {"total_simulations": 0, "ranking_sltp": [], "ranking_rsi": [], "ranking_hour": [], "ranking_symbol": [], "best_combo": None, "best_scores": []},
                    "High Volatility": {"total_simulations": 0, "ranking_sltp": [], "ranking_rsi": [], "ranking_hour": [], "ranking_symbol": [], "best_combo": None, "best_scores": []}
                }
            }

        # Group by tier
        rows_by_tier = {
            "Major": [],
            "Strong Alt": [],
            "High Volatility": []
        }
        for row in rows:
            t = row[1] or "Desconhecido"
            if t in rows_by_tier:
                rows_by_tier[t].append(row)

        global_metrics = aggregate_shadow_simulations(rows, "SHORT")
        tier_metrics = {}
        for t, t_rows in rows_by_tier.items():
            tier_metrics[t] = aggregate_shadow_simulations(t_rows, "SHORT")

        return {
            **global_metrics,
            "tiers": tier_metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get("/api/shadow-long-scan")
async def get_shadow_long_scan(min_model_score: float = 0):
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        if min_model_score > 0:
            cur.execute("""SELECT symbol, tier, rsi_entry, hour_entry, entry_price, sl, tp, pnl, exit_reason, minutes, model_score
                           FROM shadow_long_scan WHERE model_score >= %s ORDER BY entry_ts DESC""", (min_model_score,))
        else:
            cur.execute("""SELECT symbol, tier, rsi_entry, hour_entry, entry_price, sl, tp, pnl, exit_reason, minutes, model_score
                           FROM shadow_long_scan ORDER BY entry_ts DESC""")
        rows = cur.fetchall()
        cur.close()
        if not rows:
            return {"total_simulations": 0, "ranking_sltp": [], "ranking_rsi": [], "ranking_hour": [], "ranking_tier": [], "ranking_symbol": [], "ranking_trend": [], "best_combo": None}
        sltp_agg, tier_agg, symbol_agg, combo_agg = {}, {}, {}, {}
        rsi_agg = {}
        hour_agg = {h: {"pnls": []} for h in range(24)}
        for row in rows:
            symbol, tier, rsi_e, hour_e, entry_price, sl, tp, pnl, reason, minutes, ms = row
            tier = tier or "Desconhecido"
            pnl = float(pnl) if pnl else 0
            rsi_e = float(rsi_e) if rsi_e else None
            hour_e = int(hour_e) if hour_e is not None else None
            sltp_key = f"SL={sl or 'Nulo'} | TP={tp or 'Nulo'}"
            if sltp_key not in sltp_agg:
                sltp_agg[sltp_key] = {"config": sltp_key, "sl": sl, "tp": tp, "pnls": []}
            sltp_agg[sltp_key]["pnls"].append(pnl)
            if tier not in tier_agg:
                tier_agg[tier] = {"tier": tier, "pnls": []}
            tier_agg[tier]["pnls"].append(pnl)
            if rsi_e is not None:
                if rsi_e < 25: rl = "<25"
                elif rsi_e < 30: rl = "25-30"
                elif rsi_e < 35: rl = "30-35"
                else: rl = "35+"
                if rl not in rsi_agg: rsi_agg[rl] = {"pnls": []}
                rsi_agg[rl]["pnls"].append(pnl)
            if hour_e is not None:
                hour_agg[hour_e]["pnls"].append(pnl)
            if symbol not in symbol_agg:
                symbol_agg[symbol] = {"symbol": symbol, "pnls": []}
            symbol_agg[symbol]["pnls"].append(pnl)

        def fmt(agg, key, lim=15):
            out = []
            for v in agg.values():
                pnls = v["pnls"]
                if len(pnls) < 5: continue
                avg = sum(pnls) / len(pnls)
                wins = sum(1 for p in pnls if p > 0)
                out.append({"avg_pnl": round(avg, 3), "win_rate": round(wins / len(pnls) * 100, 1), "count": len(pnls), key: v.get(key, "")})
            out.sort(key=lambda x: x["avg_pnl"], reverse=True)
            return out[:lim]

        rsltp = fmt(sltp_agg, "config")
        rtier = fmt(tier_agg, "tier")
        rsym = fmt(symbol_agg, "symbol")
        r_rsi = []
        for k in ["<25", "25-30", "30-35", "35+"]:
            v = rsi_agg.get(k, {"pnls": []})
            pnls = v["pnls"]
            n = len(pnls)
            a = sum(pnls) / n if n > 0 else 0
            w = sum(1 for p in pnls if p > 0)
            r_rsi.append({"range": k, "avg_pnl": round(a, 3), "win_rate": round(w / n * 100, 1) if n else 0, "count": n})
        rhour = [{"hour": h, "avg_pnl": round(sum(p) / len(p), 3) if (p := hour_agg[h]["pnls"]) else None, "count": len(p)} for h in range(24)]
        return {"total_simulations": sum(len(v["pnls"]) for v in sltp_agg.values()), "ranking_sltp": rsltp, "ranking_rsi": r_rsi,
                "ranking_hour": rhour, "ranking_tier": rtier, "ranking_symbol": rsym, "best_combo": rsltp[0] if rsltp else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get("/api/btc-trend")
async def get_btc_trend():
    try:
        import ccxt
        exchange = ccxt.binance({"enableRateLimit": True})
        period = int(os.getenv("BTC_SMA_PERIOD", "12"))
        ohlcv = exchange.fetch_ohlcv("BTC/USDT", "1h", limit=period + 10)
        if not ohlcv or len(ohlcv) < period:
            return {"trend": "neutral", "btc_price": 0, "sma": 0}
        closes = [c[4] for c in ohlcv]
        sma = sum(closes[-period:]) / period
        current = closes[-1]
        pct = (current / sma - 1) * 100
        if current > sma * 1.01:
            trend = "bull"
        elif current < sma * 0.99:
            trend = "bear"
        else:
            trend = "neutral"
        return {"trend": trend, "btc_price": round(current, 2), "sma": round(sma, 2), "pct": round(pct, 2)}
    except Exception as e:
        return {"trend": "neutral", "error": str(e)}


@app.get("/api/shadow")
async def get_shadow_metrics(min_model_score: float = 0.73):
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()

        cur.execute("""SELECT symbol, tier, rsi_entry, hour_entry, entry_price, sl, tp, pnl, exit_reason, minutes, model_score, btc_trend
                       FROM shadow_long_scan WHERE model_score >= %s ORDER BY entry_ts DESC""", (min_model_score,))
        rows = cur.fetchall()
        cur.close()

        if not rows:
            return {
                "total_simulations": 0, "ranking_sltp": [], "ranking_rsi": [], "ranking_hour": [], "ranking_tier": [], "ranking_symbol": [], "ranking_trend": [], "best_combo": None, "best_scores": [],
                "tiers": {
                    "Major": {"total_simulations": 0, "ranking_sltp": [], "ranking_rsi": [], "ranking_hour": [], "ranking_symbol": [], "best_combo": None, "best_scores": []},
                    "Strong Alt": {"total_simulations": 0, "ranking_sltp": [], "ranking_rsi": [], "ranking_hour": [], "ranking_symbol": [], "best_combo": None, "best_scores": []},
                    "High Volatility": {"total_simulations": 0, "ranking_sltp": [], "ranking_rsi": [], "ranking_hour": [], "ranking_symbol": [], "best_combo": None, "best_scores": []}
                }
            }

        # Group by tier
        rows_by_tier = {
            "Major": [],
            "Strong Alt": [],
            "High Volatility": []
        }
        for row in rows:
            t = row[1] or "Desconhecido"
            if t in rows_by_tier:
                rows_by_tier[t].append(row)

        global_metrics = aggregate_shadow_simulations(rows, "LONG")
        tier_metrics = {}
        for t, t_rows in rows_by_tier.items():
            tier_metrics[t] = aggregate_shadow_simulations(t_rows, "LONG")

        return {
            **global_metrics,
            "tiers": tier_metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()



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
    conn = None
    try:
        conn = get_db_conn()
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
    finally:
        if conn:
            conn.close()


@app.get("/api/insights")
async def get_insights(
    page: int = 1,
    limit: int = 50,
    symbol: str = None,
    decision: str = None,
    trend: str = None
):
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        # Build query
        where_clauses = []
        params = []
        
        if symbol:
            where_clauses.append("e.symbol ILIKE %s")
            params.append(f"%{symbol}%")
        if decision:
            where_clauses.append("e.decision = %s")
            params.append(decision)
        if trend:
            where_clauses.append("e.btc_trend = %s")
            params.append(trend)
            
        where_str = ""
        if where_clauses:
            where_str = "WHERE " + " AND ".join(where_clauses)
            
        # Count total
        count_query = f"SELECT COUNT(*) FROM evaluations_log e {where_str}"
        cur.execute(count_query, tuple(params))
        total_records = cur.fetchone()[0]
        
        # Fetch paginated
        offset = (page - 1) * limit
        query = f"""
            SELECT 
                e.id, e.symbol, e.tier, e.strategy, e.direction, e.score, e.rsi, e.btc_trend, e.decision, 
                e.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo',
                t.id, t.status, t.entry_price, t.exit_price, t.pnl_pct, t.exit_reason, t.is_futures, t.leverage, t.quantity, 
                t.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo'
            FROM evaluations_log e
            LEFT JOIN trade_log t ON e.symbol = t.symbol 
              AND t.created_at >= e.created_at - INTERVAL '5 minutes'
              AND t.created_at <= e.created_at + INTERVAL '5 minutes'
            {where_str}
            ORDER BY e.created_at DESC
            LIMIT %s OFFSET %s
        """
        cur.execute(query, tuple(params + [limit, offset]))
        rows = cur.fetchall()
        cur.close()
        
        items = []
        for r in rows:
            items.append({
                "id": r[0],
                "symbol": r[1],
                "tier": r[2],
                "strategy": r[3],
                "direction": r[4],
                "score": r[5],
                "rsi": r[6],
                "btc_trend": r[7],
                "decision": r[8],
                "created_at": r[9].strftime("%Y-%m-%d %H:%M:%S") if r[9] else "",
                "trade": {
                    "id": r[10],
                    "status": r[11],
                    "entry_price": r[12],
                    "exit_price": r[13],
                    "pnl_pct": r[14],
                    "exit_reason": r[15],
                    "is_futures": r[16],
                    "leverage": r[17],
                    "quantity": r[18],
                    "created_at": r[19].strftime("%Y-%m-%d %H:%M:%S") if r[19] else ""
                } if r[10] is not None else None
            })
            
        return {
            "total": total_records,
            "page": page,
            "limit": limit,
            "items": items
        }
    except Exception as e:
        import traceback
        print(f"Erro ao buscar insights: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
def init_db_settings():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            key VARCHAR(255) PRIMARY KEY,
            value JSONB NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS leme_decisions (
            id SERIAL PRIMARY KEY,
            group_name VARCHAR(50) NOT NULL,
            action VARCHAR(20) NOT NULL,
            reason TEXT NOT NULL,
            details JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    default_settings = {
        "long_Major_min_score": 0.70,
        "long_Major_max_rsi": 30.0,
        "long_Major_sl": 3.0,
        "long_Major_tp": 3.0,
        "long_Major_allowed": True,
        
        "long_Strong Alt_min_score": 0.73,
        "long_Strong Alt_max_rsi": 30.0,
        "long_Strong Alt_sl": 3.0,
        "long_Strong Alt_tp": 3.0,
        "long_Strong Alt_allowed": True,
        
        "long_High Volatility_min_score": 0.75,
        "long_High Volatility_max_rsi": 25.0,
        "long_High Volatility_sl": 5.0,
        "long_High Volatility_tp": 5.0,
        "long_High Volatility_allowed": True,
        
        "short_Major_min_score": 0.70,
        "short_Major_min_rsi": 70.0,
        "short_Major_sl": 3.0,
        "short_Major_tp": 2.0,
        "short_Major_allowed": True,
        
        "short_Strong Alt_min_score": 0.75,
        "short_Strong Alt_min_rsi": 70.0,
        "short_Strong Alt_sl": 5.0,
        "short_Strong Alt_tp": 3.0,
        "short_Strong Alt_allowed": True,
        
        "short_High Volatility_min_score": 0.85,
        "short_High Volatility_min_rsi": 75.0,
        "short_High Volatility_sl": 6.0,
        "short_High Volatility_tp": 3.0,
        "short_High Volatility_allowed": True,

        "leme_active": True,
        "leme_max_consecutive_sl": 3,
        "leme_min_win_rate": 50.0,
        "leme_cooldown_hours": 24,
        "leme_shadow_min_trades": 5,
        "leme_shadow_min_winrate": 60.0
    }
    for k, v in default_settings.items():
        cur.execute("""
            INSERT INTO bot_settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO NOTHING
        """, (k, json.dumps(v)))
    conn.commit()
    cur.close()
    conn.close()

try:
    init_db_settings()
except Exception as e:
    print(f"Erro ao inicializar bot_settings: {e}")

@app.get("/api/settings")
async def get_bot_settings():
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM bot_settings")
        rows = cur.fetchall()
        cur.close()
        out = {}
        for r in rows:
            val = r[1]
            if isinstance(val, str):
                try:
                    val = json.loads(val)
                except:
                    pass
            out[r[0]] = val
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.post("/api/settings")
async def update_bot_settings(payload: dict):
    conn = None
    try:
        # Validações rígidas de segurança para evitar parâmetros corrompidos
        for k, v in payload.items():
            if k.endswith('_min_score'):
                val = float(v)
                if val <= 0 or val >= 1.0:
                    raise HTTPException(status_code=400, detail=f"Score mínimo para {k} deve ser decimal entre 0.0 e 1.0")
            elif k.endswith('_sl') or k.endswith('_tp'):
                val = float(v)
                if val <= 0 or val > 100.0:
                    raise HTTPException(status_code=400, detail=f"Stop Loss / Take Profit para {k} deve ser entre 0.1% e 100%")
            elif k.endswith('_max_rsi') or k.endswith('_min_rsi'):
                val = float(v)
                if val <= 0 or val > 100.0:
                    raise HTTPException(status_code=400, detail=f"RSI para {k} deve ser entre 1 e 100")
            elif k == "leme_active":
                if not isinstance(v, bool):
                    raise HTTPException(status_code=400, detail="leme_active deve ser booleano")
            elif k == "leme_max_consecutive_sl":
                val = int(v)
                if val <= 0 or val > 20:
                    raise HTTPException(status_code=400, detail="leme_max_consecutive_sl deve ser entre 1 e 20")
            elif k in ["leme_min_win_rate", "leme_shadow_min_winrate"]:
                val = float(v)
                if val < 0 or val > 100.0:
                    raise HTTPException(status_code=400, detail=f"{k} deve ser entre 0% e 100%")
            elif k == "leme_cooldown_hours":
                val = int(v)
                if val <= 0 or val > 720:
                    raise HTTPException(status_code=400, detail="leme_cooldown_hours deve ser entre 1 e 720 horas")
            elif k == "leme_shadow_min_trades":
                val = int(v)
                if val <= 0 or val > 50:
                    raise HTTPException(status_code=400, detail="leme_shadow_min_trades deve ser entre 1 e 50")

        conn = get_db_conn()
        cur = conn.cursor()
        for k, v in payload.items():
            cur.execute("""
                INSERT INTO bot_settings (key, value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) 
                DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
            """, (k, json.dumps(v)))
        conn.commit()
        cur.close()
        return {"status": "success", "message": "Configurações salvas."}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.get("/api/leme/history")
async def get_leme_history():
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, group_name, action, reason, details,
                   created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo' as created_at
            FROM leme_decisions ORDER BY created_at DESC LIMIT 50
        """)
        rows = cur.fetchall()
        cur.close()
        out = []
        for r in rows:
            out.append({
                "id": r[0],
                "group_name": r[1],
                "action": r[2],
                "reason": r[3],
                "details": r[4],
                "created_at": r[5].isoformat() if r[5] else None
            })
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

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
