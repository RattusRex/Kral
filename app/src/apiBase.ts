export interface ApiBaseEnv {
  DEV?: boolean;
  PROD?: boolean;
  VITE_API_BASE_URL?: string;
  VITE_API_TARGET?: string;
}

const API_PREFIX = "/api";
const LOCAL_FASTAPI_TARGET = "http://127.0.0.1:8000";

function trimTrailingSlashes(value: string) {
  return value.replace(/\/+$/, "");
}

function normalizeExplicitBaseURL(value: string | undefined) {
  const trimmed = value?.trim();
  return trimmed ? trimTrailingSlashes(trimmed) : "";
}

function apiBaseFromTarget(value: string | undefined) {
  const target = normalizeExplicitBaseURL(value);
  if (!target) {
    return "";
  }

  return target.endsWith(API_PREFIX) ? target : `${target}${API_PREFIX}`;
}

function isLoopbackStaticOrigin(origin: string | undefined) {
  if (!origin) {
    return false;
  }

  try {
    const url = new URL(origin);
    const hostname = url.hostname;
    const isLoopback = hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1" || hostname === "[::1]";
    return isLoopback && url.port !== "" && url.port !== "8000";
  } catch {
    return false;
  }
}

export function resolveApiBaseURL(env: ApiBaseEnv = {}, origin?: string) {
  const explicitBaseURL = normalizeExplicitBaseURL(env.VITE_API_BASE_URL);
  if (explicitBaseURL) {
    return explicitBaseURL;
  }

  if (env.PROD && !env.DEV) {
    const targetBaseURL = apiBaseFromTarget(env.VITE_API_TARGET);
    if (targetBaseURL) {
      return targetBaseURL;
    }

    if (isLoopbackStaticOrigin(origin)) {
      return `${LOCAL_FASTAPI_TARGET}${API_PREFIX}`;
    }
  }

  return API_PREFIX;
}

const runtimeEnv = ((import.meta as ImportMeta & { env?: ApiBaseEnv }).env ?? {}) as ApiBaseEnv;
const runtimeOrigin = typeof window === "undefined" ? undefined : window.location.origin;

export const API_BASE_URL = resolveApiBaseURL(runtimeEnv, runtimeOrigin);
