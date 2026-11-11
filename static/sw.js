self.addEventListener("install", (e) => {
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;

  e.respondWith(
    fetch(e.request).catch(async () => {
      const cached = await caches.match(e.request);
      if (cached) return cached;

      if (e.request.mode === "navigate") {
        const html = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <title>SIM — Conectando ao servidor local...</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #0b0f17;
      color: #e2e8f0;
      font-family: system-ui, -apple-system, sans-serif;
    }
    .box {
      text-align: center;
      padding: 32px;
      border-radius: 16px;
      background: #131b2e;
      border: 1px solid rgba(255,255,255,0.08);
      max-width: 420px;
    }
    .spinner {
      width: 36px;
      height: 36px;
      border: 3px solid rgba(56,189,248,0.2);
      border-top-color: #38bdf8;
      border-radius: 50%;
      animation: spin 0.9s linear infinite;
      margin: 0 auto 16px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    h2 { margin: 0 0 8px; font-size: 18px; }
    p { margin: 0; font-size: 14px; color: #94a3b8; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="box">
    <div class="spinner"></div>
    <h2>Iniciando servidor local do SIM...</h2>
    <p>Aguardando resposta em <strong>localhost:8000</strong>. A página abrirá automaticamente em instantes.</p>
  </div>
  <script>
    setInterval(async () => {
      try {
        const r = await fetch("/manifest.json", { cache: "no-store" });
        if (r.ok) window.location.reload();
      } catch (_) {}
    }, 1000);
  </script>
</body>
</html>`;
        return new Response(html, {
          status: 200,
          headers: { "Content-Type": "text/html; charset=utf-8" },
        });
      }

      return new Response("", { status: 503, statusText: "Service Unavailable" });
    })
  );
});
