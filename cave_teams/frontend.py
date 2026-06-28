"""
frontend.py — the live team gallery (the decoupled frontend cave-teams never built).

A central, long-running server:
  - GET  /          → a single-file gallery (vanilla JS, no build step)
  - WS   /ws        → browsers connect; every TeamEvent is pushed here, tagged team+agent
  - POST /emit      → team spawners (in ANY process) push events; rebroadcast to /ws

So: start the gallery once; then ANY agent that spins up a team (via the adaptor /
the cave-teams skill) POSTs its event stream to /emit, and every team shows up in the
browser on the fly — each team a column, each agent its own live card. This is the
web version of Isaac's "split the pane and watch the agents."

In-process use: subscribe FrontendListener(server) to a Harness bus.
Cross-process use (the normal case): subscribe HttpFrontendListener(gallery_url).

CLI:  python -m cave_teams.frontend --port 8787
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import threading
import urllib.request
from collections import deque
from typing import Any, Deque, Dict, Optional, Set

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- server
class TeamGalleryServer:
    """FastAPI app holding the /ws fan-out + /emit intake + the gallery page."""

    def __init__(self, recent: int = 500):
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body

        self.app = FastAPI(title="cave-teams gallery")
        self._ws_clients: Set[Any] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._recent: Deque[dict] = deque(maxlen=recent)

        @self.app.get("/")
        async def index():
            from fastapi.responses import HTMLResponse
            return HTMLResponse(GALLERY_HTML)

        @self.app.get("/health")
        async def health():
            return {"ok": True, "clients": len(self._ws_clients), "buffered": len(self._recent)}

        @self.app.post("/emit")
        async def emit(ev: dict = Body(...)):
            self._recent.append(ev)
            await self._send_all(ev)
            return {"ok": True}

        @self.app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket):
            await ws.accept()
            # capture the running server loop so cross-thread broadcasts can schedule onto it
            self._loop = asyncio.get_running_loop()
            self._ws_clients.add(ws)
            try:
                for ev in list(self._recent):          # backfill so a late browser sees history
                    await ws.send_text(json.dumps(ev, default=str))
                while True:
                    await ws.receive_text()            # keep-alive
            except WebSocketDisconnect:
                self._ws_clients.discard(ws)
            except Exception:
                self._ws_clients.discard(ws)

    async def _send_all(self, payload: dict):
        data = json.dumps(payload, default=str)
        dead = set()
        for ws in list(self._ws_clients):
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    def broadcast(self, payload: dict):
        """Thread-safe broadcast (for in-process FrontendListener from a worker thread)."""
        self._recent.append(payload)
        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self._send_all(payload), loop)
                return
            except Exception:
                pass
        try:
            asyncio.get_running_loop().create_task(self._send_all(payload))
        except RuntimeError:
            pass

    def run(self, host: str = "0.0.0.0", port: int = 8787):
        import uvicorn
        logger.info("cave-teams gallery on http://%s:%d", host, port)
        uvicorn.run(self.app, host=host, port=port, log_level="warning")


# --------------------------------------------------------------------------- listeners
class FrontendListener:
    """In-process listener: pushes a team's events straight to a TeamGalleryServer."""

    def __init__(self, server: TeamGalleryServer):
        self.server = server

    def __call__(self, ev) -> None:
        self.server.broadcast(ev.to_dict() if hasattr(ev, "to_dict") else ev)


class HttpFrontendListener:
    """Cross-process listener: POSTs each event to a running gallery's /emit.

    NON-BLOCKING: events are enqueued and drained by a daemon thread, so emitting
    one 'stream' event per token never stalls the agent's turn. Drops on a full
    queue / unreachable gallery — the team keeps running headless, files capture it.
    """

    def __init__(self, gallery_url: str, timeout: float = 1.5, maxsize: int = 20000):
        import queue
        self.url = gallery_url.rstrip("/") + "/emit"
        self.timeout = timeout
        self._q: "queue.Queue" = queue.Queue(maxsize=maxsize)
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def __call__(self, ev) -> None:
        import queue
        payload = ev.to_dict() if hasattr(ev, "to_dict") else ev
        try:
            self._q.put_nowait(payload)
        except queue.Full:
            pass

    def _run(self) -> None:
        while True:
            payload = self._q.get()
            try:
                data = json.dumps(payload, default=str).encode()
                req = urllib.request.Request(
                    self.url, data=data, headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=self.timeout).read()
            except Exception:
                pass


