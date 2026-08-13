/* ============================================================
   희우 · 우희 청첩장 — 공통 스크립트

   index.html(본 화면) 과 index.trip.html(Trip 시안) 이 이 파일 하나를
   함께 씁니다. 두 화면의 마크업이 완전히 같지는 않으므로, 각 기능은
   자기 DOM 이 있을 때만 동작합니다. 없는 화면에서는 조용히 넘어갑니다.

   화면별로 다른 값은 <body> 의 data-* 로 넘깁니다.
     · 갤러리 배치   data-gallery-layout="square" 면 정사각 3열
     · 사진 장수     data-gallery="9"
     · 공유 주소     data-share-url="…"   (없으면 CONFIG.shareUrl)
     · 상태바 고정   data-tint-fixed      (있으면 theme-color 를 건드리지 않음)
     · 표지 상태바   data-cover-tint="…"  (스크롤을 따라 바꿀 때 쓰는 색)
   ============================================================ */

/* ============================================================
   설정 — 내용을 바꿀 일이 있으면 여기부터 보세요.
   ============================================================ */
const CONFIG = {
  wedding: new Date(2026, 9, 25, 15, 0),  // 2026-10-25 15:00 (월은 0부터)
  groom: "희우",
  bride: "우희",
  venue: "토브헤세드",
  address: "서울특별시 강남구 논현2동 도산대로 38길 32",
  lat: 37.5185551,
  lng: 127.0327655,

  // 네이버 클라우드 플랫폼 > Maps > Application 의 Key ID.
  // 같은 Application 의 "Web 서비스 URL" 에 이 페이지의 도메인도 등록해야 합니다.
  naverKeyId: "8ecuewium6",

  // 공유로 나가는 기본 주소. 화면마다 다르게 하려면 <body data-share-url="…"> 로 덮어씁니다.
  shareUrl: "https://heewoo0419.github.io/wedding-invitation/",
  shareImage: "https://heewoo0419.github.io/wedding-invitation/og-image.jpg",

  // 카카오톡 카드·시스템 공유에 찍히는 제목. og:title 과 같은 문구로 맞춰 두세요.
  shareTitle: "희우 💍 우희 결혼합니다.",
  shareText: "2026년 10월 25일 일요일 오후 3시 · 토브헤세드",

  // 카카오톡 카드 전용. 1:1 정사각(800×800) — 카카오가 권장하는 크기 형태입니다.
  // 세로로 길게 두면(2:3, 1:2) 카드에서 위아래가 잘립니다.
  // 카카오는 이 주소로 받은 그림을 자기 서버에 캐시합니다. 그림을 갈 때는
  // 파일명을 함께 바꿔야 새 그림이 나갑니다.
  kakaoImage: "https://heewoo0419.github.io/wedding-invitation/kakao-share-cover-1x1.jpg",
  kakaoDesc: "귀한 걸음으로 함께해 주세요.",

  // 카카오톡 공유(미리보기 카드)에 필요한 JavaScript 키.
  //   https://developers.kakao.com → 내 애플리케이션 → 앱 키 → JavaScript 키
  //   같은 화면의 [플랫폼 > Web] 에 이 페이지 도메인도 등록해야 합니다.
  // 비워 두면 카카오톡 버튼이 시스템 공유(또는 주소 복사)로 대신 동작합니다.
  kakaoKey: "02485fdd8eff4ae4475876a8d91a1e7f",

  gallery: 15,          // assets/photos/gallery-01.jpg … 순서로 읽습니다
  galleryVisible: 6,    // 처음에 보여줄 장수 (나머지는 "더 보기")

  // 사진 원본 크기. img 의 width·height 속성으로 넣어 자리를 미리 잡습니다.
  // 사진을 바꾸면 이 값도 함께 고쳐야 지연 로딩 중 배치가 흔들리지 않습니다.
  //   확인:  sips -g pixelWidth -g pixelHeight assets/photos/gallery-01.jpg
  gallerySize: {
    default: [1280, 1920],   // 대부분의 세로 사진
    1:  [1280, 1886],
    15: [1280, 853]          // 가로 사진
  }
};

