// 모션 html 1장을 자체완결 문서로 — 앱 iframe 프리뷰용 기계 CLI.
//
//   node engine/preview.js --file <이름|경로> [--project <회차 폴더>]
//
// stdout 으로 상대 참조(_base.css·_params.js 등 같은 폴더 계열 css/js)를 인라인한 html 을
// 뱉는다. params 는 여기서 처리하지 않는다 — 이 문서를 서빙하는 URL 의 질의 문자열이 담당한다
// (_params.js 가 location.search 를 읽는 엔진 렌더 방식 그대로라, 프리뷰 결과가 곧 실물이다).
// 경로형 params(src·fontUrl)는 앱이 API 자산 URL 로 바꿔 넘긴다.
//
// 01_architecture 의 vendoring 예외 조항에 따른 앱 전용 신설 파일 — 기존 엔진 파일 무수정.
import fs from 'node:fs';
import path from 'node:path';
import { AD_DIR, parseArgs } from './lib/util.js';

const args = parseArgs();
if (!args.file) {
  process.stderr.write('사용: node preview.js --file <이름|경로> [--project <회차 폴더>]\n');
  process.exit(2);
}

// compose.js resolveMotionFile 과 같은 순서 — 회차 전용 먼저, 공용 motion/ 폴백.
const candidates = [
  args.project && path.resolve(String(args.project), String(args.file)),
  path.resolve(AD_DIR, 'motion', String(args.file)),
  path.resolve(String(args.file)),
].filter(Boolean);
const source = candidates.find((f) => fs.existsSync(f) && fs.statSync(f).isFile());
if (!source) {
  process.stderr.write(`템플릿을 찾지 못했습니다: ${args.file}\n`);
  process.exit(2);
}

const dir = path.dirname(source);
let html = fs.readFileSync(source, 'utf8');

const inline = (ref) => {
  const f = path.resolve(dir, ref);
  return fs.existsSync(f) ? fs.readFileSync(f, 'utf8') : null;
};

// <link rel="stylesheet" href="상대.css"> → <style>…</style>
html = html.replace(
  /<link\b[^>]*href="([^"]+\.css)"[^>]*>/g,
  (tag, ref) => {
    if (/^[a-z]+:/i.test(ref)) return tag; // 외부 URL 은 그대로
    const css = inline(ref);
    return css === null ? tag : `<style>\n${css}\n</style>`;
  }
);

// <script src="상대.js"></script> → <script>…</script>
html = html.replace(
  /<script\b[^>]*src="([^"]+\.js)"[^>]*>\s*<\/script>/g,
  (tag, ref) => {
    if (/^[a-z]+:/i.test(ref)) return tag;
    const js = inline(ref);
    return js === null ? tag : `<script>\n${js}\n</script>`;
  }
);

process.stdout.write(html);