# --------------------------------------------------------------------------- gallery page
GALLERY_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<title>cave-teams gallery</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;
         background:#0d1117; color:#c9d1d9; }
  header { padding:8px 14px; background:#161b22; border-bottom:1px solid #30363d;
           display:flex; gap:12px; align-items:center; }
  header b { color:#58a6ff; } #status { color:#8b949e; }
  #teams { display:flex; gap:14px; padding:14px; align-items:flex-start; overflow-x:auto; }
  .team { min-width:340px; max-width:380px; background:#161b22; border:1px solid #30363d;
          border-radius:8px; flex:0 0 auto; }
  .team > h2 { margin:0; padding:8px 12px; font-size:13px; color:#d2a8ff;
               border-bottom:1px solid #30363d; display:flex; justify-content:space-between; }
  .agents { padding:8px; display:flex; flex-direction:column; gap:8px; }
  .agent { background:#0d1117; border:1px solid #21262d; border-radius:6px; }
  .agent > h3 { margin:0; padding:6px 10px; font-size:12px; color:#7ee787;
                border-bottom:1px solid #21262d; display:flex; justify-content:space-between; }
  .agent .dot { width:8px;height:8px;border-radius:50%;background:#3fb950;display:inline-block;margin-left:6px;}
  .agent .dot.busy { background:#d29922; animation:pulse 1s infinite; }
  @keyframes pulse { 50% { opacity:.3; } }
  .log { max-height:240px; overflow-y:auto; padding:6px 10px; }
  .live { padding:4px 10px; color:#e3b341; white-space:pre-wrap; word-break:break-word;
          border-top:1px dashed #30363d; min-height:0; }
  .live:empty { display:none; }
  .live::after { content:'▋'; opacity:.6; animation:pulse 1s infinite; }
  .ev { padding:2px 0; border-bottom:1px dotted #21262d; white-space:pre-wrap; word-break:break-word; }
  .k { display:inline-block; min-width:78px; font-weight:bold; }
  .k.dispatched{color:#58a6ff} .k.response{color:#7ee787} .k.message{color:#79c0ff}
  .k.error{color:#f85149} .k.blocked{color:#d29922} .k.done{color:#a5d6ff}
  .k.agent_added,.k.team_spawned{color:#8b949e} .k.task{color:#d2a8ff}
  .t { color:#6e7681; }
</style></head><body>
<header><b>cave-teams</b> live gallery <span id="status">connecting…</span></header>
<div id="teams"></div>
<script>
const teamsEl = document.getElementById('teams');
const status = document.getElementById('status');
const teams = {};   // name -> {el, agents:{alias->{card,log,dot}}}

function team(name){
  if(teams[name]) return teams[name];
  const el=document.createElement('div'); el.className='team';
  el.innerHTML=`<h2><span>▣ ${name}</span><span class="t" data-c>0</span></h2><div class="agents"></div>`;
  teamsEl.appendChild(el);
  return teams[name]={el, agentsEl:el.querySelector('.agents'), agents:{}, n:0};
}
function agent(tname, alias){
  const T=team(tname); alias=alias||'(team)';
  if(T.agents[alias]) return T.agents[alias];
  const card=document.createElement('div'); card.className='agent';
  card.innerHTML=`<h3><span>${alias}<span class="dot"></span></span></h3>`+
                 `<div class="log"></div><div class="live"></div>`;
  T.agentsEl.appendChild(card);
  return T.agents[alias]={card, log:card.querySelector('.log'),
                         live:card.querySelector('.live'), dot:card.querySelector('.dot')};
}
function summarize(ev){
  const d=ev.data||{};
  if(ev.kind==='dispatched') return (d.content||'').slice(0,200);
  if(ev.kind==='response')   return (d.text||'').slice(0,400);
  if(ev.kind==='message')    return `${d.frm||''}: ${(d.content||'').slice(0,200)}`;
  if(ev.kind==='error')      return d.error||'';
  if(ev.kind==='blocked')    return d.reason||'';
  if(ev.kind==='done')       return d.summary||'✓';
  if(ev.kind==='agent_added')return `${d.backend||''} ${d.model||''}`;
  if(ev.kind==='team_spawned')return `task: ${(d.task||'').slice(0,160)}`;
  return JSON.stringify(d).slice(0,200);
}
function render(ev){
  const A=agent(ev.team, ev.agent);
  const T=teams[ev.team];
  // live token streaming: append the delta to the agent's live line, no log spam
  if(ev.kind==='stream'){
    A.live.textContent += (ev.data && ev.data.delta) || '';
    A.live.scrollIntoView({block:'nearest'});
    A.dot.classList.add('busy');
    return;
  }
  const line=document.createElement('div'); line.className='ev';
  const time=new Date((ev.ts||0)*1000).toLocaleTimeString();
  line.innerHTML=`<span class="k ${ev.kind}">${ev.kind}</span> <span class="t">${time}</span>  `+
                 summarize(ev).replace(/</g,'&lt;');
  A.log.appendChild(line); A.log.scrollTop=A.log.scrollHeight;
  if(ev.kind==='dispatched'){ A.dot.classList.add('busy'); A.live.textContent=''; }
  if(['response','error','done','blocked'].includes(ev.kind)){ A.dot.classList.remove('busy'); A.live.textContent=''; }
  T.n++; T.el.querySelector('[data-c]').textContent=T.n;
}
function connect(){
  const ws=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws');
  ws.onopen =()=> status.textContent='● live';
  ws.onclose=()=>{ status.textContent='● reconnecting…'; setTimeout(connect,1500); };
  ws.onmessage=(m)=>{ try{ render(JSON.parse(m.data)); }catch(e){} };
}
connect();
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="cave-teams live gallery server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    TeamGalleryServer().run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
