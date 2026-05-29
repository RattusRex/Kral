import { FormEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Link, Navigate, Route, BrowserRouter as Router, Routes, useNavigate } from "react-router-dom";
import { LogOut, Shield, ShoppingBag, UserRound, UsersRound } from "lucide-react";
import { api, Character, Inventory, InventoryItem, ShopResult, TOKEN_KEY, User } from "./api";
import "./styles.css";

const rarities = ["Обычный", "Необычный", "Редкий"];
const hirelings = ["Плохой", "Хороший", "Опытный", "Экспертный"];

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
            <Link className="btn-secondary" to={`/shop?character=${character.id}`}>Магазин</Link>
          </div>
        </article>
      ))}
    </div>
  );
}

function CharacterPage() {
  const id = Number(location.pathname.split("/").pop());
  const [character, setCharacter] = useState<Character | null>(null);
  const [inventory, setInventory] = useState<Inventory | null>(null);

  useEffect(() => {
    api.get<Character[]>("/characters").then((response) => {
      setCharacter(response.data.find((item) => item.id === id) ?? null);
    });
    api.get<Inventory>(`/characters/${id}/inventory`).then((response) => setInventory(response.data));
  }, [id]);

  if (!character) return <p>Загрузка...</p>;
  const stats = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma", "investigation"] as const;

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
          {stats.map((stat) => <Stat key={stat} label={stat} value={character[stat]} />)}
        </dl>
      </section>
      <InventoryPanel inventory={inventory} onChange={setInventory} characterId={id} />
    </div>
  );
}

function InventoryPanel({ inventory, onChange, characterId }: { inventory: Inventory | null; onChange: (inventory: Inventory) => void; characterId: number }) {
  async function remove(item: InventoryItem) {
    const response = await api.delete<Inventory>(`/characters/${characterId}/inventory/items/${item.id}`);
    onChange(response.data);
  }

  async function sell(item: InventoryItem) {
    const response = await api.post<ShopResult>(`/characters/${characterId}/shop/sell`, { item_id: item.id });
    onChange(response.data.inventory);
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
              <button className="btn-secondary" onClick={() => sell(item)}>Продать</button>
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
  const [form, setForm] = useState({ item_name: "", rarity: "Обычный", is_consumable: false, searcher_type: "character", hireling_level: "Плохой" });
  const [result, setResult] = useState<ShopResult | null>(null);

  useEffect(() => {
    api.get<Character[]>("/characters").then((response) => {
      setCharacters(response.data);
      const selected = new URLSearchParams(location.search).get("character");
      setCharacterId(selected ?? String(response.data[0]?.id ?? ""));
    });
  }, []);

  async function buy(event: FormEvent) {
    event.preventDefault();
    const response = await api.post<ShopResult>(`/characters/${characterId}/shop/buy`, form);
    setResult(response.data);
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[420px_1fr]">
      <form className="panel flex flex-col gap-3 p-5" onSubmit={buy}>
        <h1 className="text-xl font-bold text-ember">Магазин</h1>
        <select className="field" value={characterId} onChange={(event) => setCharacterId(event.target.value)}>
          {characters.map((character) => <option key={character.id} value={character.id}>{character.name}</option>)}
        </select>
        <input className="field" placeholder="название предмета" value={form.item_name} onChange={(event) => setForm({ ...form, item_name: event.target.value })} />
        <select className="field" value={form.rarity} onChange={(event) => setForm({ ...form, rarity: event.target.value })}>{rarities.map((rarity) => <option key={rarity}>{rarity}</option>)}</select>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_consumable} onChange={(event) => setForm({ ...form, is_consumable: event.target.checked })} />Расходуемый</label>
        <select className="field" value={form.searcher_type} onChange={(event) => setForm({ ...form, searcher_type: event.target.value })}><option value="character">Персонаж</option><option value="hireling">Наёмник</option></select>
        <select className="field" value={form.hireling_level} onChange={(event) => setForm({ ...form, hireling_level: event.target.value })}>{hirelings.map((level) => <option key={level}>{level}</option>)}</select>
        <button className="btn">Найти и купить</button>
      </form>
      <ResultPanel result={result} />
    </div>
  );
}

function ResultPanel({ result }: { result: ShopResult | null }) {
  if (!result) return <section className="panel p-5 text-white/60">Результат поиска появится здесь.</section>;
  return (
    <section className="panel p-5">
      <h2 className="text-lg font-semibold text-ember">{result.success ? "Успех" : "Неуспех"}</h2>
      <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Бросок" value={result.search_roll} />
        <Stat label="Итог" value={result.total_roll} />
        <Stat label="DC" value={result.dc} />
        <Stat label="Дни" value={result.days} />
        <Stat label="Цена" value={result.item_price ?? "-"} />
        <Stat label="Наёмники" value={result.hireling_cost} />
        <Stat label="Итого" value={result.total_cost ?? "-"} />
      </dl>
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
  const [selected, setSelected] = useState("");
  const [amount, setAmount] = useState(1);
  const [item, setItem] = useState({ name: "", rarity: "Обычный", is_consumable: false });

  const selectedCharacter = useMemo(() => characters.find((character) => String(character.id) === selected), [characters, selected]);

  function load() {
    api.get<Character[]>("/admin/characters").then((response) => {
      setCharacters(response.data);
      setSelected(String(response.data[0]?.id ?? ""));
    });
  }

  useEffect(load, []);

  async function action(path: string, body?: unknown) {
    await api.post(`/admin/characters/${selected}/${path}`, body ?? {});
    load();
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
      <section className="panel flex flex-col gap-3 p-5">
        <h1 className="text-xl font-bold text-ember">Админка мастера</h1>
        <select className="field" value={selected} onChange={(event) => setSelected(event.target.value)}>
          {characters.map((character) => <option value={character.id} key={character.id}>{character.name}</option>)}
        </select>
        <input className="field" type="number" value={amount} onChange={(event) => setAmount(Number(event.target.value))} />
        <button className="btn" onClick={() => action("xp", { amount })}>Выдать XP</button>
        <button className="btn" onClick={() => action("gold", { amount })}>Выдать золото</button>
        <button className="btn-secondary" onClick={() => action("revive")}>Воскресить персонажа</button>
      </section>
      <section className="panel flex flex-col gap-3 p-5">
        <h2 className="text-lg font-semibold text-ember">{selectedCharacter?.name ?? "Персонаж"}</h2>
        <input className="field" placeholder="название" value={item.name} onChange={(event) => setItem({ ...item, name: event.target.value })} />
        <select className="field" value={item.rarity} onChange={(event) => setItem({ ...item, rarity: event.target.value })}>{rarities.map((rarity) => <option key={rarity}>{rarity}</option>)}</select>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={item.is_consumable} onChange={(event) => setItem({ ...item, is_consumable: event.target.checked })} />consumable</label>
        <button className="btn" onClick={() => action("item", item)}>Выдать предмет</button>
      </section>
    </div>
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
        <Route path="/characters" element={<Protected><CharactersPage /></Protected>} />
        <Route path="/characters/:id" element={<Protected><CharacterPage /></Protected>} />
        <Route path="/shop" element={<Protected><ShopPage /></Protected>} />
        <Route path="/profile" element={<Protected><ProfilePage /></Protected>} />
        <Route path="/admin" element={<Protected><AdminPage /></Protected>} />
        <Route path="*" element={<Navigate to="/characters" replace />} />
      </Routes>
    </Router>
  );
}

createRoot(document.getElementById("root")!).render(<App />);