/* 화면이 따로 지정한 값이 있으면 그것을 씁니다 */
const PAGE = {
  gallery: Number(document.body.dataset.gallery) || CONFIG.gallery,
  square: document.body.dataset.galleryLayout === "square",
  // 공유 주소 — 화면마다 자기 주소를 내보냅니다.
  //   본 화면: 속성이 없어 CONFIG.shareUrl(=본 화면 주소)
  //   시안:    data-share-url="…/index.trip.html"
  shareUrl: document.body.dataset.shareUrl || CONFIG.shareUrl
};

/* ---------- 토스트 · 복사 ---------- */
const toast = document.getElementById("toast");
let toastTimer;
function showToast(msg){
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add("on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("on"), 2000);
}
async function copyText(text){
  try {
    await navigator.clipboard.writeText(text);
    showToast("복사했습니다");
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch {}
    document.body.removeChild(ta);
    showToast(ok ? "복사했습니다" : "복사할 수 없습니다. 길게 눌러 선택해 주세요");
  }
}
document.querySelectorAll("[data-copy]").forEach(btn => {
  btn.addEventListener("click", () => copyText(btn.dataset.copy));
});

/* ---------- 갤러리 ----------
   본 화면은 세로·가로가 섞인 벽돌 배치에 "더 보기"를 두고,
   시안은 정사각 3열 한 판만 깝니다. 어느 쪽이든 타일은 .tile 이라서
   아래 라이트박스가 그대로 집어 씁니다.                        */
(function buildGallery(){
  const grid = document.getElementById("grid");
  if (!grid) return;

  let html = "";
  for (let i = 1; i <= PAGE.gallery; i++) {
    const no = String(i).padStart(2, "0");
    const [w, h] = CONFIG.gallerySize[i] || CONFIG.gallerySize.default;

    // 정사각 배치에서는 감출 것도, 가로로 늘일 것도 없습니다
    const hidden = (!PAGE.square && i > CONFIG.galleryVisible) ? " is-hidden" : "";
    const wide = (!PAGE.square && w > h) ? " is-wide" : "";

    html +=
      '<button class="tile' + hidden + wide + '" type="button" aria-label="사진 ' + i + ' 크게 보기">' +
        '<img src="assets/photos/gallery-' + no + '.jpg" alt="" loading="lazy" decoding="async"' +
          ' width="' + w + '" height="' + h + '"' +
          ' onerror="this.parentElement.classList.add(\'is-empty\');this.remove()">' +
      '</button>';
  }
  grid.innerHTML = html;

  const moreBtn = document.getElementById("moreBtn");
  if (!moreBtn) return;
  if (PAGE.square || PAGE.gallery <= CONFIG.galleryVisible) { moreBtn.remove(); return; }
  moreBtn.addEventListener("click", () => {
    grid.querySelectorAll(".is-hidden").forEach(el => el.classList.remove("is-hidden"));
    moreBtn.remove();
  });
})();

/* ---------- 달력 ----------
   앞뒤 달의 날짜까지 흐리게 채워 격자를 항상 채웁니다. */
(function buildCalendar(){
  const cal = document.getElementById("cal");
  if (!cal) return;

  const d = CONFIG.wedding;
  const y = d.getFullYear(), m = d.getMonth(), day = d.getDate();
  const first = new Date(y, m, 1).getDay();
  const last = new Date(y, m + 1, 0).getDate();
  const prevLast = new Date(y, m, 0).getDate();
  const dows = ["일","월","화","수","목","금","토"];

  let html = '<thead><tr>';
  dows.forEach((w, i) => html += '<th scope="col" class="' + (i === 0 ? "sun" : "") + '">' + w + '</th>');
  html += '</tr></thead><tbody>';

  const cells = [];
  for (let i = first - 1; i >= 0; i--) cells.push({ n: prevLast - i, out: true });
  for (let n = 1; n <= last; n++) cells.push({ n, out: false });
  while (cells.length % 7 !== 0) cells.push({ n: cells.length % 7, out: true });

  cells.forEach((c, i) => {
    if (i % 7 === 0) html += "<tr>";
    const cls = [
      i % 7 === 0 ? "sun" : "",
      c.out ? "out" : "",
      (!c.out && c.n === day) ? "mark" : ""
    ].filter(Boolean).join(" ");
    html += '<td class="' + cls + '"><span>' + c.n + '</span></td>';
    if (i % 7 === 6) html += "</tr>";
  });

  html += "</tbody>";
  cal.innerHTML = html;
})();

/* ---------- 카운트다운 · D-day ---------- */
(function countdown(){
  const cells = {
    day: document.getElementById("cDay"),
    hour: document.getElementById("cHour"),
    min: document.getElementById("cMin"),
    sec: document.getElementById("cSec")
  };
  const ddayEl = document.getElementById("dday");
  if (!ddayEl && !cells.day) return;

  const pad = n => String(n).padStart(2, "0");

  function tick(){
    const gap = CONFIG.wedding - new Date();

    if (cells.day) {
      if (gap > 0) {
        const s = Math.floor(gap / 1000);
        cells.day.textContent = Math.floor(s / 86400);
        cells.hour.textContent = pad(Math.floor(s % 86400 / 3600));
        cells.min.textContent = pad(Math.floor(s % 3600 / 60));
        cells.sec.textContent = pad(s % 60);
      } else {
        Object.values(cells).forEach(el => el && (el.textContent = "00"));
      }
    }

    if (ddayEl) {
      const today = new Date(); today.setHours(0, 0, 0, 0);
      const wedDay = new Date(CONFIG.wedding); wedDay.setHours(0, 0, 0, 0);
      const diff = Math.round((wedDay - today) / 86400000);

      ddayEl.innerHTML = diff > 0
        ? CONFIG.groom + ", " + CONFIG.bride + "의 결혼식이 <b>" + diff + "일</b> 남았습니다."
        : diff === 0
          ? "오늘은 " + CONFIG.groom + "과 " + CONFIG.bride + "의 결혼식입니다."
          : "함께한 지 <b>" + Math.abs(diff) + "일</b>이 되었습니다.";
    }
  }

  tick();
  setInterval(tick, 1000);
})();

/* ============================================================
   네이버 지도 (Maps JavaScript API v3)
   Key ID 가 비어 있으면 스크립트를 요청하지 않고 질감만 남습니다.
   ============================================================ */
function initNaverMap(){
  const el = document.getElementById("map");
  if (!el || !window.naver || !window.naver.maps) return;

  const position = new naver.maps.LatLng(CONFIG.lat, CONFIG.lng);

  const map = new naver.maps.Map(el, {
    center: position,
    zoom: 16,
    minZoom: 12,
    scrollWheel: false,        // 페이지 스크롤이 지도에 갇히지 않게
    scaleControl: false,
    mapDataControl: false,
    logoControl: true,         // 네이버 로고는 이용약관상 표시 유지
    logoControlOptions: { position: naver.maps.Position.BOTTOM_LEFT },
    zoomControl: true,
    zoomControlOptions: {
      style: naver.maps.ZoomControlStyle.SMALL,
      position: naver.maps.Position.TOP_RIGHT
    }
  });

  new naver.maps.Marker({
    map: map,
    position: position,
    title: CONFIG.venue,
    icon: {
      content:
        '<svg width="30" height="38" viewBox="0 0 30 38" xmlns="http://www.w3.org/2000/svg">' +
          '<path d="M15 37s12-13.2 12-22A12 12 0 1 0 3 15c0 8.8 12 22 12 22z" fill="#2b2926"/>' +
          '<circle cx="15" cy="14.6" r="4.4" fill="#fff"/>' +
        '</svg>',
      size: new naver.maps.Size(30, 38),
      anchor: new naver.maps.Point(15, 38)
    }
  });

  naver.maps.Event.addListener(map, "dblclick", () => map.setCenter(position));

  el.classList.add("loaded");
  el.removeAttribute("role");
  el.removeAttribute("aria-label");
}

(function loadNaverMap(){
  if (!CONFIG.naverKeyId || !document.getElementById("map")) return;
  const s = document.createElement("script");
  s.src = "https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=" + encodeURIComponent(CONFIG.naverKeyId);
  s.async = true;
  s.onload = initNaverMap;
  s.onerror = () => console.warn("[naver maps] 스크립트 로드 실패 — Key ID 와 등록된 Web 서비스 URL 을 확인하세요.");
  document.head.appendChild(s);
})();

/* ============================================================
   지도 앱 연동 — 앱 스킴 먼저, 실패하면 웹/스토어로 폴백
   모바일: nmap:// · kakaomap:// · tmap:// 실행 시도
           1.1초 안에 화면이 그대로면(=앱 없음) 폴백 주소로 이동
   데스크톱: 앱 스킴을 건너뛰고 <a href> 의 웹 주소를 그대로 사용
             (티맵은 웹 지도가 없어 주소 복사로 안내)
   ============================================================ */
const UA = navigator.userAgent;
const isMobile = /iPhone|iPad|iPod|Android/i.test(UA);

const MAP_APPS = {
  naver: {
    scheme: () => "nmap://place?lat=" + CONFIG.lat + "&lng=" + CONFIG.lng +
                  "&name=" + encodeURIComponent(CONFIG.venue) +
                  "&appname=" + encodeURIComponent(location.hostname || "wedding.invitation")
  },
  kakao: {
    scheme: () => "kakaomap://look?p=" + CONFIG.lat + "," + CONFIG.lng
  },
  tmap: {
    scheme: () => "tmap://route?goalname=" + encodeURIComponent(CONFIG.venue) +
                  "&goalx=" + CONFIG.lng + "&goaly=" + CONFIG.lat,
    // 티맵은 웹 지도가 없습니다. 앱이 없으면 설치 페이지로 안내합니다.
    fallback: () => /iPhone|iPad|iPod/i.test(UA)
      ? "https://apps.apple.com/kr/app/id431589174"
      : "https://play.google.com/store/apps/details?id=com.skt.tmap.ku"
  }
};

/* 앱 스킴을 시도하고, 화면이 그대로면 폴백 주소로 넘깁니다.
   토스 송금도 같은 방식이라 함께 씁니다. */
function tryAppScheme(scheme, onStay){
  let moved = false;
  const onHide = () => { moved = true; };
  document.addEventListener("visibilitychange", onHide, { once:true });
  window.addEventListener("pagehide", onHide, { once:true });

  setTimeout(() => {
    document.removeEventListener("visibilitychange", onHide);
    window.removeEventListener("pagehide", onHide);
    if (moved || document.hidden) return;   // 앱으로 전환됨
    onStay();
  }, 1100);

  location.href = scheme;
}

function openMapApp(key, webUrl){
  const app = MAP_APPS[key];
  if (!app) return;
  if (app.fallback) webUrl = app.fallback();
  tryAppScheme(app.scheme(), () => { location.href = webUrl; });
}

document.querySelectorAll("[data-map]").forEach(el => {
  el.addEventListener("click", e => {
    if (!isMobile) {                        // 데스크톱
      if (!el.href) {                       // 웹 지도가 없는 앱(티맵)
        copyText(CONFIG.address);
        showToast("티맵은 휴대폰에서 열립니다. 주소를 복사했어요");
      }
      return;                               // 나머지는 기본 링크 사용
    }
    e.preventDefault();
    openMapApp(el.dataset.map, el.href);
  });
});

/* ---------- 토스로 송금 ----------
   supertoss:// 는 토스 앱이 깔린 기기에서만 열립니다.
   PC 이거나 앱이 없으면 아무 일도 일어나지 않으므로,
   그 경우에는 계좌번호를 복사해 주고 안내합니다.               */
document.querySelectorAll(".toss").forEach(btn => {
  btn.addEventListener("click", () => {
    const bank = btn.dataset.bank, account = btn.dataset.account;

    if (!isMobile) {                       // PC 는 토스 앱이 없습니다
      copyText(account);
      showToast("계좌번호를 복사했습니다. 토스 송금은 휴대폰에서 열어 주세요");
      return;
    }

    tryAppScheme(
      "supertoss://send?bank=" + encodeURIComponent(bank) + "&accountNo=" + encodeURIComponent(account),
      () => {
        copyText(account);                 // 앱이 없으면 복사로 대신합니다
        showToast("토스 앱이 없어 계좌번호를 복사했습니다");
      }
    );
  });
});

/* ---------- 접었다 펴는 영역 ----------
   본 화면은 .acc-head 가 부모의 .open 을 토글하고,
   시안은 [data-panel] 이 대상 패널의 data-open 을 바꿉니다. */
document.querySelectorAll(".acc-head").forEach(head => {
  head.addEventListener("click", () => {
    const open = head.parentElement.classList.toggle("open");
    head.setAttribute("aria-expanded", String(open));
  });
});
document.querySelectorAll("[data-panel]").forEach(btn => {
  btn.addEventListener("click", () => {
    const panel = document.getElementById(btn.dataset.panel);
    if (!panel) return;
    const open = panel.dataset.open === "true";
    panel.dataset.open = String(!open);
    btn.setAttribute("aria-expanded", String(!open));
  });
});

/* ---------- 라이트박스 ----------
   슬라이드 세 칸(이전·현재·다음)을 나란히 두고 트랙을 -100% 에 놓습니다.
   손가락을 따라 트랙을 밀고, 놓으면 옆 칸까지 마저 밀거나 제자리로 돌립니다.
   전환이 끝나면 인덱스를 옮기고 트랙을 소리 없이 -100% 로 되돌려,
   몇 장을 넘겨도 늘 가운데 칸을 보고 있는 상태가 됩니다.               */
(function lightbox(){
  const tiles = [...document.querySelectorAll(".tile")];
  const lightbox = document.getElementById("lightbox");
  const lbTrack = document.getElementById("lbTrack");
  if (!tiles.length || !lightbox || !lbTrack) return;

  const lbSlides = [...lbTrack.children];
  const lbCount = document.getElementById("lbCount");
  let lbIndex = 0, lastFocused = null, sliding = false;

  const EASE = "transform .3s cubic-bezier(.22,.61,.36,1)";

  function fillSlide(slide, i){
    const idx = (i + tiles.length) % tiles.length;
    const source = tiles[idx].querySelector("img");
    slide.innerHTML = "";
    if (source) {
      slide.style.background = "none";
      const img = document.createElement("img");
      img.src = source.src;
      img.alt = source.alt || "";
      slide.appendChild(img);
    } else {
      // 사진을 아직 넣지 않은 자리
      slide.style.background = "linear-gradient(150deg,#efedeb,#e4e1de 48%,#eceae7)";
    }
  }
  function setTrack(x, animate){
    lbTrack.style.transition = animate ? EASE : "none";
    lbTrack.style.transform = "translate3d(" + x + ",0,0)";
  }
  function renderLb(){
    fillSlide(lbSlides[0], lbIndex - 1);
    fillSlide(lbSlides[1], lbIndex);
    fillSlide(lbSlides[2], lbIndex + 1);
    setTrack("-100%", false);
    if (lbCount) lbCount.textContent = (lbIndex + 1) + " / " + tiles.length;
  }
  function openLb(i){
    lbIndex = i;
    lastFocused = document.activeElement;
    renderLb();
    lightbox.classList.add("on");
    document.body.style.overflow = "hidden";
    lightbox.querySelector(".lb-close").focus();
  }
  function closeLb(){
    lightbox.classList.remove("on");
    document.body.style.overflow = "";
    if (lastFocused) lastFocused.focus();
  }
  function move(step){
    if (sliding || !step) return;
    sliding = true;
    setTrack((-100 - step * 100) + "%", true);

    const done = () => {
      lbIndex = (lbIndex + step + tiles.length) % tiles.length;
      renderLb();            // 트랙을 다시 가운데로 (애니메이션 없이)
      sliding = false;
    };
    // transitionend 가 오지 않는 경우(탭 전환 등)를 대비해 시간으로도 마무리합니다
    let settled = false;
    const once = () => { if (settled) return; settled = true; done(); };
    lbTrack.addEventListener("transitionend", once, { once: true });
    setTimeout(once, 360);
  }

  tiles.forEach((t, i) => t.addEventListener("click", () => openLb(i)));
  lightbox.querySelector(".lb-close").addEventListener("click", closeLb);
  lightbox.querySelector(".lb-prev").addEventListener("click", () => move(-1));
  lightbox.querySelector(".lb-next").addEventListener("click", () => move(1));
  lightbox.addEventListener("click", e => { if (e.target === lightbox) closeLb(); });
  document.addEventListener("keydown", e => {
    if (!lightbox.classList.contains("on")) return;
    if (e.key === "Escape") closeLb();
    if (e.key === "ArrowLeft") move(-1);
    if (e.key === "ArrowRight") move(1);
  });

  /* 스와이프 — 손가락을 따라 사진이 움직이고, 놓으면 넘어가거나 제자리로.
     아래로 크게 내리면 닫습니다. 손가락이 둘 이상이면(핀치 확대) 건드리지 않습니다. */
  const LOCK = 8;      // 이만큼 움직인 방향으로 가로/세로를 정합니다
  const CLOSE = 90;    // 닫을 최소 거리(px)
  const FLICK = 0.5;   // 이 속도(px/ms) 이상이면 짧게 튕겨도 넘깁니다

  let x0 = 0, y0 = 0, t0 = 0;
  let active = false, axis = "", width = 0;

  lightbox.addEventListener("touchstart", e => {
    if (e.touches.length !== 1 || sliding) { active = false; return; }
    const t = e.changedTouches[0];
    x0 = t.clientX; y0 = t.clientY; t0 = Date.now();
    active = true; axis = "";
    width = lbTrack.getBoundingClientRect().width || 1;
  }, { passive: true });

  lightbox.addEventListener("touchmove", e => {
    if (!active || e.touches.length !== 1) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - x0, dy = t.clientY - y0;

    if (!axis) {
      if (Math.abs(dx) < LOCK && Math.abs(dy) < LOCK) return;
      axis = Math.abs(dx) > Math.abs(dy) ? "x" : "y";
    }
    if (axis !== "x") return;

    // 양 끝에서도 순환하므로 저항 없이 그대로 따라갑니다
    setTrack("calc(-100% + " + dx + "px)", false);
  }, { passive: true });

  lightbox.addEventListener("touchend", e => {
    if (!active || e.touches.length) return;
    active = false;

    const t = e.changedTouches[0];
    const dx = t.clientX - x0, dy = t.clientY - y0;
    const speed = Math.abs(dx) / Math.max(Date.now() - t0, 1);

    if (axis === "x") {
      // 절반을 넘겼거나 빠르게 튕겼으면 넘기고, 아니면 제자리로
      if (Math.abs(dx) > width * 0.28 || speed > FLICK) move(dx < 0 ? 1 : -1);
      else setTrack("-100%", true);
      return;
    }
    if (dy > CLOSE && dy > Math.abs(dx) * 1.4) closeLb();
  }, { passive: true });
})();

/* ---------- 일정 저장 (.ics) ---------- */
(function saveIcs(){
  const btn = document.getElementById("icsBtn");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const start = CONFIG.wedding;
    const end = new Date(start.getTime() + 2 * 60 * 60 * 1000);
    const fmt = d => d.getFullYear() +
      String(d.getMonth() + 1).padStart(2, "0") + String(d.getDate()).padStart(2, "0") + "T" +
      String(d.getHours()).padStart(2, "0") + String(d.getMinutes()).padStart(2, "0") + "00";
    const ics = [
      "BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//wedding//KR","BEGIN:VEVENT",
      "SUMMARY:" + CONFIG.groom + " · " + CONFIG.bride + " 결혼식",
      "DTSTART;TZID=Asia/Seoul:" + fmt(start),
      "DTEND;TZID=Asia/Seoul:" + fmt(end),
      "LOCATION:" + CONFIG.venue + " " + CONFIG.address,
      "END:VEVENT","END:VCALENDAR"
    ].join("\r\n");
    const url = URL.createObjectURL(new Blob([ics], { type: "text/calendar;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url; a.download = "wedding.ics";
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast("캘린더 파일을 내려받았습니다");
  });
})();

/* ---------- 카카오톡 공유 ----------
   미리보기 카드로 보내려면 Kakao SDK 와 JavaScript 키가 필요합니다.
   키가 없거나 SDK 를 못 받았으면 시스템 공유 → 주소 복사 순으로 대신합니다.
   (developers.kakao.com 의 [플랫폼 > Web] 에 이 페이지 도메인이 등록되어 있어야
    전송이 성공합니다. localhost 로 열어 볼 때도 등록이 필요합니다.)     */
(function kakaoShare(){
  const btn = document.getElementById("kakaoBtn");
  if (!btn) return;

  let ready = false;

  /* 카드 이미지의 원본 크기를 미리 읽어 둡니다.
     크기를 알려 주지 않으면 카카오가 카드를 작은 형태로 접고 버튼도 가려집니다.
     값을 박아 두지 않고 이미지에서 읽으므로, og-image 를 다른 비율로 바꿔도
     그 비율이 그대로 전달됩니다. */
  let imageSize = null;
  (function measureShareImage(){
    const probe = new Image();
    probe.onload = () => {
      if (probe.naturalWidth) imageSize = { w: probe.naturalWidth, h: probe.naturalHeight };
    };
    probe.src = CONFIG.kakaoImage || CONFIG.shareImage;
  })();

  if (CONFIG.kakaoKey) {
    const s = document.createElement("script");
    s.src = "https://t1.kakaocdn.net/kakao_js_sdk/2.7.5/kakao.min.js";
    s.async = true;
    s.crossOrigin = "anonymous";
    s.onload = () => {
      try {
        if (!window.Kakao.isInitialized()) window.Kakao.init(CONFIG.kakaoKey);
        ready = true;
      } catch (e) {
        console.warn("[kakao] 초기화 실패 — JavaScript 키를 확인하세요.", e);
      }
    };
    s.onerror = () => console.warn("[kakao] SDK 로드 실패 — 주소 복사로 대신합니다.");
    document.head.appendChild(s);
  }

  async function fallback(){
    const data = {
      title: CONFIG.shareTitle,
      text: CONFIG.shareText,
      url: PAGE.shareUrl
    };
    if (navigator.share) {
      try { await navigator.share(data); return; } catch {}
    }
    copyText(PAGE.shareUrl);
    showToast("주소를 복사했습니다. 카카오톡에 붙여 넣어 주세요");
  }

  btn.addEventListener("click", () => {
    if (!ready) { fallback(); return; }

    const link = { mobileWebUrl: PAGE.shareUrl, webUrl: PAGE.shareUrl };
    const content = {
      title: CONFIG.shareTitle,
      description: CONFIG.kakaoDesc || CONFIG.shareText,
      imageUrl: CONFIG.kakaoImage || CONFIG.shareImage,
      link: link
    };
    if (imageSize) {                       // 원본 비율 그대로
      content.imageWidth = imageSize.w;
      content.imageHeight = imageSize.h;
    }

    /* Feed B형 — content 아래에 항목 목록과 요약을 덧붙인 형태입니다.
       https://developers.kakao.com/docs/ko/message-template/common#feed-b
       item 은 짧게(6자 안쪽), 표시되는 줄 수 제한이 있어 항목은 둘만 둡니다. */
    const itemContent = {
      profileText: CONFIG.groom + " · " + CONFIG.bride,
      items: [
        { item: "예식", itemOp: "10월 25일 (일) 오후 3시" },
        { item: "장소", itemOp: CONFIG.venue + " · 강남" }
      ]
    };

    try {
      window.Kakao.Share.sendDefault({
        objectType: "feed",
        content: content,
        itemContent: itemContent,
        buttons: [{ title: "청첩장 보기", link: link }],
        installTalk: true
      });
    } catch (e) {
      console.warn("[kakao] 전송 실패 — 도메인 등록 여부를 확인하세요.", e);
      fallback();
    }
  });
})();

/* ---------- 공유 ---------- */
(function share(){
  const linkBtn = document.getElementById("linkBtn");
  const shareBtn = document.getElementById("shareBtn");

  if (linkBtn) linkBtn.addEventListener("click", () => copyText(PAGE.shareUrl));

  if (shareBtn) shareBtn.addEventListener("click", async () => {
    const data = {
      title: CONFIG.shareTitle,
      text: CONFIG.shareText,
      url: PAGE.shareUrl
    };
    if (navigator.share) {
      try { await navigator.share(data); } catch {}
      return;
    }
    copyText(data.url);
  });
})();

/* ---------- 상태바 색 ----------
   표지가 화면 맨 위에 걸쳐 있는 동안에는 사진 톤,
   본문으로 넘어가면 흰색. iOS Safari 상단 바가 이 값을 따라갑니다.
   표지 톤은 <body data-cover-tint="#000"> 으로 지정합니다. meta 에는 표준 속성만
   두는 편이 안전해서(사파리가 초기 값을 그대로 읽습니다) body 쪽에 적습니다. */
(function statusBarTint(){
  const meta = document.querySelector('meta[name="theme-color"]');
  const cover = document.querySelector('.cover');
  if (!meta || !cover) return;

  /* 아이폰 사파리는 문서를 읽는 시점의 theme-color 만 보고, 그 뒤 JS 로 바꾼 값은
     반영하지 않습니다. 그래서 색을 하나로 두고 갈 화면은 아예 건드리지 않습니다.
     <body data-tint-fixed> 를 두면 meta 에 적힌 값이 그대로 남습니다. */
  if (document.body.hasAttribute("data-tint-fixed")) return;

  const COVER = document.body.dataset.coverTint || meta.dataset.cover || "#4a352d";
  const PAGE_TINT = "#ffffff";
  let current = meta.getAttribute("content");

  // 요소 하나의 위치만 읽으므로 스크롤마다 그대로 호출해도 부담이 없습니다.
  // requestAnimationFrame 으로 묶으면 탭이 백그라운드일 때 갱신이 멈춥니다.
  function apply(){
    const r = cover.getBoundingClientRect();
    // 표지가 화면에 조금이라도 남아 있으면 사진 톤.
    // top <= 0 으로 재면 맨 위에서 당겼을 때(오버스크롤) 잠깐 흰색으로 튑니다.
    const next = (r.bottom > 0 && r.top < innerHeight) ? COVER : PAGE_TINT;
    if (next !== current) { current = next; meta.setAttribute("content", next); }
  }
  addEventListener("scroll", apply, { passive: true });
  addEventListener("resize", apply, { passive: true });
  apply();
})();

/* ---------- 스크롤 등장 ----------
   본 화면은 .reveal, 시안은 .rise 를 씁니다. 등장 시점이 조금 달라
   관찰자를 따로 둡니다. */
(function reveal(){
  const watch = (selector, options) => {
    const targets = document.querySelectorAll(selector);
    if (!targets.length) return;
    const io = new IntersectionObserver(list => {
      list.forEach(en => {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, options);
    targets.forEach(el => io.observe(el));
  };
  watch(".reveal", { threshold: .12 });
  watch(".rise", { rootMargin: "0px 0px -12% 0px" });
})();
