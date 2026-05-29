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
  armor_class: number;
  level: number;
  xp: number;
  route: string;
  user_id?: number;
  is_dead?: boolean;
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
  items: InventoryItem[];
}

export interface ShopResult {
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
  inventory: Inventory;
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