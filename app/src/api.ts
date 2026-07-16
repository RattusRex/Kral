import axios from "axios";
import { API_BASE_URL } from "./apiBase";

export const TOKEN_KEY = "access_token";
export const PROJECT_KEY = "active_project_id";
export const AUTH_NOTICE_KEY = "auth_notice";
export const SESSION_EXPIRED_MESSAGE = "Сессия истекла. Войдите снова.";

export type UserRole = "owner" | "project_owner" | "head_admin" | "admin" | "technician" | "player";

export const ROLE_LABELS: Record<UserRole, string> = {
  owner: "👑 Владелец",
  project_owner: "🏰 Владелец проекта",
  head_admin: "🛡 Главный Администратор",
  admin: "🎲 Мастер игры",
  technician: "🔧 Техник",
  player: "🎮 Игрок"
};

export interface ProjectFeatures {
  shop: boolean;
  market: boolean;
  karma_shop: boolean;
  recruitments: boolean;
  personal_hirelings: boolean;
  simulacrums: boolean;
  leaderboard: boolean;
  karma: boolean;
  karma_logs: boolean;
  character_transfers: boolean;
  market_logs: boolean;
  logs: boolean;
}

export interface ProjectContext {
  id: number;
  name: string;
  slug: string;
  is_default: boolean;
  is_selectable: boolean;
  role: UserRole | null;
  karma: number;
  features: ProjectFeatures;
  is_admin: boolean;
  can_manage_settings: boolean;
  can_manage_roles: boolean;
}

export interface User {
  id: number;
  username: string;
  email: string;
  karma: number;
  role?: UserRole;
  is_admin?: boolean;
  is_owner?: boolean;
  is_head_admin?: boolean;
  email_verified?: boolean;
  email_verified_at?: string | null;
}

export interface Project {
  id: number;
  name: string;
  created_at: string;
  owner_id: number;
  settings: Record<string, unknown>;
  role: "owner" | "admin" | "player" | null;
}

