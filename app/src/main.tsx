import { FormEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Link, Navigate, Route, BrowserRouter as Router, Routes, useNavigate, useParams } from "react-router-dom";
import { Check, LogOut, Plus, RefreshCw, Search, Shield, ShoppingBag, UserRound, UsersRound } from "lucide-react";
import { AdminUser, api, Character, Inventory, InventoryItem, ShopResult, TOKEN_KEY, User } from "./api";
import "./styles.css";

const rarities = ["Обычный", "Необычный", "Редкий"];
const hirelings = [
  { level: "Плохой", bonus: 0, cost: 1 },
  { level: "Хороший", bonus: 4, cost: 5 },
  { level: "Компетентный", bonus: 6, cost: 10 },
  { level: "Эксперт", bonus: 8, cost: 25 }
];
const textFields = [
  { field: "name", label: "Имя" },
  { field: "class_name", label: "Класс" },
  { field: "subclass", label: "Подкласс" },
  { field: "race", label: "Раса" },
  { field: "background", label: "Предыстория" },
  { field: "route", label: "Путь" }
] as const;
const numberFields = [
  { field: "level", label: "Уровень" },
  { field: "hp", label: "HP" },
  { field: "armor_class", label: "КД (Armor Class)" },
  { field: "strength", label: "Сила (STR)" },
  { field: "dexterity", label: "Ловкость (DEX)" },
  { field: "constitution", label: "Телосложение (CON)" },
  { field: "intelligence", label: "Интеллект (INT)" },
  { field: "wisdom", label: "Мудрость (WIS)" },
  { field: "charisma", label: "Харизма (CHA)" },
  { field: "investigation", label: "Внимательность / Investigation" }
] as const;
const blankCharacter = {
  name: "",
  class_name: "",
  subclass: "",
  race: "",
  background: "",
  route: "",
  level: 1,
  hp: 1,
  armor_class: 10,
  strength: 10,
  dexterity: 10,
  constitution: 10,
  intelligence: 10,
  wisdom: 10,
  charisma: 10,
  investigation: 0
};

function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem(TOKEN_KEY)) {
      setLoading(false);
      return;
    }
    api.get<User>("/me")
      .then((response) => setUser(response.data))
      .finally(() => setLoading(false));
  }, []);

  return { user, loading, setUser };
}

function Shell({ children, user }: { children: React.ReactNode; user: User | null }) {
  const navigate = useNavigate();

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-[#101217] text-parchment">
      <header className="sticky top-0 z-10 border-b border-white/10 bg-[#101217]/95 backdrop-blur">
        <nav className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <Link to="/characters" className="text-lg font-bold text-ember">Epoha Truda</Link>
          <div className="flex flex-wrap items-center gap-2">
            <Link className="btn-secondary" to="/"><UsersRound size={16} />Меню</Link>
            <Link className="btn-secondary" to="/characters"><UsersRound size={16} />Персонажи</Link>
            <Link className="btn-secondary" to="/shop"><ShoppingBag size={16} />Магазин</Link>
            <Link className="btn-secondary" to="/profile"><UserRound size={16} />Профиль</Link>
            {user?.is_admin && <Link className="btn-secondary" to="/admin"><Shield size={16} />Админ</Link>}
            <button className="btn-secondary" onClick={logout}><LogOut size={16} />Выйти</button>
          </div>
        </nav>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}

function HomePage() {
  const { user, loading } = useAuth();
  if (loading || !user) return <p>Загрузка...</p>;
  return (
    <div className="grid gap-4 md:grid-cols-[1fr_320px]">
      <section className="panel p-5">
        <h1 className="text-2xl font-bold text-ember">Главное меню</h1>
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <Link className="btn" to="/shop"><ShoppingBag size={18} />Shop</Link>
          <Link className="btn" to="/characters"><UsersRound size={18} />My Characters</Link>
          <Link className="btn" to="/characters/new"><Plus size={18} />Create Character</Link>
        </div>
      </section>
      <aside className="panel p-5">
        <h2 className="text-lg font-semibold text-ember">{user.username}</h2>
        <p className="mt-2 text-white/70">{user.email}</p>
        <p className="mt-4 text-xl font-semibold">Карма: {user.karma}</p>
      </aside>
    </div>
  );
}

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-6 text-parchment">Загрузка...</div>;
  if (!localStorage.getItem(TOKEN_KEY)) return <Navigate to="/login" replace />;
  return <Shell user={user}>{children}</Shell>;
}

