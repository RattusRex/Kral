import axios from "axios";

export const TOKEN_KEY = "access_token";

export interface User {
  id: number;
  username: string;
  email: string;
  karma: number;
  is_admin?: boolean;
}

export interface Character {
  id: number;
  name: string;
  class_name: string;
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
  hp: number;
  temp_hp: number;
  armor_class: number;
  speed: number;
  level: number;
  xp: number;
  route: string;
  user_id?: number;
  owner_username?: string;
  owner_email?: string;
  is_dead?: boolean;
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

export interface ShopResult {
  quote_id: number | null;
  mode: "buy" | "sell";
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
  is_admin: boolean;
}

export interface ShopTransactionLog {
  id: number;
  created_at: string;
  user_id: number;
  username: string;
  character_id: number;
  character_name: string;
  mode: "buy" | "sell";
  item_name: string;
  rarity: string;
  item_price: number;
  hireling_cost: number;
  total_amount: number;
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

export const api = axios.create({
  baseURL: "/api"
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
