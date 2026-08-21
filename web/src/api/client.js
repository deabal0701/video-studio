// REST + SSE 클라이언트 — 04_api.md 계약의 얇은 래퍼.
export async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw Object.assign(new Error(detail?.detail?.message ?? res.statusText), {
      status: res.status,
      detail: detail?.detail,
    });
  }
  return res.json();
}

// SSE 구독 — 콜백은 {event, data(parsed)} 를 받는다. 반환값으로 닫는다.
export function sse(path, onEvent) {
  const source = new EventSource(`/api${path}`);
  const relay = (event) => (e) => {
    let data = e.data;
    try {
      data = JSON.parse(e.data);
    } catch {
      /* 로그 라인 등 순수 문자열 */
    }
    onEvent({ event, data });
  };
  for (const name of ['progress', 'log', 'done', 'failed', 'job', 'fs', 'event']) {
    source.addEventListener(name, relay(name));
  }
  source.onerror = () => onEvent({ event: 'error', data: null });
  return () => source.close();
}