function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    const body = new URLSearchParams({ username: email, password });
    try {
      const response = await api.post("/login", body);
      localStorage.setItem(TOKEN_KEY, response.data.access_token);
      navigate("/characters");
    } catch {
      setError("Не удалось войти");
    }
  }

  return <AuthPanel title="Вход" error={error} onSubmit={submit}>
    <input className="field" placeholder="email" value={email} onChange={(event) => setEmail(event.target.value)} />
    <input className="field" placeholder="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
    <button className="btn" type="submit">Войти</button>
    <Link className="btn-secondary" to="/register">Перейти к регистрации</Link>
  </AuthPanel>;
}

function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api.post("/users", form);
      navigate("/login");
    } catch {
      setError("Не удалось создать аккаунт");
    }
  }

  return <AuthPanel title="Регистрация" error={error} onSubmit={submit}>
    <input className="field" placeholder="username" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} />
    <input className="field" placeholder="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
    <input className="field" placeholder="password" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
    <button className="btn" type="submit">Создать аккаунт</button>
    <Link className="btn-secondary" to="/login">Войти</Link>
  </AuthPanel>;
}

function AuthPanel({ title, error, onSubmit, children }: { title: string; error: string; onSubmit: (event: FormEvent) => void; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen place-items-center bg-[#101217] px-4 text-parchment">
      <form className="panel flex w-full max-w-sm flex-col gap-3 p-6" onSubmit={onSubmit}>
        <h1 className="text-2xl font-bold text-ember">{title}</h1>
        {children}
        {error && <p className="text-sm text-red-300">{error}</p>}
      </form>
    </div>
  );
}

function CharactersPage() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [inventories, setInventories] = useState<Record<number, Inventory>>({});

  useEffect(() => {
    api.get<Character[]>("/characters").then(async (response) => {
      setCharacters(response.data);
      const pairs = await Promise.all(response.data.map(async (character) => {
        const inventory = await api.get<Inventory>(`/characters/${character.id}/inventory`);
        return [character.id, inventory.data] as const;
      }));
      setInventories(Object.fromEntries(pairs));
    });
  }, []);

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Link className="btn" to="/characters/new"><Plus size={16} />Создать персонажа</Link>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {characters.map((character) => (
        <article className="panel p-4" key={character.id}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-ember">{character.name}</h2>
              <p className="text-sm text-white/70">{character.race} {character.class_name} {character.subclass}</p>
            </div>
            <span className="rounded bg-white/10 px-2 py-1 text-sm">Ур. {character.level}</span>
          </div>
          <dl className="mt-4 grid grid-cols-3 gap-2 text-sm">
            <Stat label="XP" value={character.xp} />
            <Stat label="HP" value={character.hp} />
            <Stat label="КД" value={character.armor_class} />
            <Stat label="Золото" value={inventories[character.id]?.gold ?? 0} />
            <Stat label="Серебро" value={inventories[character.id]?.silver ?? 0} />
            <Stat label="Медь" value={inventories[character.id]?.copper ?? 0} />
          </dl>
          <p className="mt-3 text-sm text-white/60">{character.background || "Без предыстории"}</p>
          <div className="mt-4 flex gap-2">
            <Link className="btn" to={`/characters/${character.id}`}>Открыть персонажа</Link>
            <Link className="btn-secondary" to={`/characters/${character.id}/edit`}>Редактировать</Link>
            <Link className="btn-secondary" to={`/shop?character=${character.id}`}>Магазин</Link>
          </div>
        </article>
        ))}
      </div>
    </div>
  );
}

