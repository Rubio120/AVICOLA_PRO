const baseValue = process.env.SMOKE_BASE_URL;
const requestCount = Number(process.env.SMOKE_REQUESTS ?? "20");
const concurrency = Number(process.env.SMOKE_CONCURRENCY ?? "2");
const timeoutMs = Number(process.env.SMOKE_TIMEOUT_MS ?? "10000");
const p95Budget = process.env.SMOKE_P95_BUDGET_MS ? Number(process.env.SMOKE_P95_BUDGET_MS) : null;
const requireAuth = process.env.SMOKE_REQUIRE_AUTH === "true";
const identity = process.env.SMOKE_AUTH_IDENTITY;
const password = process.env.SMOKE_AUTH_PASSWORD;

function configuration() {
  if (!baseValue) throw new Error("SMOKE_BASE_URL is required");
  const base = new URL(baseValue);
  if (!new Set(["https:", "http:"]).has(base.protocol) || base.username || base.password) {
    throw new Error("SMOKE_BASE_URL must be an HTTP(S) origin without embedded credentials");
  }
  if (base.protocol !== "https:" && !new Set(["localhost", "127.0.0.1", "::1"]).has(base.hostname)) {
    throw new Error("HTTPS is required except for loopback smoke targets");
  }
  if (!Number.isInteger(requestCount) || requestCount < 1 || requestCount > 500) {
    throw new Error("SMOKE_REQUESTS must be between 1 and 500");
  }
  if (!Number.isInteger(concurrency) || concurrency < 1 || concurrency > 25) {
    throw new Error("SMOKE_CONCURRENCY must be between 1 and 25");
  }
  if (!Number.isFinite(timeoutMs) || timeoutMs < 100 || timeoutMs > 120000) {
    throw new Error("SMOKE_TIMEOUT_MS is outside the allowed range");
  }
  if (p95Budget !== null && (!Number.isFinite(p95Budget) || p95Budget < 1)) {
    throw new Error("SMOKE_P95_BUDGET_MS must be positive");
  }
  if ((identity && !password) || (!identity && password) || (requireAuth && (!identity || !password))) {
    throw new Error("Provide both synthetic auth credentials or require them explicitly");
  }
  return base;
}

async function authenticate(base) {
  const login = await fetch(new URL("/api/v1/auth/login", base), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ identity, password }),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!login.ok) throw new Error("Synthetic login smoke failed");
  const cookie = login.headers
    .getSetCookie()
    .map((value) => value.split(";", 1)[0])
    .filter(Boolean)
    .join("; ");
  const csrf = login.headers.get("x-csrf-token");
  if (!cookie || !csrf) throw new Error("Login response omitted session or CSRF state");

  const current = await fetch(new URL("/api/v1/auth/me", base), {
    headers: { cookie },
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!current.ok) throw new Error("Synthetic authenticated-session smoke failed");

  const logout = await fetch(new URL("/api/v1/auth/logout", base), {
    method: "POST",
    headers: { cookie, "x-csrf-token": csrf },
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!logout.ok) throw new Error("Synthetic logout smoke failed");
  return "passed-login-me-logout";
}

function percentile(samples, value) {
  return samples[Math.max(0, Math.ceil(value * samples.length) - 1)];
}

async function main() {
  const base = configuration();
  const samples = [];
  let errors = 0;
  let next = 0;
  const workers = Array.from({ length: Math.min(concurrency, requestCount) }, async () => {
    while (next < requestCount) {
      next += 1;
      const started = performance.now();
      try {
        const response = await fetch(new URL("/", base), { signal: AbortSignal.timeout(timeoutMs) });
        samples.push(performance.now() - started);
        if (!response.ok) errors += 1;
        await response.body?.cancel();
      } catch {
        samples.push(performance.now() - started);
        errors += 1;
      }
    }
  });
  await Promise.all(workers);
  samples.sort((left, right) => left - right);
  const p50 = Math.round(percentile(samples, 0.5));
  const p95 = Math.round(percentile(samples, 0.95));
  const errorRate = errors / requestCount;
  const authStatus = identity && password ? await authenticate(base) : "skipped-no-synthetic-account";
  const summary = { requests: requestCount, concurrency, p50_ms: p50, p95_ms: p95, error_rate: errorRate, auth: authStatus };
  process.stdout.write(`${JSON.stringify(summary)}\n`);
  if (errors || (p95Budget !== null && p95 > p95Budget)) process.exitCode = 1;
}

main().catch(() => {
  process.stderr.write("Smoke check failed; response bodies and credentials withheld\n");
  process.exitCode = 1;
});
