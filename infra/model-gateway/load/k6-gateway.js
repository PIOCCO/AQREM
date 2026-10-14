import http from "k6/http";
import { check, sleep } from "k6";

const baseUrl = __ENV.GATEWAY_URL;
const apiKey = __ENV.GATEWAY_API_KEY;
const stream = (__ENV.K6_STREAM || "0") === "1";

export const options = {
  vus: Number(__ENV.K6_VUS || 50),
  duration: __ENV.K6_DURATION || "5m",
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<5000"],
  },
};

export default function () {
  if (!baseUrl || !apiKey) {
    throw new Error("Set GATEWAY_URL and GATEWAY_API_KEY");
  }
  const payload = JSON.stringify({
    messages: [{ role: "user", content: "Say hello in one word." }],
    stream,
    max_tokens: stream ? 32 : 16,
  });
  const res = http.post(`${baseUrl}/v1/chat-default/chat/completions`, payload, {
    headers: {
      "Content-Type": "application/json",
      "X-AQREM-Gateway-Key": apiKey,
    },
    timeout: "120s",
  });
  check(res, {
    "status 200 or 429": (r) => r.status === 200 || r.status === 429,
  });
  sleep(0.2);
}
