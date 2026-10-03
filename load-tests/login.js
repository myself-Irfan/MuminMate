// Login load test; see the README. LOAD_*, not K6_*: k6 reads K6_* as its own options.
import http from "k6/http";
import { check } from "k6";

const CONFIG = {
  loginPath: "/accounts/login/",
  duration: "30s",
  timeUnit: "1s",
  rate: { throttled: 20, valid: 2 },
  preAllocatedVUs: 5,
  maxVUs: 40,
  maxErrorRate: 0.01,
  // Measured 2026-10-03 (M-series): throttled 14 ms, valid 113 ms; 40 ms is below any hash.
  p95: { throttled: 40, valid: 500 },
};

const BASE_URL = requiredEnv("LOAD_BASE_URL");
const EMAIL = requiredEnv("LOAD_EMAIL");
const PASSWORD = requiredEnv("LOAD_PASSWORD");

function requiredEnv(name) {
  const value = __ENV[name];
  if (!value) throw new Error(`Missing required k6 variable: ${name}`);
  return value;
}

// Sequential: sync views share one thread, so refusals would queue behind hashes.
function scenario(name, startTime) {
  return {
    executor: "constant-arrival-rate",
    exec: name,
    rate: CONFIG.rate[name],
    timeUnit: CONFIG.timeUnit,
    duration: CONFIG.duration,
    startTime,
    preAllocatedVUs: CONFIG.preAllocatedVUs,
    maxVUs: CONFIG.maxVUs,
  };
}

export const options = {
  scenarios: {
    throttled: scenario("throttled", "0s"),
    valid: scenario("valid", CONFIG.duration),
  },
  thresholds: {
    http_req_failed: [`rate<${CONFIG.maxErrorRate}`],
    "http_req_duration{endpoint:post_throttled}": [`p(95)<${CONFIG.p95.throttled}`],
    "http_req_duration{endpoint:post_valid}": [`p(95)<${CONFIG.p95.valid}`],
  },
};

// A fresh unknown email per run, so reruns start unthrottled.
export function setup() {
  return { throttledEmail: `k6-throttled-${Date.now()}@example.com` };
}

function postLogin(email, password, endpoint) {
  http.cookieJar().clear(BASE_URL);
  const page = http.get(`${BASE_URL}${CONFIG.loginPath}`, { tags: { endpoint: "get_login" } });
  const token = page.html().find("input[name=csrfmiddlewaretoken]").attr("value");
  return http.post(
    `${BASE_URL}${CONFIG.loginPath}`,
    { username: email, password, csrfmiddlewaretoken: token },
    { redirects: 0, tags: { endpoint } },
  );
}

export function throttled(data) {
  const res = postLogin(data.throttledEmail, PASSWORD, "post_throttled");
  check(res, { "throttled login re-renders the form": (r) => r.status === 200 });
}

export function valid() {
  const res = postLogin(EMAIL, PASSWORD, "post_valid");
  check(res, { "valid login redirects": (r) => r.status === 302 });
}
