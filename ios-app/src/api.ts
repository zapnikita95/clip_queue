import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";

const DEFAULT_API = "https://clip-queue-web-production.up.railway.app";
const TOKEN_KEY = "kyro_session_token";

export function apiBase(): string {
  const extra = (Constants.expoConfig?.extra || {}) as { apiBaseUrl?: string };
  return (extra.apiBaseUrl || DEFAULT_API).replace(/\/$/, "");
}

export async function getToken(): Promise<string> {
  return (await AsyncStorage.getItem(TOKEN_KEY)) || "";
}

export async function setToken(token: string): Promise<void> {
  if (token) await AsyncStorage.setItem(TOKEN_KEY, token);
  else await AsyncStorage.removeItem(TOKEN_KEY);
}

export async function api<T = any>(
  path: string,
  opts: { method?: string; body?: any } = {},
): Promise<T> {
  const token = await getToken();
  const res = await fetch(`${apiBase()}${path}`, {
    method: opts.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: opts.body != null ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error((data && data.error) || `HTTP ${res.status}`);
  }
  return data as T;
}

export type VideoCard = {
  video_id: string;
  title?: string;
  channel_title?: string;
  thumb_url?: string;
  duration_label?: string;
  reason?: string;
  watch_url?: string;
};

export type ListCard = {
  id: number;
  title?: string;
  count?: number;
};