function CharacterPage() {
  const { id: idParam } = useParams();
  const id = Number(idParam);
  const [character, setCharacter] = useState<Character | null>(null);
  const [inventory, setInventory] = useState<Inventory | null>(null);

  useEffect(() => {
    api.get<Character[]>("/characters").then((response) => {
      setCharacter(response.data.find((item) => item.id === id) ?? null);
    });
    api.get<Inventory>(`/characters/${id}/inventory`).then((response) => setInventory(response.data));
  }, [id]);

  if (!character) return <p>Загрузка...</p>;
  const stats = numberFields.filter((item) => !["level", "hp", "armor_class"].includes(item.field));

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <section className="panel p-5">
        <h1 className="text-2xl font-bold text-ember">{character.name}</h1>
        <p className="text-white/70">{character.class_name} / {character.subclass} / {character.race}</p>
        <dl className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Уровень" value={character.level} />
          <Stat label="XP" value={character.xp} />
          <Stat label="HP" value={character.hp} />
          <Stat label="КД" value={character.armor_class} />
          {stats.map((stat) => <Stat key={stat.field} label={stat.label} value={character[stat.field]} />)}
        </dl>
      </section>
      <InventoryPanel inventory={inventory} onChange={setInventory} characterId={id} />
    </div>
  );
}

function CharacterFormPage({ edit = false }: { edit?: boolean }) {
  const navigate = useNavigate();
  const { id: idParam } = useParams();
  const id = Number(idParam);
  const [form, setForm] = useState(blankCharacter);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!edit) return;
    api.get<Character[]>("/characters").then((response) => {
      const character = response.data.find((item) => item.id === id);
      if (character) setForm({ ...blankCharacter, ...character });
    });
  }, [edit, id]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      if (edit) {
        await api.patch(`/characters/${id}`, form);
        navigate(`/characters/${id}`);
      } else {
        await api.post("/characters", form);
        navigate("/characters");
      }
    } catch {
      setError("Не удалось сохранить персонажа");
    }
  }

  return (
    <form className="panel grid gap-3 p-5 md:grid-cols-2" onSubmit={submit}>
      <h1 className="text-xl font-bold text-ember md:col-span-2">{edit ? "Редактировать персонажа" : "Создать персонажа"}</h1>
      {textFields.map(({ field, label }) => (
        <label className="field-label" key={field}>
          <span>{label}</span>
          <input className="field" value={form[field]} onChange={(event) => setForm({ ...form, [field]: event.target.value })} />
        </label>
      ))}
      {numberFields.map(({ field, label }) => (
        <label className="field-label" key={field}>
          <span>{label}</span>
          <input className="field" type="number" value={form[field]} onChange={(event) => setForm({ ...form, [field]: Number(event.target.value) })} />
        </label>
      ))}
      {error && <p className="text-sm text-red-300 md:col-span-2">{error}</p>}
      <button className="btn md:col-span-2" type="submit">Сохранить</button>
    </form>
  );
}

