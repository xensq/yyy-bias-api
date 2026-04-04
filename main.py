from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from concurrent.futures import ThreadPoolExecutor

from engine.topology import calculate_topology, calculate_entropy
from engine.gex import calculate_gex
from engine.macro import get_walcl, get_reserves_rrp, get_oas, get_auctions
from engine.scorer import score
from engine.iv import get_iv_surface
from engine.iv_surface import get_iv_surface as get_iv_surface_3d
from engine.outlook import generate_outlook
from engine.history import get_chart_data

executor = ThreadPoolExecutor(max_workers=10)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    executor.shutdown(wait=False)

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

async def run(fn, *args):
    return await asyncio.get_event_loop().run_in_executor(executor, fn, *args)

@app.get("/")
def root():
    return {"status": "ok", "service": "yyy bias api v3"}

@app.get("/bias")
async def bias():
    topology, entropy = await asyncio.gather(run(calculate_topology), run(calculate_entropy))
    gex, walcl, reserves_rrp, oas, auctions = await asyncio.gather(
        run(calculate_gex), run(get_walcl), run(get_reserves_rrp), run(get_oas), run(get_auctions))
    result = score(topology, entropy, walcl, reserves_rrp, oas, gex, auctions)
    return {"bias": result, "topology": topology, "entropy": entropy, "gex": gex,
            "macro": {"walcl": walcl, "reserves_rrp": reserves_rrp, "oas": oas, "auctions": auctions}}

@app.get("/gex")
async def gex_route():
    return await run(calculate_gex)

@app.get("/macro")
async def macro_route():
    walcl, reserves_rrp, oas, auctions = await asyncio.gather(
        run(get_walcl), run(get_reserves_rrp), run(get_oas), run(get_auctions))
    return {"walcl": walcl, "reserves_rrp": reserves_rrp, "oas": oas, "auctions": auctions}

@app.get("/iv")
async def iv_route():
    return await run(get_iv_surface)

@app.get("/iv_surface")
async def iv_surface_route(ticker: str = Query(default="SPX")):
    return await run(get_iv_surface_3d, ticker)

@app.get("/outlook")
async def outlook_route():
    topology, entropy = await asyncio.gather(run(calculate_topology), run(calculate_entropy))
    walcl, reserves_rrp, oas, auctions = await asyncio.gather(
        run(get_walcl), run(get_reserves_rrp), run(get_oas), run(get_auctions))
    gex = await run(calculate_gex)
    result = score(topology, entropy, walcl, reserves_rrp, oas, gex, auctions)
    macro = {"walcl": walcl, "reserves_rrp": reserves_rrp, "oas": oas, "auctions": auctions}
    return await run(generate_outlook, macro, result, topology, entropy)

@app.get("/history")
async def history_route():
    return await run(get_chart_data)