export interface ContentBlock {
  id: number;
  page_slug: "server-rules" | "approved-homebrew" | "illegal-items";
  title: string;
  content: string;
  content_type: string | null;
  karma_cost: number | null;
  is_banned: boolean;
  source_url: string | null;
  rarity: string | null;
  source: string | null;
  notes: string | null;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectAbout {
  posts: ProjectAboutPost[];
  creator_content: string;
}

export interface ProjectAboutPost {
  id: number;
  title: string;
  content: string;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface Character {
  id: number;
  project_id: number;
  name: string;
  class_name: string;
  class_levels: CharacterClassLevel[];
  subclass: string;
  race: string;
  background: string;
  strength: number;
  dexterity: number;
  constitution: number;
  intelligence: number;
  wisdom: number;
  charisma: number;
  investigation: number;
  skill_proficiencies: string[];
  skill_expertise: string[];
  saving_throw_proficiencies: string[];
  hp: number;
  temp_hp: number;
  armor_class: number;
  speed: number;
  level: number;
  xp: number;
  route: string;
  game_created_at?: string;
  total_days?: number;
  busy_days?: number;
  free_days?: number;
  personal_hireling_enabled?: boolean;
  personal_hireling_acquired_at?: string;
  personal_hireling_investigation?: number;
  personal_hireling_total_days?: number;
  personal_hireling_busy_days?: number;
  personal_hireling_free_days?: number;
  simulacrum_enabled?: boolean;
  simulacrum_created_at?: string;
  simulacrum_investigation?: number;
  simulacrum_total_days?: number;
  simulacrum_busy_days?: number;
  simulacrum_free_days?: number;
  user_id?: number;
  owner_username?: string;
  owner_email?: string;
  is_dead?: boolean;
}

export interface CharacterClassLevel {
  class_name: string;
  level: number;
}

export interface DowntimeEntry {
  id: number;
  character_id: number;
  start_date: string;
  end_date: string;
  days: number;
  reason: string;
  source: string;
  agent_type: string;
  tools?: string | null;
  proficiency_modifier?: number | null;
  income_copper?: number | null;
}

export interface CalendarSummary {
  game_epoch: string;
  created_at: string;
  current_date: string;
  total_days: number;
  busy_days: number;
  free_days: number;
  can_manage: boolean;
  page: number;
  page_size: number;
  total_entries: number;
  pages: number;
  entries: DowntimeEntry[];
}

export interface TransferTarget {
  id: number;
  name: string;
  class_name: string;
  level: number;
  owner_username: string;
}

export interface InventoryItem {
  id: number;
  name: string;
  rarity: string;
  is_consumable: boolean;
}

export interface Inventory {
  id: number;
  character_id: number;
  gold: number;
  silver: number;
  copper: number;
  notes: string;
  items: InventoryItem[];
}

export interface CharacterAttack {
  id: number;
  character_id: number;
  name: string;
  attack_bonus: number;
  damage: string;
}

export interface AttackRoll {
  attack_id: number;
  name: string;
  roll: number;
  bonus: number;
  total: number;
  damage: string;
}

export interface DamageRoll {
  attack_id: number;
  name: string;
  formula: string;
  rolls: number[];
  modifier: number;
  total: number;
}

export interface AbilityRoll {
  ability: string;
  score: number;
  modifier: number;
  roll: number;
  total: number;
}

export interface SavingThrowRoll {
  ability: string;
  bonus: number;
  roll: number;
  total: number;
}

export interface SkillRoll {
  skill: string;
  ability: string;
  modifier: number;
  roll: number;
  total: number;
}

export interface ChatMessage {
  id: number;
  created_at: string;
  user_id: number;
  username: string;
  channel: "general" | "rolls";
  content: string;
  formula: string | null;
  rolls: number[] | null;
  total: number | null;
}

export interface LeaderboardEntry {
  rank: number;
  id: number;
  username: string;
  karma: number;
}

export interface GameApplication {
  id: number;
  user_id: number;
  username: string;
  character_id: number;
  character_name: string;
  class_name: string;
  level: number;
  created_at: string;
  status: "applied" | "selected";
}

export interface RecruitmentMessage {
  id: number;
  created_at: string;
  user_id: number | null;
  username: string | null;
  is_system: boolean;
  content: string;
}

export interface ProjectAuditLog {
  id: number;
  created_at: string;
  admin_id: number;
  admin_username: string;
  project_id: number;
  project_name: string;
  action: string;
}

export interface GameRecruitment {
  id: number;
  author_id: number;
  author_username: string;
  created_at: string;
  real_date: string;
  game_date: string;
  start_time: string;
  duration: string;
  location: string;
  quest: string;
  notes: string;
  status: "upcoming" | "completed";
  can_manage: boolean;
  application_status: "not_applied" | "applied" | "selected";
  applications: GameApplication[];
  messages: RecruitmentMessage[];
}

export interface ShopResult {
  quote_id: number | null;
  mode: "buy" | "sell";
  searcher_type: "character" | "paid_hireling" | "personal_hireling" | "simulacrum";
  searcher_label: string;
  item_name: string;
  rarity: string;
  is_consumable: boolean;
  success: boolean;
  search_roll: number;
  modifier: number;
  total_roll: number;
  dc: number;
  days: number;
  hireling_cost: number;
  price_roll: number | null;
  multiplier: number | null;
  item_price: number | null;
  total_cost: number | null;
  is_consumed: boolean;
  inventory: Inventory;
}

export interface MagicItem {
  id: string;
  name: string;
  rarity: string;
  rarity_key: "common" | "uncommon" | "rare";
  item_type: string;
  source: string | null;
  page: number | null;
  tier: string | null;
  is_consumable: boolean;
  reference_sources: string[];
  requires: Record<string, unknown>[];
  entries: string[];
}

export interface AdminUser extends User {
  character_count: number;
  role: UserRole;
  is_admin: boolean;
  is_owner: boolean;
  is_head_admin: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface ShopTransactionLog {
  id: number;
  created_at: string;
  user_id: number;
  username: string;
  actor_id?: number | null;
  actor_username?: string | null;
  character_id: number;
  character_name: string;
  mode: "buy" | "sell" | "work";
  item_name: string;
  rarity: string;
  item_price: number;
  hireling_cost: number;
  total_amount: number;
  total_copper?: number | null;
}

export interface MarketSaleLog {
  id: number;
  created_at: string;
  user_id: number;
  username: string;
  actor_id?: number | null;
  actor_username?: string | null;
  character_id: number;
  character_name: string;
  item_name: string;
  gold: number;
}

export interface MarketSaleResult {
  sale: MarketSaleLog;
  inventory: Inventory;
}

export interface TransferLog {
  id: number;
  created_at: string;
  user_id: number;
  username: string;
  sender_character_id: number;
  sender_character_name: string;
  recipient_character_id: number;
  recipient_character_name: string;
  transfer_type: "currency" | "item";
  gold: number;
  silver: number;
  copper: number;
  item_name: string | null;
  item_rarity: string | null;
  item_is_consumable: boolean | null;
}

export interface AdminGrantLog {
  id: number;
  created_at: string;
  admin_id: number;
  admin_username: string;
  user_id: number;
  username: string;
  character_id: number | null;
  character_name: string | null;
  operation_type: "karma" | "xp" | "gold" | "item";
  value: string;
  reason: string;
}

export interface KarmaPurchase {
  id: number;
  created_at: string;
  user_id: number;
  username: string;
  actor_id?: number | null;
  actor_username?: string | null;
  character_id: number | null;
  character_name: string | null;
  character_level: number | null;
  purchase_type: "xp" | "item" | "opener" | "resurrection";
  name: string;
  cost: number;
}

export interface KarmaPurchaseResult {
  purchase: KarmaPurchase;
  remaining_karma: number;
  character_level: number | null;
  character_xp: number | null;
  character_is_dead: boolean | null;
}

export interface KarmaOpener {
  name: string;
  cost: number;
  note: string | null;
}

export interface RealtimeEvent {
  type: string;
  project_id?: number;
  user_id?: number;
  entity_id?: number;
  created_at?: string;
}

export function realtimeWebSocketURL(token: string, projectId: string) {
  const apiURL = new URL(API_BASE_URL, window.location.origin);
  apiURL.protocol = apiURL.protocol === "https:" ? "wss:" : "ws:";
  apiURL.pathname = `${apiURL.pathname.replace(/\/$/, "")}/ws`;
  apiURL.search = new URLSearchParams({ token, project_id: projectId }).toString();
  return apiURL.toString();
}

export function connectRealtime(onEvent: (event: RealtimeEvent) => void) {
  let socket: WebSocket | null = null;
  let reconnectTimer: number | undefined;
  let heartbeatTimer: number | undefined;
  let stopped = false;
  let attempt = 0;

  function connect() {
    const token = localStorage.getItem(TOKEN_KEY);
    const projectId = localStorage.getItem(PROJECT_KEY);
    if (stopped || !token || !projectId) return;
    socket = new WebSocket(realtimeWebSocketURL(token, projectId));
    socket.onopen = () => {
      attempt = 0;
      heartbeatTimer = window.setInterval(() => {
        if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "ping" }));
      }, 25_000);
    };
    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as RealtimeEvent;
        if (event.type !== "pong" && event.type !== "connection.ready") onEvent(event);
      } catch {
        // Ignore malformed frames; a later valid invalidation can still refresh the page.
      }
    };
    socket.onclose = () => {
      if (heartbeatTimer) window.clearInterval(heartbeatTimer);
      if (!stopped) {
        attempt += 1;
        reconnectTimer = window.setTimeout(connect, Math.min(30_000, 1_000 * (2 ** attempt)));
      }
    };
  }

  function handleStorage(event: StorageEvent) {
    if (event.key === TOKEN_KEY || event.key === PROJECT_KEY) {
      if (!event.newValue && event.key === TOKEN_KEY) stopped = true;
      socket?.close();
      if (!stopped && (!socket || socket.readyState === WebSocket.CLOSED)) connect();
    }
  }

  window.addEventListener("storage", handleStorage);
  connect();
  return () => {
    stopped = true;
    if (reconnectTimer) window.clearTimeout(reconnectTimer);
    if (heartbeatTimer) window.clearInterval(heartbeatTimer);
    window.removeEventListener("storage", handleStorage);
    socket?.close();
  };
}

export const api = axios.create({
  baseURL: API_BASE_URL
});

function isHtmlResponse(data: unknown) {
  return typeof data === "string" && /^\s*(?:<!doctype html|<html[\s>])/i.test(data);
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  const projectId = localStorage.getItem(PROJECT_KEY);
  if (projectId) config.headers["X-Project-ID"] = projectId;
  return config;
});

api.interceptors.response.use(
  (response) => {
    if (isHtmlResponse(response.data)) {
      return Promise.reject(new Error(
        `API request ${response.config.url ?? ""} returned HTML. Check VITE_API_TARGET or your /api reverse proxy.`
      ));
    }
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      if (error.response?.data?.detail?.code === "token_expired") {
        sessionStorage.setItem(AUTH_NOTICE_KEY, SESSION_EXPIRED_MESSAGE);
      }
      localStorage.removeItem(TOKEN_KEY);
      window.dispatchEvent(new Event("auth:logout"));
    }
    return Promise.reject(error);
  }
);