function InventoryPanel({ inventory, onChange, characterId }: { inventory: Inventory | null; onChange: (inventory: Inventory) => void; characterId: number }) {
  async function remove(item: InventoryItem) {
    const response = await api.delete<Inventory>(`/characters/${characterId}/inventory/items/${item.id}`);
    onChange(response.data);
  }

  return (
    <aside className="panel p-5">
      <h2 className="text-lg font-semibold text-ember">Инвентарь</h2>
      <p className="mt-1 text-sm text-white/70">{inventory?.gold ?? 0} зол. / {inventory?.silver ?? 0} сер. / {inventory?.copper ?? 0} мед.</p>
      <div className="mt-4 space-y-3">
        {inventory?.items.map((item) => (
          <div className="rounded-md border border-white/10 p-3" key={item.id}>
            <div className="font-semibold">{item.name}</div>
            <div className="text-sm text-white/60">{item.rarity} · {item.is_consumable ? "расходуемый" : "постоянный"}</div>
            <div className="mt-3 flex gap-2">
              <Link className="btn-secondary" to={`/shop?mode=sell&character=${characterId}&item=${item.id}`}>Продать</Link>
              <button className="btn-secondary" onClick={() => remove(item)}>Удалить</button>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}

function ShopPage() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [characterId, setCharacterId] = useState("");
  const [mode, setMode] = useState<"buy" | "sell">(() => new URLSearchParams(window.location.search).get("mode") === "sell" ? "sell" : "buy");
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [form, setForm] = useState({ item_name: "", rarity: "Обычный", is_consumable: false, item_id: "", searcher_type: "hireling", hireling_level: "Плохой" });
  const [result, setResult] = useState<ShopResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<Character[]>("/characters").then((response) => {
      setCharacters(response.data);
      const selected = new URLSearchParams(window.location.search).get("character");
      setCharacterId(selected ?? String(response.data[0]?.id ?? ""));
    });
  }, []);

  useEffect(() => {
    if (!characterId) return;
    api.get<Inventory>(`/characters/${characterId}/inventory`).then((response) => {
      setInventory(response.data);
      const selectedItem = new URLSearchParams(window.location.search).get("item");
      const fallbackItem = response.data.items[0]?.id;
      setForm((current) => ({
        ...current,
        item_id: selectedItem ?? (fallbackItem ? String(fallbackItem) : "")
      }));
    });
  }, [characterId]);

  async function performSearch() {
    setError("");
    try {
      const payload = mode === "buy"
        ? {
            mode,
            item_name: form.item_name,
            rarity: form.rarity,
            is_consumable: form.is_consumable,
            searcher_type: form.searcher_type,
            hireling_level: form.hireling_level
          }
        : {
            mode,
            item_id: Number(form.item_id),
            searcher_type: form.searcher_type,
            hireling_level: form.hireling_level
          };
      const response = await api.post<ShopResult>(`/characters/${characterId}/shop/search`, payload);
      setResult(response.data);
      setInventory(response.data.inventory);
    } catch {
      setError("Поиск не выполнен");
    }
  }

  async function searchShop(event: FormEvent) {
    event.preventDefault();
    await performSearch();
  }

  async function confirmResult() {
    if (!result?.quote_id) return;
    setError("");
    try {
      const endpoint = result.mode === "buy" ? "buy" : "sell";
      const response = await api.post<ShopResult>(`/characters/${characterId}/shop/${endpoint}`, { quote_id: result.quote_id });
      setResult(response.data);
      setInventory(response.data.inventory);
      if (response.data.mode === "sell") {
        setForm((current) => ({
          ...current,
          item_id: String(response.data.inventory.items[0]?.id ?? "")
        }));
      }
    } catch {
      setError("Не удалось подтвердить сделку");
    }
  }

  function switchMode(nextMode: "buy" | "sell") {
    setMode(nextMode);
    setResult(null);
    setError("");
    if (nextMode === "sell") {
      setForm((current) => ({
        ...current,
        item_id: current.item_id || String(inventory?.items[0]?.id ?? "")
      }));
    }
  }

  const selectedCharacter = characters.find((character) => String(character.id) === characterId);
  const selectedItem = inventory?.items.find((item) => String(item.id) === form.item_id);
  const canSearch = Boolean(characterId) && (mode === "buy" ? form.item_name.trim().length > 0 : Boolean(form.item_id));

  return (
    <div className="grid gap-4 lg:grid-cols-[420px_1fr]">
      <form className="panel flex flex-col gap-4 p-5" onSubmit={searchShop}>
        <h1 className="text-xl font-bold text-ember">Магазин</h1>
        <div className="grid grid-cols-2 gap-2">
          <button type="button" className={mode === "buy" ? "mode-tab-active" : "mode-tab"} onClick={() => switchMode("buy")}>Купить</button>
          <button type="button" className={mode === "sell" ? "mode-tab-active" : "mode-tab"} onClick={() => switchMode("sell")}>Продать</button>
        </div>
        <select className="field" value={characterId} onChange={(event) => setCharacterId(event.target.value)}>
          {characters.map((character) => <option key={character.id} value={character.id}>{character.name}</option>)}
        </select>
        <p className="text-sm text-white/70">{selectedCharacter?.name ?? "Персонаж"}: {inventory?.gold ?? 0} зм / {inventory?.silver ?? 0} см / {inventory?.copper ?? 0} мм</p>
        {mode === "buy" ? (
          <>
            <label className="field-label">
              <span>Название предмета</span>
              <input className="field" value={form.item_name} onChange={(event) => setForm({ ...form, item_name: event.target.value })} />
            </label>
            <label className="field-label">
              <span>Редкость</span>
              <select className="field" value={form.rarity} onChange={(event) => setForm({ ...form, rarity: event.target.value })}>{rarities.map((rarity) => <option key={rarity}>{rarity}</option>)}</select>
            </label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_consumable} onChange={(event) => setForm({ ...form, is_consumable: event.target.checked })} />Расходуемый</label>
          </>
        ) : (
          <label className="field-label">
            <span>Предмет из инвентаря</span>
            <select className="field" value={form.item_id} onChange={(event) => setForm({ ...form, item_id: event.target.value })}>
              {inventory?.items.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.rarity}</option>)}
            </select>
          </label>
        )}
        <div className="grid grid-cols-2 gap-2">
          <button type="button" className={form.searcher_type === "character" ? "mode-tab-active" : "mode-tab"} onClick={() => setForm({ ...form, searcher_type: "character" })}>Персонаж</button>
          <button type="button" className={form.searcher_type === "hireling" ? "mode-tab-active" : "mode-tab"} onClick={() => setForm({ ...form, searcher_type: "hireling" })}>Наёмник</button>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {hirelings.map((hireling) => (
            <button
              className={form.hireling_level === hireling.level ? "hireling-option-active" : "hireling-option"}
              disabled={form.searcher_type !== "hireling"}
              key={hireling.level}
              onClick={() => setForm({ ...form, hireling_level: hireling.level })}
              type="button"
            >
              <span className="font-semibold">{hireling.level}</span>
              <span>Бонус: +{hireling.bonus}</span>
              <span>Стоимость: {hireling.cost} зм/день</span>
            </button>
          ))}
        </div>
        {mode === "sell" && !selectedItem && <p className="text-sm text-red-300">У персонажа нет предметов для продажи.</p>}
        {error && <p className="text-sm text-red-300">{error}</p>}
        <button className="btn" disabled={!canSearch}><Search size={16} />{mode === "buy" ? "Найти продавца" : "Найти покупателя"}</button>
      </form>
      <ResultPanel result={result} onConfirm={confirmResult} onContinue={performSearch} />
    </div>
  );
}

