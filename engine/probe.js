// 녹화 대상 앱을 열어 **실제로 조작할 수 있는 요소 목록**을 JSON 으로 뱉는다.
//
//   node engine/probe.js --url <주소> [--routes "/,/settings"] [--login-user admin]
//                        [--login-pass ****] [--save-state <파일>] [--json]
//
// 왜 필요한가: 대본의 녹화 액션은 CSS 셀렉터로 화면을 조작한다(record.js). 그런데 AI 는
// 브라우저가 없어 셀렉터를 **지어낼 수밖에 없고**, 틀린 셀렉터는 녹화에서 조용히 건너뛰어져
// (record.js 223행 "(건너뜀)") 아무 일도 안 일어난 화면이 그대로 찍힌다. 그래서 앱이 먼저
// 페이지를 열어 "여기 이런 버튼·입력칸이 있다"를 뽑아 주고, 모델은 **그 목록에서만** 고른다.
// 소재 목록에서만 B롤을 고르게 하는 것과 같은 방식이다.
//
// 01_architecture vendoring 예외에 따른 앱 전용 신규 파일 4호 (기존 엔진 파일 무수정).
import { parseArgs, resolvePlaywright } from './lib/util.js';

const args = parseArgs();
if (!args.url) {
  process.stderr.write('사용: node probe.js --url <주소> [--routes "/,/a"] [--login-user u --login-pass p]\n');
  process.exit(2);
}
const base = String(args.url).replace(/\/$/, '');
const routes = String(args.routes ?? '/')
  .split(',')
  .map((r) => r.trim())
  .filter(Boolean);
const MAX_PER_KIND = 25;

// 셀렉터는 **사람이 읽는 텍스트 기준**으로 만든다 — 클래스 해시는 배포마다 바뀌지만
// 버튼 글자는 잘 안 바뀌고, record.js 가 쓰는 Playwright 가 :has-text 를 지원한다.
function selectorFor(tag, text, placeholder, type, id) {
  if (placeholder) return `${tag}[placeholder*=${JSON.stringify(placeholder.slice(0, 14))}]`;
  if (type === 'password') return 'input[type=password]';
  if (text) return `${tag}:has-text(${JSON.stringify(text.slice(0, 20))})`;
  if (id) return `#${id}`;
  return tag;
}

const { chromium } = resolvePlaywright();
const browser = await chromium.launch({ headless: true });
const out = { url: base, routes: [] };
try {
  // 컨텍스트를 직접 만든다 — 로그인 뒤 **세션을 파일로 저장**해 녹화가 그대로 이어받는다
  // (record.js 187행 storageState). 그래야 대본·녹화 어디에도 비밀번호가 남지 않는다.
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  // 로그인은 **선택**이다 — 값은 앱이 .env 에서 읽어 넘긴다(대본에 비밀번호를 두지 않는다).
  if (args['login-user']) {
    await page.goto(`${base}/login`, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(1200);
    const user = page.locator('input[placeholder*="아이디"], input[name*="user" i], input[type=text]').first();
    await user.fill(String(args['login-user'])).catch(() => {});
    if (args['login-pass']) {
      await page.locator('input[type=password]').first().fill(String(args['login-pass'])).catch(() => {});
    }
    await page.locator('button:has-text("로그인"), button[type=submit]').first().click().catch(() => {});
    // SPA 는 로그인 직후에도 `/login?redirect=…` URL 을 잠시 들고 있다 — 고정 대기로 판정하면
    // **성공한 로그인을 실패로 읽는다** (2026-08-23 실측: 2.5초로는 이르다). 주소가 로그인
    // 화면을 벗어날 때까지 기다리되, 못 벗어나도 아래 경로 방문 결과로 다시 판단한다.
    await page
      .waitForURL((u) => !/\/login/.test(String(u)), { timeout: 15000 })
      .catch(() => {});
    await page.waitForTimeout(1200);
    out.loggedIn = !/\/login/.test(page.url());
  }

  for (const route of routes) {
    const url = route.startsWith('http') ? route : base + route;
    await page.goto(url, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(1800);
    const found = await page.evaluate((cap) => {
      const visible = (el) => {
        const r = el.getBoundingClientRect();
        return r.width > 8 && r.height > 8 && getComputedStyle(el).visibility !== 'hidden';
      };
      // **네이티브 CSS 경로** — `highlight` 액션은 브라우저의 document.querySelector 로
      // 도는데(record.js __adHighlight), 거기서는 Playwright 전용 `:has-text()` 가
      // "not a valid selector" 로 터진다. 그래서 요소마다 순수 CSS 경로도 함께 뽑는다.
      const cssPath = (el) => {
        if (el.id && document.querySelectorAll(`#${CSS.escape(el.id)}`).length === 1) {
          return `#${CSS.escape(el.id)}`;
        }
        const parts = [];
        for (let node = el; node && node.nodeType === 1 && parts.length < 6; node = node.parentElement) {
          const tag = node.tagName.toLowerCase();
          if (tag === 'html' || tag === 'body') break;
          const sibs = [...(node.parentElement?.children ?? [])].filter(
            (c) => c.tagName === node.tagName
          );
          parts.unshift(sibs.length > 1 ? `${tag}:nth-of-type(${sibs.indexOf(node) + 1})` : tag);
          const path = parts.join(' > ');
          try {
            if (document.querySelectorAll(path).length === 1) return path;
          } catch { /* 계속 올라간다 */ }
        }
        return parts.join(' > ');
      };
      const grab = (sel, kind) =>
        [...document.querySelectorAll(sel)]
          .filter(visible)
          .slice(0, cap)
          .map((el) => ({
            kind,
            tag: el.tagName.toLowerCase(),
            text: (el.innerText || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 40),
            placeholder: el.getAttribute('placeholder') || '',
            type: el.getAttribute('type') || '',
            id: el.id || '',
            cssSelector: cssPath(el),
          }))
          .filter((e) => e.text || e.placeholder);
      return {
        title: document.title,
        heading: (document.querySelector('h1, h2')?.innerText || '').trim().slice(0, 60),
        buttons: grab('button, a[href], [role=button]', 'click'),
        inputs: grab('input, textarea', 'type'),
        scrollable: document.body.scrollHeight > window.innerHeight + 100,
      };
    }, MAX_PER_KIND);

    for (const list of [found.buttons, found.inputs]) {
      for (const e of list) e.selector = selectorFor(e.tag, e.text, e.placeholder, e.type, e.id);
    }
    out.routes.push({ route, url: page.url(), ...found });
  }

  // 세션 저장은 **경로를 다 돌아본 뒤**에 한다 — 로그인 직후 판정은 SPA 타이밍에 흔들리지만,
  // 실제로 들어간 화면의 주소는 흔들리지 않는다. 여기서 로그인 여부를 확정한다.
  if (args['login-user']) {
    out.loggedIn = out.routes.some((r) => !/\/login/.test(String(r.url)));
    if (out.loggedIn && args['save-state']) {
      await context.storageState({ path: String(args['save-state']) });
      out.stateSaved = String(args['save-state']);
    }
  }
} finally {
  await browser.close().catch(() => {});
}
process.stdout.write(JSON.stringify(out, null, args.json ? 0 : 1));