function ResultPanel({ result, onConfirm, onContinue }: { result: ShopResult | null; onConfirm: () => void; onContinue: () => void }) {
  if (!result) return <section className="panel p-5 text-white/60">Результат поиска появится здесь.</section>;
  const action = result.mode === "buy" ? "Купить предмет" : "Продать предмет";
  return (
    <section className="panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ember">{result.success ? "Сделка найдена" : "Сделка не найдена"}</h2>
          <p className="text-sm text-white/65">{result.item_name} · {result.rarity} · {result.mode === "buy" ? "покупка" : "продажа"}</p>
        </div>
        {result.is_consumed && <span className="rounded-md border border-emerald-400/40 px-2 py-1 text-sm text-emerald-200">Сделка завершена</span>}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Бросок" value={result.search_roll} />
        <Stat label="Модификатор" value={result.modifier >= 0 ? `+${result.modifier}` : result.modifier} />
        <Stat label="Итог" value={result.total_roll} />
        <Stat label="DC" value={result.dc} />
        <Stat label="Дни" value={result.days} />
        <Stat label="Бросок цены" value={result.price_roll ?? "-"} />
        <Stat label="Множитель" value={result.multiplier ? `x${result.multiplier.toFixed(2)}` : "-"} />
        <Stat label="Цена, зм" value={result.item_price ?? "-"} />
        <Stat label="Наёмник, зм" value={result.hireling_cost} />
        <Stat label="Итого, зм" value={result.total_cost ?? "-"} />
      </dl>
      <div className="mt-5 flex flex-wrap gap-2">
        {result.success && !result.is_consumed && <button className="btn" onClick={onConfirm}><Check size={16} />{action}</button>}
        {!result.is_consumed && <button className="btn-secondary" onClick={onContinue}><RefreshCw size={16} />Продолжить поиск</button>}
      </div>
    </section>
  );
}

function ProfilePage() {
  const { user, loading } = useAuth();
  if (loading || !user) return <p>Загрузка...</p>;
  return <section className="panel max-w-xl p-5"><h1 className="text-xl font-bold text-ember">{user.username}</h1><p>{user.email}</p><p className="mt-2">Карма: {user.karma}</p></section>;
}

function AdminPage() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [selected, setSelected] = useState("");
  const [amount, setAmount] = useState(1);
  const [karmaUserId, setKarmaUserId] = useState("");
  const [karmaAmount, setKarmaAmount] = useState(1);
  const [item, setItem] = useState({ name: "", rarity: "Обычный", is_consumable: false });

  const selectedCharacter = useMemo(() => characters.find((character) => String(character.id) === selected), [characters, selected]);
  const selectedUser = useMemo(() => users.find((user) => String(user.id) === karmaUserId), [users, karmaUserId]);

  function load() {
    Promise.all([
      api.get<Character[]>("/admin/characters"),
      api.get<AdminUser[]>("/admin/users")
    ]).then(([characterResponse, userResponse]) => {
      setCharacters(characterResponse.data);
      setSelected((current) => characterResponse.data.some((character) => String(character.id) === current) ? current : String(characterResponse.data[0]?.id ?? ""));
      setUsers(userResponse.data);
      setKarmaUserId((current) => userResponse.data.some((user) => String(user.id) === current) ? current : String(userResponse.data[0]?.id ?? ""));
    });
  }

  useEffect(load, []);

  async function action(path: string, body?: unknown) {
    await api.post(`/admin/characters/${selected}/${path}`, body ?? {});
    load();
  }

  async function karmaAction(path: "add" | "subtract") {
    await api.post(`/admin/users/${karmaUserId}/karma/${path}`, { amount: karmaAmount });
    load();
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
      <div className="space-y-4">
        <section className="panel flex flex-col gap-3 p-5">
          <h1 className="text-xl font-bold text-ember">Админка мастера</h1>
          <label className="field-label">
            <span>Персонаж</span>
            <select className="field" value={selected} onChange={(event) => setSelected(event.target.value)}>
              {characters.map((character) => <option value={character.id} key={character.id}>{character.name} · {character.owner_username}</option>)}
            </select>
          </label>
          <label className="field-label">
            <span>Количество</span>
            <input className="field" type="number" value={amount} onChange={(event) => setAmount(Number(event.target.value))} />
            <span className="text-xs text-white/45">Отрицательное значение уменьшает ресурс (не ниже нуля).</span>
          </label>
          <button className="btn" onClick={() => action("xp", { amount })}>Выдать XP</button>
          <button className="btn" onClick={() => action("gold", { amount })}>Выдать золото</button>
          <button className="btn-secondary" onClick={() => action("revive")}>Воскресить персонажа</button>
          <div className="mt-2 border-t border-white/10 pt-3">
            <h2 className="text-lg font-semibold text-ember">{selectedCharacter?.name ?? "Персонаж"}</h2>
            <div className="mt-3 flex flex-col gap-3">
              <input className="field" placeholder="название" value={item.name} onChange={(event) => setItem({ ...item, name: event.target.value })} />
              <select className="field" value={item.rarity} onChange={(event) => setItem({ ...item, rarity: event.target.value })}>{rarities.map((rarity) => <option key={rarity}>{rarity}</option>)}</select>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={item.is_consumable} onChange={(event) => setItem({ ...item, is_consumable: event.target.checked })} />Расходуемый</label>
              <button className="btn" onClick={() => action("item", item)}>Выдать предмет</button>
            </div>
          </div>
        </section>
        <section className="panel flex flex-col gap-3 p-5">
          <h2 className="text-lg font-semibold text-ember">Карма игроков</h2>
          <label className="field-label">
            <span>Игрок</span>
            <select className="field" value={karmaUserId} onChange={(event) => setKarmaUserId(event.target.value)}>
              {users.map((user) => <option value={user.id} key={user.id}>{user.username} · {user.karma} кармы</option>)}
            </select>
          </label>
          <label className="field-label">
            <span>Карма</span>
            <input className="field" type="number" value={karmaAmount} onChange={(event) => setKarmaAmount(Number(event.target.value))} />
            <span className="text-xs text-white/45">«Выдать» с отрицательным значением уменьшает карму (не ниже нуля).</span>
          </label>
          <p className="text-sm text-white/65">{selectedUser?.username ?? "Игрок"}: {selectedUser?.karma ?? 0}</p>
          <div className="grid grid-cols-2 gap-2">
            <button className="btn" onClick={() => karmaAction("add")}>Выдать</button>
            <button className="btn-secondary" onClick={() => karmaAction("subtract")}>Списать</button>
          </div>
        </section>
      </div>
      <section className="panel p-5">
        <h2 className="text-lg font-semibold text-ember">Все персонажи</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-xs uppercase text-white/45">
              <tr>
                <th className="py-2 pr-3">Имя</th>
                <th className="py-2 pr-3">Владелец</th>
                <th className="py-2 pr-3">Уровень</th>
                <th className="py-2 pr-3">Раса</th>
                <th className="py-2 pr-3">Подкласс</th>
                <th className="py-2 pr-3">Путь</th>
                <th className="py-2 pr-3"></th>
              </tr>
            </thead>
            <tbody>
              {characters.map((character) => (
                <tr className="border-t border-white/10" key={character.id}>
                  <td className="py-3 pr-3 font-semibold text-ember">{character.name}</td>
                  <td className="py-3 pr-3">{character.owner_username}</td>
                  <td className="py-3 pr-3">{character.level}</td>
                  <td className="py-3 pr-3">{character.race || "-"}</td>
                  <td className="py-3 pr-3">{character.subclass || "-"}</td>
                  <td className="py-3 pr-3">{character.route || "-"}</td>
                  <td className="py-3 pr-3"><Link className="btn-secondary" to={`/admin/characters/${character.id}`}>Открыть</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function AdminCharacterPage() {
  const { id: idParam } = useParams();
  const id = Number(idParam);
  const [character, setCharacter] = useState<Character | null>(null);
  const [inventory, setInventory] = useState<Inventory | null>(null);

  useEffect(() => {
    api.get<Character>(`/admin/characters/${id}`).then((response) => setCharacter(response.data));
    api.get<Inventory>(`/admin/characters/${id}/inventory`).then((response) => setInventory(response.data));
  }, [id]);

  if (!character) return <p>Загрузка...</p>;
  const stats = numberFields.filter((item) => !["level", "hp", "armor_class"].includes(item.field));

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <section className="panel p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-ember">{character.name}</h1>
            <p className="text-white/70">{character.class_name} / {character.subclass || "-"} / {character.race || "-"}</p>
            <p className="text-sm text-white/55">Владелец: {character.owner_username}</p>
          </div>
          <Link className="btn-secondary" to="/admin">Назад</Link>
        </div>
        <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Уровень" value={character.level} />
          <Stat label="XP" value={character.xp} />
          <Stat label="HP" value={character.hp} />
          <Stat label="КД" value={character.armor_class} />
          {stats.map((stat) => <Stat key={stat.field} label={stat.label} value={character[stat.field]} />)}
        </dl>
      </section>
      <ReadOnlyInventoryPanel inventory={inventory} />
    </div>
  );
}

function ReadOnlyInventoryPanel({ inventory }: { inventory: Inventory | null }) {
  return (
    <aside className="panel p-5">
      <h2 className="text-lg font-semibold text-ember">Инвентарь</h2>
      <p className="mt-1 text-sm text-white/70">{inventory?.gold ?? 0} зм / {inventory?.silver ?? 0} см / {inventory?.copper ?? 0} мм</p>
      <div className="mt-4 space-y-3">
        {inventory?.items.map((item) => (
          <div className="rounded-md border border-white/10 p-3" key={item.id}>
            <div className="font-semibold">{item.name}</div>
            <div className="text-sm text-white/60">{item.rarity} · {item.is_consumable ? "расходуемый" : "постоянный"}</div>
          </div>
        ))}
      </div>
    </aside>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return <div className="rounded-md bg-black/25 p-3"><dt className="text-xs uppercase text-white/45">{label}</dt><dd className="mt-1 text-lg font-semibold">{value}</dd></div>;
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/" element={<Protected><HomePage /></Protected>} />
        <Route path="/characters" element={<Protected><CharactersPage /></Protected>} />
        <Route path="/characters/new" element={<Protected><CharacterFormPage /></Protected>} />
        <Route path="/characters/:id" element={<Protected><CharacterPage /></Protected>} />
        <Route path="/characters/:id/edit" element={<Protected><CharacterFormPage edit /></Protected>} />
        <Route path="/shop" element={<Protected><ShopPage /></Protected>} />
        <Route path="/profile" element={<Protected><ProfilePage /></Protected>} />
        <Route path="/admin/characters/:id" element={<Protected><AdminCharacterPage /></Protected>} />
        <Route path="/admin" element={<Protected><AdminPage /></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
