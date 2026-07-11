import { Component, FormEvent, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import { Link, Navigate, Route, BrowserRouter as Router, Routes, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowDown, ArrowUp, BookOpen, CalendarDays, Check, ChevronDown, ChevronUp, Coins, Dice5, LogOut, MapPin, MessageSquare, Pencil, Plus, RefreshCw, Save, ScrollText, Search, Send, Shield, ShoppingBag, Swords, Trash2, Trophy, UserRound, UsersRound, X } from "lucide-react";
import { AbilityRoll, AdminGrantLog, AdminUser, api, AttackRoll, CalendarSummary, Character, CharacterAttack, ChatMessage, ContentBlock, DamageRoll, GameRecruitment, Inventory, InventoryItem, KarmaPurchase, KarmaPurchaseResult, LeaderboardEntry, MagicItem, MarketSaleLog, MarketSaleResult, PaginatedResponse, PROJECT_KEY, ProjectContext, ROLE_LABELS, SavingThrowRoll, ShopResult, ShopTransactionLog, SkillRoll, TOKEN_KEY, TransferLog, TransferTarget, User, UserRole } from "./api";
import "./styles.css";

const rarities = ["Обычный", "Необычный", "Редкий"];
// The game world started counting in-world time on this date; characters
// cannot be created (or spend downtime) earlier than it.
const GAME_EPOCH = "2025-06-01";
const hirelings = [
  { level: "Плохой", bonus: 0, cost: 1 },
  { level: "Хороший", bonus: 4, cost: 5 },
  { level: "Компетентный", bonus: 6, cost: 10 },
  { level: "Эксперт", bonus: 8, cost: 25 }
];
type SearcherType = "character" | "paid_hireling" | "personal_hireling" | "simulacrum";
type CalendarAgentType = "character" | "personal_hireling" | "simulacrum";
const searcherOptions: { type: SearcherType; label: string }[] = [
  { type: "character", label: "Персонаж" },
  { type: "personal_hireling", label: "Личный наёмник" },
  { type: "simulacrum", label: "Симулякр" },
  { type: "paid_hireling", label: "Платный наёмник" }
];
const characterClasses = [
  { name: "Бард", hitDie: "d8" },
  { name: "Варвар", hitDie: "d12" },
  { name: "Воин", hitDie: "d10" },
  { name: "Волшебник", hitDie: "d6" },
  { name: "Друид", hitDie: "d8" },
  { name: "Егерь", hitDie: "d8" },
  { name: "Жрец", hitDie: "d8" },
  { name: "Изобретатель", hitDie: "d8" },
  { name: "Колдун", hitDie: "d8" },
  { name: "Монах", hitDie: "d8" },
  { name: "Паладин", hitDie: "d10" },
  { name: "Плут", hitDie: "d8" },
  { name: "Следопыт", hitDie: "d10" },
  { name: "Чародей", hitDie: "d10" },
  { name: "Альтернативный следопыт", hitDie: "d10" },
  { name: "Альтернативный монах", hitDie: "d10" },
  { name: "Альтернативный изобретатель", hitDie: "d8" },
  { name: "Магус", hitDie: "d10" },
  { name: "Кровавый охотник", hitDie: "d10" },
  { name: "Призыватель", hitDie: "d8" },
  { name: "Некромант", hitDie: "d8" }
];
const defaultCharacterClass = characterClasses[0].name;
const textFields = [
  { field: "name", label: "Имя" },
  { field: "subclass", label: "Подкласс" },
  { field: "race", label: "Раса" },
  { field: "background", label: "Предыстория" },
  { field: "route", label: "Путь" }
] as const;
const numberFields = [
  { field: "level", label: "Уровень" },
  { field: "hp", label: "HP" },
  { field: "temp_hp", label: "Временные HP" },
  { field: "armor_class", label: "КД (Armor Class)" },
  { field: "speed", label: "Скорость" },
  { field: "strength", label: "Сила (STR)" },
  { field: "dexterity", label: "Ловкость (DEX)" },
  { field: "constitution", label: "Телосложение (CON)" },
  { field: "intelligence", label: "Интеллект (INT)" },
  { field: "wisdom", label: "Мудрость (WIS)" },
  { field: "charisma", label: "Харизма (CHA)" },
  { field: "investigation", label: "Расследование" }
] as const;
const adminUnitNumberFields = [
  { field: "personal_hireling_investigation", label: "Расследование личного наёмника" },
  { field: "simulacrum_investigation", label: "Расследование симулякра" }
] as const;
const adminUnitDateFields = [
  { field: "game_created_at", label: "Дата появления персонажа" },
  { field: "personal_hireling_acquired_at", label: "Дата появления личного наёмника" },
  { field: "simulacrum_created_at", label: "Дата появления симулякра" }
] as const;
const adminNumberFields = [
  { field: "level", label: "Уровень" },
  { field: "xp", label: "XP" },
  ...numberFields.filter(({ field }) => field !== "level"),
  ...adminUnitNumberFields
] as const;
const blankCharacter = {
  name: "",
  class_name: defaultCharacterClass,
  class_levels: [{ class_name: defaultCharacterClass, level: 1 }],
  subclass: "",
  race: "",
  background: "",
  route: "",
  game_created_at: GAME_EPOCH,
  level: 1,
  hp: 1,
  temp_hp: 0,
  armor_class: 10,
  speed: 30,
  strength: 10,
  dexterity: 10,
  constitution: 10,
  intelligence: 10,
  wisdom: 10,
  charisma: 10,
  investigation: 0,
  skill_proficiencies: [] as string[],
  skill_expertise: [] as string[],
  saving_throw_proficiencies: [] as string[]
};
const maxCharacters = 10;

function apiErrorDetail(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

function formatGameDate(value: string | undefined) {
  if (!value) return "-";
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) return value;
  return `${day}.${month}.${year}`;
}

function abilityModifier(score: number) {
  return Math.floor((score - 10) / 2);
}

function proficiencyBonus(level: number) {
  return 2 + Math.floor((Math.max(1, Math.min(20, level)) - 1) / 4);
}

const skills = [
  { key: "athletics", label: "Атлетика", ability: "strength" },
  { key: "acrobatics", label: "Акробатика", ability: "dexterity" },
  { key: "sleight_of_hand", label: "Ловкость рук", ability: "dexterity" },
  { key: "stealth", label: "Скрытность", ability: "dexterity" },
  { key: "arcana", label: "Магия", ability: "intelligence" },
  { key: "history", label: "История", ability: "intelligence" },
  { key: "investigation", label: "Расследование", ability: "intelligence" },
  { key: "nature", label: "Природа", ability: "intelligence" },
  { key: "religion", label: "Религия", ability: "intelligence" },
  { key: "animal_handling", label: "Уход за животными", ability: "wisdom" },
  { key: "insight", label: "Проницательность", ability: "wisdom" },
  { key: "medicine", label: "Медицина", ability: "wisdom" },
  { key: "perception", label: "Восприятие", ability: "wisdom" },
  { key: "survival", label: "Выживание", ability: "wisdom" },
  { key: "deception", label: "Обман", ability: "charisma" },
  { key: "intimidation", label: "Запугивание", ability: "charisma" },
  { key: "performance", label: "Выступление", ability: "charisma" },
  { key: "persuasion", label: "Убеждение", ability: "charisma" }
] as const;

const abilityDefinitions = [
  { label: "Сила", short: "STR", field: "strength" },
  { label: "Ловкость", short: "DEX", field: "dexterity" },
  { label: "Телосложение", short: "CON", field: "constitution" },
  { label: "Интеллект", short: "INT", field: "intelligence" },
  { label: "Мудрость", short: "WIS", field: "wisdom" },
  { label: "Харизма", short: "CHA", field: "charisma" }
] as const;

function signed(value: number) {
  return value >= 0 ? `+${value}` : String(value);
}

function classOptionsForValue(value: string) {
  if (!value || characterClasses.some((characterClass) => characterClass.name === value)) {
    return characterClasses;
  }
  return [{ name: value, hitDie: "-" }, ...characterClasses];
}

function hitDieForClass(value: string) {
  return classOptionsForValue(value).find((characterClass) => characterClass.name === value)?.hitDie ?? "-";
}

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
  const [projects, setProjects] = useState<ProjectContext[]>([]);
  const [project, setProject] = useState<ProjectContext | null>(null);

  useEffect(() => {
    api.get<ProjectContext[]>("/projects").then((response) => {
      setProjects(response.data);
      const stored = Number(localStorage.getItem(PROJECT_KEY));
      const selected = response.data.find((item) => item.id === stored) ?? response.data[0];
      if (selected) {
        localStorage.setItem(PROJECT_KEY, String(selected.id));
        setProject(selected);
      }
    });
  }, []);

  function selectProject(id: number) {
    localStorage.setItem(PROJECT_KEY, String(id));
    window.location.assign("/");
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PROJECT_KEY);
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-[#101217] text-parchment">
      <header className="sticky top-0 z-10 border-b border-white/10 bg-[#101217]/95 backdrop-blur">
        <nav className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <Link to="/characters" className="text-lg font-bold text-ember">Эпоха Катастроф</Link>
          <div className="flex flex-wrap items-center gap-2">
            {projects.length > 0 && <select aria-label="Проект" className="field max-w-52" value={project?.id ?? ""} onChange={(event) => selectProject(Number(event.target.value))}>{projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>}
            <Link className="btn-secondary" to="/"><UsersRound size={16} />Меню</Link>
            <Link className="btn-secondary" to="/characters"><UsersRound size={16} />Персонажи</Link>
            {project?.features.shop !== false && <Link className="btn-secondary" to="/shop"><ShoppingBag size={16} />Магазин</Link>}
            {project?.features.market !== false && <Link className="btn-secondary" to="/market"><Coins size={16} />Рынок</Link>}
            {project?.features.karma_shop !== false && <Link className="btn-secondary" to="/karma-shop"><ShoppingBag size={16} />Карма</Link>}
            <Link className="btn-secondary" to="/leaderboard"><Trophy size={16} />Лидеры</Link>
            <Link className="btn-secondary" to="/chat"><MessageSquare size={16} />Чат</Link>
            {project?.features.recruitments !== false && <Link className="btn-secondary" to="/game-recruitments"><CalendarDays size={16} />Набор на игры</Link>}
            <Link className="btn-secondary" to="/profile"><UserRound size={16} />Профиль</Link>
            {(user?.is_owner || project?.is_admin) && <Link className="btn-secondary" to="/admin"><Shield size={16} />Админ</Link>}
            {project?.can_manage_settings && <Link className="btn-secondary" to="/project-settings"><Shield size={16} />Настройки проекта</Link>}
            {user?.is_owner && <Link className="btn-secondary" to="/project-management"><Shield size={16} />Управление проектами</Link>}
            {user?.is_admin && <Link className="btn-secondary" to="/admin/shop-logs"><ScrollText size={16} />Логи</Link>}
            {user?.is_admin && <Link className="btn-secondary" to="/admin/market-sales"><ScrollText size={16} />Рынок-логи</Link>}
            {user?.is_admin && <Link className="btn-secondary" to="/admin/transfer-logs"><ScrollText size={16} />Передачи</Link>}
            {user?.is_admin && <Link className="btn-secondary" to="/admin/karma-shop-logs"><ScrollText size={16} />Карма-логи</Link>}
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
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Link className="btn" to="/shop"><ShoppingBag size={18} />Магазин</Link>
          <Link className="btn" to="/market"><Coins size={18} />Рынок</Link>
          <Link className="btn" to="/karma-shop"><ShoppingBag size={18} />Магазин Кармы</Link>
          <Link className="btn" to="/characters"><UsersRound size={18} />Мои персонажи</Link>
          <Link className="btn" to="/leaderboard"><Trophy size={18} />Таблица лидеров</Link>
          <Link className="btn" to="/chat"><MessageSquare size={18} />Чат</Link>
          <Link className="btn" to="/game-recruitments"><CalendarDays size={18} />Набор на игры</Link>
          <Link className="btn" to="/server-rules"><BookOpen size={18} />Правила сервера</Link>
          <Link className="btn" to="/approved-homebrew"><ScrollText size={18} />Одобренное ХБ</Link>
        </div>
      </section>
      <aside className="panel p-5">
        <h2 className="text-lg font-semibold text-ember">{user.username}</h2>
        <p className="mt-2 text-white/70">{user.email}</p>
        <p className="mt-3 text-sm text-white/80">Роль: {ROLE_LABELS[user.role ?? "player"]}</p>
        <p className="mt-4 text-xl font-semibold">Карма: {user.karma}</p>
      </aside>
    </div>
  );
}

const PROJECT_FEATURE_LABELS: Record<string, string> = {
  shop: "Магазин",
  market: "Рынок",
  karma_shop: "Магазин Кармы",
  recruitments: "Набор на игры",
  personal_hirelings: "Личные наёмники",
  simulacrums: "Симулякры"
};

function ProjectSettingsPage() {
  const [project, setProject] = useState<ProjectContext | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.get<ProjectContext>("/projects/current").then((response) => setProject(response.data)).catch((requestError) => setError(apiErrorDetail(requestError, "Нет доступа к настройкам проекта")));
  }, []);
  async function toggle(feature: string, enabled: boolean) {
    if (!project) return;
    const response = await api.patch<ProjectContext>(`/projects/${project.id}/settings`, { features: { [feature]: enabled } });
    setProject(response.data);
  }
  if (error) return <section className="panel p-5 text-red-300">{error}</section>;
  if (!project) return <p>Загрузка...</p>;
  return <section className="panel p-5"><h1 className="text-2xl font-bold text-ember">Настройки проекта</h1><p className="mt-2 text-white/60">{project.name} · {ROLE_LABELS[project.role]}</p><div className="mt-5 grid gap-3 sm:grid-cols-2">{Object.entries(PROJECT_FEATURE_LABELS).map(([feature, label]) => <label className="flex items-center justify-between rounded-md border border-white/10 p-3" key={feature}><span>{label}</span><input aria-label={label} type="checkbox" checked={project.features[feature as keyof typeof project.features]} onChange={(event) => toggle(feature, event.target.checked)} /></label>)}</div></section>;
}

function ProjectManagementPage() {
  const { user, loading } = useAuth();
  const [projects, setProjects] = useState<ProjectContext[]>([]);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [error, setError] = useState("");
  async function load() {
    const response = await api.get<ProjectContext[]>("/projects");
    setProjects(response.data);
  }
  useEffect(() => { if (user?.is_owner) load().catch((e) => setError(apiErrorDetail(e, "Не удалось загрузить проекты"))); }, [user?.is_owner]);
  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      await api.post("/projects", { name, slug: slug || undefined });
      setName(""); setSlug(""); await load();
    } catch (e) { setError(apiErrorDetail(e, "Не удалось создать проект")); }
  }
  async function remove(project: ProjectContext) {
    if (!window.confirm(`Удалить проект «${project.name}» и все его данные?`)) return;
    try {
      await api.delete(`/projects/${project.id}`);
      if (localStorage.getItem(PROJECT_KEY) === String(project.id)) localStorage.removeItem(PROJECT_KEY);
      await load();
    } catch (e) { setError(apiErrorDetail(e, "Не удалось удалить проект")); }
  }
  if (loading) return <p>Загрузка...</p>;
  if (!user?.is_owner) return <Navigate to="/" replace />;
  return <div className="space-y-5"><section className="panel p-5"><h1 className="text-2xl font-bold text-ember">Управление проектами</h1><p className="mt-2 text-white/60">Создание и полное удаление независимых игровых экосистем.</p><form className="mt-5 grid gap-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={create}><input required maxLength={100} className="field" placeholder="Название" value={name} onChange={(e) => setName(e.target.value)} /><input pattern="[a-z0-9-]+" maxLength={100} className="field" placeholder="slug (необязательно)" value={slug} onChange={(e) => setSlug(e.target.value)} /><button className="btn"><Plus size={16} />Создать</button></form>{error && <p className="mt-3 text-red-300">{error}</p>}</section><section className="grid gap-3">{projects.map((project) => <article className="panel flex items-center justify-between gap-4 p-4" key={project.id}><div><h2 className="font-semibold text-ember">{project.name}</h2><p className="text-sm text-white/50">{project.slug}</p></div><button className="btn-secondary text-red-200" disabled={(project as ProjectContext & { is_default?: boolean }).is_default} onClick={() => remove(project)}><Trash2 size={16} />Удалить</button></article>)}</section></div>;
}

type ContentPageSlug = "server-rules" | "approved-homebrew";

function ContentPage({ pageSlug, title }: { pageSlug: ContentPageSlug; title: string }) {
  const { user, loading: userLoading } = useAuth();
  const [blocks, setBlocks] = useState<ContentBlock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<number | "new" | null>(null);
  const [form, setForm] = useState({ title: "", content: "" });

  function load() {
    setLoading(true);
    setError("");
    api.get<ContentBlock[]>(`/content-pages/${pageSlug}`)
      .then((response) => setBlocks(response.data))
      .catch((requestError) => setError(apiErrorDetail(requestError, "Не удалось загрузить страницу")))
      .finally(() => setLoading(false));
  }

  useEffect(load, [pageSlug]);

  function startCreate() {
    setEditingId("new");
    setForm({ title: "", content: "" });
  }

  function startEdit(block: ContentBlock) {
    setEditingId(block.id);
    setForm({ title: block.title, content: block.content });
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      if (editingId === "new") {
        await api.post(`/content-pages/${pageSlug}`, form);
      } else {
        await api.patch(`/content-pages/${pageSlug}/${editingId}`, form);
      }
      setEditingId(null);
      load();
    } catch (requestError) {
      setError(apiErrorDetail(requestError, "Не удалось сохранить блок"));
    }
  }

  async function remove(block: ContentBlock) {
    if (!window.confirm(`Удалить блок «${block.title}»?`)) return;
    try {
      await api.delete(`/content-pages/${pageSlug}/${block.id}`);
      if (editingId === block.id) setEditingId(null);
      load();
    } catch (requestError) {
      setError(apiErrorDetail(requestError, "Не удалось удалить блок"));
    }
  }

  async function move(index: number, offset: -1 | 1) {
    const target = index + offset;
    if (target < 0 || target >= blocks.length) return;
    const reordered = [...blocks];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    setBlocks(reordered);
    try {
      const response = await api.put<ContentBlock[]>(`/content-pages/${pageSlug}/order`, {
        block_ids: reordered.map((block) => block.id)
      });
      setBlocks(response.data);
    } catch (requestError) {
      setError(apiErrorDetail(requestError, "Не удалось изменить порядок"));
      load();
    }
  }

  if (loading || userLoading) return <p>Загрузка...</p>;

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ember">{title}</h1>
          <p className="mt-1 text-sm text-white/60">Информационные разделы кампании</p>
        </div>
        {user?.is_admin && editingId !== "new" && <button className="btn" onClick={startCreate}><Plus size={16} />Создать блок</button>}
      </div>
      {error && <p className="rounded-md border border-red-400/30 bg-red-950/30 p-3 text-sm text-red-200">{error}</p>}
      {editingId === "new" && (
        <ContentBlockForm form={form} setForm={setForm} onSubmit={save} onCancel={() => setEditingId(null)} />
      )}
      {!blocks.length && editingId !== "new" && (
        <section className="panel p-8 text-center text-white/60">Разделы пока не добавлены.</section>
      )}
      {blocks.map((block, index) => editingId === block.id ? (
        <ContentBlockForm key={block.id} form={form} setForm={setForm} onSubmit={save} onCancel={() => setEditingId(null)} />
      ) : (
        <section className="panel p-5" key={block.id}>
          <div className="flex items-start justify-between gap-4">
            <h2 className="text-xl font-semibold text-ember">{block.title}</h2>
            {user?.is_admin && (
              <div className="flex flex-wrap justify-end gap-2">
                <button className="btn-secondary p-2" aria-label="Переместить вверх" title="Переместить вверх" disabled={index === 0} onClick={() => move(index, -1)}><ArrowUp size={16} /></button>
                <button className="btn-secondary p-2" aria-label="Переместить вниз" title="Переместить вниз" disabled={index === blocks.length - 1} onClick={() => move(index, 1)}><ArrowDown size={16} /></button>
                <button className="btn-secondary" onClick={() => startEdit(block)}><Pencil size={16} />Редактировать</button>
                <button className="btn-secondary" onClick={() => remove(block)}><Trash2 size={16} />Удалить</button>
              </div>
            )}
          </div>
          <p className="mt-4 whitespace-pre-wrap text-white/80">{block.content}</p>
        </section>
      ))}
    </div>
  );
}

function ContentBlockForm({ form, setForm, onSubmit, onCancel }: {
  form: { title: string; content: string };
  setForm: (form: { title: string; content: string }) => void;
  onSubmit: (event: FormEvent) => void;
  onCancel: () => void;
}) {
  return (
    <form className="panel flex flex-col gap-3 p-5" onSubmit={onSubmit}>
      <label className="field-label"><span>Название</span><input className="field" required maxLength={200} value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
      <label className="field-label"><span>Текст</span><textarea className="field min-h-40" required maxLength={20000} value={form.content} onChange={(event) => setForm({ ...form, content: event.target.value })} /></label>
      <div className="flex gap-2"><button className="btn" type="submit"><Save size={16} />Сохранить</button><button className="btn-secondary" type="button" onClick={onCancel}><X size={16} />Отмена</button></div>
    </form>
  );
}

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    function handleLogout() { forceUpdate(n => n + 1); }
    window.addEventListener("auth:logout", handleLogout);
    return () => window.removeEventListener("auth:logout", handleLogout);
  }, []);

  if (loading) return <div className="p-6 text-parchment">Загрузка...</div>;
  if (!localStorage.getItem(TOKEN_KEY)) return <Navigate to="/login" replace />;
  return <Shell user={user}>{children}</Shell>;
}

function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [unverifiedEmail, setUnverifiedEmail] = useState("");
  const [notice, setNotice] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    setUnverifiedEmail("");
    const body = new URLSearchParams({ username: email, password });
    try {
      const response = await api.post("/login", body);
      localStorage.setItem(TOKEN_KEY, response.data.access_token);
      navigate("/characters");
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
      if (detail?.code === "email_not_verified") {
        setError(detail.message);
        setUnverifiedEmail(detail.email ?? email);
      } else {
        setError("Не удалось войти");
      }
    }
  }

  async function resend() {
    setError("");
    try {
      await api.post("/email/resend", { email: unverifiedEmail });
      setNotice("Новое письмо отправлено. Проверьте почту.");
    } catch {
      setError("Не удалось повторно отправить письмо");
    }
  }

  return <AuthPanel title="Вход" error={error} onSubmit={submit}>
    <input className="field" placeholder="email" value={email} onChange={(event) => setEmail(event.target.value)} />
    <input className="field" placeholder="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
    <button className="btn" type="submit">Войти</button>
    {unverifiedEmail && <button className="btn-secondary" type="button" onClick={resend}>Отправить письмо повторно</button>}
    {notice && <p className="text-sm text-green-300">{notice}</p>}
    <Link className="btn-secondary" to="/register">Перейти к регистрации</Link>
  </AuthPanel>;
}

function Register() {
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [registeredEmail, setRegisteredEmail] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api.post("/users", form);
      setRegisteredEmail(form.email);
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail ?? "Не удалось создать аккаунт");
    }
  }

  if (registeredEmail) return <AuthPanel title="Проверьте почту" error="" onSubmit={(event) => event.preventDefault()}>
    <p className="text-sm text-white/75">Мы отправили ссылку подтверждения на {registeredEmail}. Она действует 24 часа.</p>
    <Link className="btn" to="/login">Перейти ко входу</Link>
  </AuthPanel>;

  return <AuthPanel title="Регистрация" error={error} onSubmit={submit}>
    <input className="field" placeholder="username" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} />
    <input className="field" placeholder="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
    <input
      className="field"
      placeholder="password"
      type="password"
      minLength={12}
      maxLength={72}
      autoComplete="new-password"
      value={form.password}
      onChange={(event) => setForm({ ...form, password: event.target.value })}
    />
    <p className="text-xs text-parchment/70">
      Пароль должен содержать не менее 12 символов: заглавную и строчную буквы, цифру и специальный символ.
    </p>
    <button className="btn" type="submit">Создать аккаунт</button>
    <Link className="btn-secondary" to="/login">Войти</Link>
  </AuthPanel>;
}

function VerifyEmail() {
  const [params] = useSearchParams();
  const [state, setState] = useState<"loading" | "success" | "error">("loading");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setState("error");
      return;
    }
    api.post("/email/verify", { token })
      .then(() => setState("success"))
      .catch(() => setState("error"));
  }, [params]);

  return <AuthPanel title="Подтверждение почты" error="" onSubmit={(event) => event.preventDefault()}>
    {state === "loading" && <p>Проверяем ссылку...</p>}
    {state === "success" && <><p className="text-green-300">Почта подтверждена. Теперь можно войти.</p><Link className="btn" to="/login">Войти</Link></>}
    {state === "error" && <><p className="text-red-300">Ссылка недействительна или истекла.</p><Link className="btn-secondary" to="/login">Вернуться ко входу</Link></>}
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

function ClassSelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <label className="field-label">
      <span>Класс</span>
      <select className="field" value={value} onChange={(event) => onChange(event.target.value)}>
        {classOptionsForValue(value).map((characterClass) => (
          <option key={characterClass.name} value={characterClass.name}>{characterClass.name}</option>
        ))}
      </select>
      <span className="text-xs text-white/55">Кость хитов: {hitDieForClass(value)}</span>
    </label>
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

  const characterLimitReached = characters.length >= maxCharacters;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-ember">Мои персонажи</h1>
          <p className="text-sm text-white/65">Слоты: {characters.length}/{maxCharacters}</p>
        </div>
        {characterLimitReached ? (
          <button className="btn" disabled><Plus size={16} />Лимит персонажей</button>
        ) : (
          <Link className="btn" to="/characters/new"><Plus size={16} />Создать персонажа</Link>
        )}
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

function CalendarPanel({ characterId, agentType = "character", title = "Календарь персонажа" }: { characterId: number; agentType?: CalendarAgentType; title?: string }) {
  const [summary, setSummary] = useState<CalendarSummary | null>(null);
  const [form, setForm] = useState({ start_date: GAME_EPOCH, days: 1, reason: "" });
  const [workForm, setWorkForm] = useState({ start_date: GAME_EPOCH, days: 1, tools: "", proficiency_modifier: 0 });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ start_date: GAME_EPOCH, days: 1, reason: "" });
  const [page, setPage] = useState(1);
  const canManage = summary?.can_manage ?? false;
  const isUnitCalendar = agentType !== "character";
  const createdAtLabel = agentType === "personal_hireling"
    ? "Дата получения"
    : "Дата создания";
  const calendarPath = agentType === "character"
    ? `/characters/${characterId}/calendar`
    : `/characters/${characterId}/calendar/agents/${agentType}`;

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.get<CalendarSummary>(calendarPath, { params: { page, page_size: 10 } })
      .then((response) => {
        if (!active) return;
        setSummary(response.data);
        setForm((current) => ({ ...current, start_date: response.data.created_at }));
        setWorkForm((current) => ({ ...current, start_date: response.data.created_at }));
      })
      .catch((loadError) => active && setError(apiErrorDetail(loadError, "Не удалось загрузить календарь")))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [calendarPath, characterId, page]);

  async function addEntry(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api.post<CalendarSummary>(`${calendarPath}/downtime`, {
        start_date: form.start_date,
        days: Number(form.days),
        reason: form.reason
      });
      if (page === 1) {
        const response = await api.get<CalendarSummary>(calendarPath, { params: { page: 1, page_size: 10 } });
        setSummary(response.data);
      } else {
        setPage(1);
      }
      setForm({ start_date: summary?.created_at ?? GAME_EPOCH, days: 1, reason: "" });
    } catch (addError) {
      setError(apiErrorDetail(addError, "Не удалось добавить запись"));
    }
  }

  async function addWork(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api.post(`${calendarPath}/work`, {
        ...workForm,
        days: Number(workForm.days),
        proficiency_modifier: Number(workForm.proficiency_modifier)
      });
      const response = await api.get<CalendarSummary>(calendarPath, { params: { page: 1, page_size: 10 } });
      setSummary(response.data);
      setPage(1);
      setWorkForm({ start_date: response.data.created_at, days: 1, tools: "", proficiency_modifier: 0 });
    } catch (workError) {
      setError(apiErrorDetail(workError, "Не удалось оформить работу"));
    }
  }

  async function removeEntry(entryId: number) {
    setError("");
    try {
      await api.delete<CalendarSummary>(`${calendarPath}/downtime/${entryId}`);
      const nextPage = summary?.entries.length === 1 && page > 1 ? page - 1 : page;
      const response = await api.get<CalendarSummary>(calendarPath, { params: { page: nextPage, page_size: 10 } });
      setSummary(response.data);
      if (nextPage !== page) setPage(nextPage);
      if (editingId === entryId) setEditingId(null);
    } catch (removeError) {
      setError(apiErrorDetail(removeError, "Не удалось удалить запись"));
    }
  }

  function startEdit(entry: { id: number; start_date: string; days: number; reason: string }) {
    setError("");
    setEditingId(entry.id);
    setEditForm({ start_date: entry.start_date, days: entry.days, reason: entry.reason });
  }

  async function saveEdit(event: FormEvent) {
    event.preventDefault();
    if (editingId === null) return;
    setError("");
    try {
      await api.patch<CalendarSummary>(`${calendarPath}/downtime/${editingId}`, {
        start_date: editForm.start_date,
        days: Number(editForm.days),
        reason: editForm.reason
      });
      const response = await api.get<CalendarSummary>(calendarPath, { params: { page, page_size: 10 } });
      setSummary(response.data);
      setEditingId(null);
    } catch (editError) {
      setError(apiErrorDetail(editError, "Не удалось изменить запись"));
    }
  }

  return (
    <section className="panel p-5">
      <div className="mb-4 flex items-center gap-2">
        <CalendarDays size={18} className="text-ember" />
        <h2 className="text-lg font-semibold text-ember">{title}</h2>
      </div>
      {loading && !summary ? (
        <p className="text-sm text-white/55">Загрузка...</p>
      ) : summary ? (
        <>
          <dl className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <Stat label={createdAtLabel} value={formatGameDate(summary.created_at)} />
            <Stat label="Текущая игровая дата" value={formatGameDate(summary.current_date)} />
            <Stat label="Всего дней" value={summary.total_days} />
            <Stat label="Занятые дни" value={summary.busy_days} />
            <Stat label="Свободные дни" value={summary.free_days} />
          </dl>

          {!isUnitCalendar && (
            <form className="mt-5 grid gap-3 md:grid-cols-[150px_110px_1fr_auto]" onSubmit={addWork}>
              <label className="field-label"><span>Дата начала</span><input className="field" type="date" min={summary.created_at} max={summary.current_date} value={workForm.start_date} onChange={(event) => setWorkForm({ ...workForm, start_date: event.target.value })} /></label>
              <label className="field-label"><span>Дней работы</span><input className="field" type="number" min={1} value={workForm.days} onChange={(event) => setWorkForm({ ...workForm, days: Number(event.target.value) })} /></label>
              <label className="field-label"><span>Используемые инструменты</span><input className="field" required maxLength={255} placeholder="Инструменты кузнеца" value={workForm.tools} onChange={(event) => setWorkForm({ ...workForm, tools: event.target.value })} /></label>
              <label className="field-label"><span>Модификатор владения</span><input className="field" type="number" min={-20} max={100} value={workForm.proficiency_modifier} onChange={(event) => setWorkForm({ ...workForm, proficiency_modifier: Number(event.target.value) })} /></label>
              <button className="btn self-end" type="submit"><Plus size={16} />Работать</button>
            </form>
          )}

          {!isUnitCalendar && (
            <details className="mt-4"><summary className="cursor-pointer text-sm text-white/60">Добавить другую занятость</summary><form className="mt-3 grid gap-3 md:grid-cols-[150px_110px_1fr_auto]" onSubmit={addEntry}>
              <label className="field-label">
                <span>Дата начала</span>
                <input
                  className="field"
                  type="date"
                  min={summary.created_at}
                  max={summary.current_date}
                  value={form.start_date}
                  onChange={(event) => setForm({ ...form, start_date: event.target.value })}
                />
              </label>
              <label className="field-label">
                <span>Дней</span>
                <input
                  className="field"
                  type="number"
                  min={1}
                  value={form.days}
                  onChange={(event) => setForm({ ...form, days: Number(event.target.value) })}
                />
              </label>
              <label className="field-label">
                <span>Причина</span>
                <input
                  className="field"
                  placeholder="Крафт, исследование, обучение..."
                  value={form.reason}
                  onChange={(event) => setForm({ ...form, reason: event.target.value })}
                />
              </label>
              <button className="btn self-end" type="submit"><Plus size={16} />Занять дни</button>
            </form></details>
          )}
          {error && <p className="mt-3 text-sm text-red-300">{error}</p>}

          <div className="mt-4 space-y-2">
            <h3 className="text-sm font-semibold text-white/70">Журнал занятых дней</h3>
            {!canManage && (
              <p className="text-xs text-white/45">Занятые дни нельзя удалять или редактировать. За исправлениями обратитесь к администратору.</p>
            )}
            {summary.entries.length === 0 ? (
              <p className="text-sm text-white/55">Занятых дней пока нет.</p>
            ) : (
              summary.entries.map((entry) => (
                <div className="rounded-md border border-white/10 px-3 py-2" key={entry.id}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="font-semibold">
                        <div>{formatGameDate(entry.start_date)} — {formatGameDate(entry.end_date)}</div>
                        <div className="text-sm text-white/70">Всего: {entry.days} дн.</div>
                        {entry.source === "shop" && <span className="ml-2 rounded bg-amber-400/15 px-2 py-0.5 text-xs text-amber-200">магазин</span>}
                        {entry.source === "work" && <span className="ml-2 rounded bg-emerald-400/15 px-2 py-0.5 text-xs text-emerald-200">работа</span>}
                      </div>
                      <div className="text-sm text-white/60">{entry.reason || "Без описания"}</div>
                      {entry.source === "work" && <div className="text-xs text-emerald-200">Модификатор {entry.proficiency_modifier! >= 0 ? "+" : ""}{entry.proficiency_modifier} · заработок {Math.floor((entry.income_copper ?? 0) / 100)} зм {Math.floor(((entry.income_copper ?? 0) % 100) / 10)} см {(entry.income_copper ?? 0) % 10} мм</div>}
                    </div>
                    {canManage && (
                      <div className="flex gap-2">
                        {entry.source !== "work" && <button className="btn-secondary" onClick={() => startEdit(entry)} type="button"><Pencil size={16} />Изменить</button>}
                        <button className="btn-secondary" onClick={() => removeEntry(entry.id)} type="button"><Trash2 size={16} />Удалить</button>
                      </div>
                    )}
                  </div>
                  {canManage && entry.source !== "work" && editingId === entry.id && (
                    <form className="mt-3 grid gap-3 md:grid-cols-[150px_110px_1fr_auto_auto]" onSubmit={saveEdit}>
                      <label className="field-label">
                        <span>Дата начала</span>
                        <input
                          className="field"
                          type="date"
                          min={summary.created_at}
                          max={summary.current_date}
                          value={editForm.start_date}
                          onChange={(event) => setEditForm({ ...editForm, start_date: event.target.value })}
                        />
                      </label>
                      <label className="field-label">
                        <span>Дней</span>
                        <input
                          className="field"
                          type="number"
                          min={1}
                          value={editForm.days}
                          onChange={(event) => setEditForm({ ...editForm, days: Number(event.target.value) })}
                        />
                      </label>
                      <label className="field-label">
                        <span>Причина</span>
                        <input
                          className="field"
                          value={editForm.reason}
                          onChange={(event) => setEditForm({ ...editForm, reason: event.target.value })}
                        />
                      </label>
                      <button className="btn self-end" type="submit"><Save size={16} />Сохранить</button>
                      <button className="btn-secondary self-end" type="button" onClick={() => setEditingId(null)}><X size={16} />Отмена</button>
                    </form>
                  )}
                </div>
              ))
            )}
            {summary.pages > 1 && (
              <div className="mt-3 flex items-center justify-between gap-3 text-sm">
                <button className="btn-secondary" disabled={page <= 1} onClick={() => setPage(page - 1)} type="button">Назад</button>
                <span>Страница {summary.page} из {summary.pages} · записей: {summary.total_entries}</span>
                <button className="btn-secondary" disabled={page >= summary.pages} onClick={() => setPage(page + 1)} type="button">Вперёд</button>
              </div>
            )}
          </div>
        </>
      ) : (
        <p className="text-sm text-red-300">{error || "Календарь недоступен"}</p>
      )}
    </section>
  );
}

function CharacterPage() {
  const { id: idParam } = useParams();
  const id = Number(idParam);
  const [character, setCharacter] = useState<Character | null>(null);
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [transferTargets, setTransferTargets] = useState<TransferTarget[]>([]);
  const [attacks, setAttacks] = useState<CharacterAttack[]>([]);
  const [attackForm, setAttackForm] = useState({ name: "", attack_bonus: 0, damage: "" });
  const [attackRoll, setAttackRoll] = useState<AttackRoll | null>(null);
  const [damageRoll, setDamageRoll] = useState<DamageRoll | null>(null);
  const [abilityRoll, setAbilityRoll] = useState<AbilityRoll | null>(null);
  const [savingThrowRoll, setSavingThrowRoll] = useState<SavingThrowRoll | null>(null);
  const [attackError, setAttackError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<Character[]>("/characters"),
      api.get<TransferTarget[]>("/characters/transfer-targets"),
      api.get<Inventory>(`/characters/${id}/inventory`),
      api.get<CharacterAttack[]>(`/characters/${id}/attacks`)
    ]).then(([charactersResponse, targetsResponse, inventoryResponse, attacksResponse]) => {
      setCharacter(charactersResponse.data.find((item) => item.id === id) ?? null);
      setTransferTargets(targetsResponse.data);
      setInventory(inventoryResponse.data);
      setAttacks(attacksResponse.data);
    });
  }, [id]);

  if (!character) return <p>Загрузка...</p>;
  const abilities = abilityDefinitions.map((ability) => ({
    ...ability,
    value: character[ability.field]
  }));

  async function createAttack(event: FormEvent) {
    event.preventDefault();
    setAttackError("");
    try {
      const response = await api.post<CharacterAttack>(`/characters/${id}/attacks`, attackForm);
      setAttacks((current) => [...current, response.data]);
      setAttackForm({ name: "", attack_bonus: 0, damage: "" });
    } catch (createError) {
      setAttackError(apiErrorDetail(createError, "Не удалось добавить атаку"));
    }
  }

  async function removeAttack(attack: CharacterAttack) {
    setAttackError("");
    try {
      await api.delete(`/characters/${id}/attacks/${attack.id}`);
      setAttacks((current) => current.filter((item) => item.id !== attack.id));
    } catch (removeError) {
      setAttackError(apiErrorDetail(removeError, "Не удалось удалить атаку"));
    }
  }

  async function rollAttack(attack: CharacterAttack) {
    setAttackError("");
    setDamageRoll(null);
    try {
      const response = await api.post<AttackRoll>(`/characters/${id}/attacks/${attack.id}/roll`);
      setAttackRoll(response.data);
    } catch (rollError) {
      setAttackError(apiErrorDetail(rollError, "Не удалось выполнить бросок атаки"));
    }
  }

  async function rollDamage(attack: CharacterAttack) {
    setAttackError("");
    setAttackRoll(null);
    try {
      const response = await api.post<DamageRoll>(`/characters/${id}/attacks/${attack.id}/roll-damage`);
      setDamageRoll(response.data);
    } catch (rollError) {
      setAttackError(apiErrorDetail(rollError, "Не удалось выполнить бросок урона"));
    }
  }

  async function rollAbility(ability: string) {
    setSavingThrowRoll(null);
    try {
      const response = await api.post<AbilityRoll>(`/characters/${id}/roll-ability/${ability}`);
      setAbilityRoll(response.data);
    } catch {
      // ignore
    }
  }

  async function rollSavingThrow(ability: string) {
    setAbilityRoll(null);
    try {
      const response = await api.post<SavingThrowRoll>(`/characters/${id}/roll-saving-throw/${ability}`);
      setSavingThrowRoll(response.data);
    } catch {
      // ignore
    }
  }

  return (
    <div className="space-y-4">
      <section className="panel p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase text-white/45">Лист персонажа</p>
            <h1 className="text-3xl font-bold text-ember">{character.name}</h1>
            <p className="mt-1 text-white/70">{(character.class_levels?.length ? character.class_levels : [{ class_name: character.class_name, level: character.level }]).map((entry) => `${entry.class_name} — ${entry.level} ур.`).join(" · ")}{character.subclass ? ` / ${character.subclass}` : ""}</p>
          </div>
          <Link className="btn-secondary" to={`/characters/${id}/edit`}>Редактировать</Link>
        </div>
        <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Stat label="Статус" value={character.is_dead ? "Мёртв" : "Жив"} />
          <Stat label="Класс" value={character.class_name} />
          <Stat label="Кость хитов" value={hitDieForClass(character.class_name)} />
          <Stat label="Раса" value={character.race || "-"} />
          <Stat label="Предыстория" value={character.background || "-"} />
          <Stat label="Путь" value={character.route || "-"} />
          <Stat label="Уровень" value={character.level} />
          <Stat label="XP" value={character.xp} />
          <Stat label="Бонус мастерства" value={signed(proficiencyBonus(character.level))} />
        </dl>
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-4">
          <section className="panel p-5">
            <div className="mb-4 flex items-center gap-2">
              <Shield size={18} className="text-ember" />
              <h2 className="text-lg font-semibold text-ember">Боевой блок</h2>
            </div>
            <dl className="grid grid-cols-2 gap-3 md:grid-cols-5">
              <Stat label="HP" value={character.hp} />
              <Stat label="Временные HP" value={character.temp_hp} />
              <Stat label="КД" value={character.armor_class} />
              <Stat label="Скорость" value={`${character.speed} фт`} />
              <Stat label="Расследование" value={signed(character.investigation)} />
            </dl>
          </section>

          <SkillsPanel character={character} onChange={setCharacter} />

          <CalendarPanel characterId={id} />

          {character.personal_hireling_enabled && (
            <CalendarPanel
              characterId={id}
              agentType="personal_hireling"
              title="Календарь личного наёмника"
            />
          )}

          {character.simulacrum_enabled && (
            <CalendarPanel
              characterId={id}
              agentType="simulacrum"
              title="Календарь симулякра"
            />
          )}

          <section className="panel p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-ember">Характеристики</h2>
              {abilityRoll && (
                <div className="rounded-md border border-ember/40 px-3 py-2 text-sm">
                  <span className="font-semibold text-ember">{abilities.find((a) => a.field === abilityRoll.ability)?.label}</span>: d20 {signed(abilityRoll.modifier)} = <span className="font-bold text-ember">{abilityRoll.total}</span>
                </div>
              )}
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {abilities.map((ability) => (
                <AbilityCard key={ability.short} {...ability} onRoll={() => rollAbility(ability.field)} />
              ))}
            </div>
          </section>

          <section className="panel p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-ember">Спасброски</h2>
              {savingThrowRoll && (
                <div className="rounded-md border border-ember/40 px-3 py-2 text-sm">
                  <span className="font-semibold text-ember">{abilities.find((a) => a.field === savingThrowRoll.ability)?.label}</span>: d20 {signed(savingThrowRoll.bonus)} = <span className="font-bold text-ember">{savingThrowRoll.total}</span>
                </div>
              )}
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {abilities.map((ability) => (
                <SavingThrowCard
                  key={ability.short}
                  label={ability.label}
                  short={ability.short}
                  value={ability.value}
                  proficient={(character.saving_throw_proficiencies ?? []).includes(ability.field)}
                  proficiencyBonus={proficiencyBonus(character.level)}
                  onRoll={() => rollSavingThrow(ability.field)}
                />
              ))}
            </div>
          </section>

          <section className="panel p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Swords size={18} className="text-ember" />
                <h2 className="text-lg font-semibold text-ember">Атаки</h2>
              </div>
              {attackRoll && (
                <div className="rounded-md border border-ember/40 px-3 py-2 text-sm">
                  <span className="font-semibold text-ember">{attackRoll.name}</span>: d20 {signed(attackRoll.bonus)} = {attackRoll.total}
                </div>
              )}
              {damageRoll && (
                <div className="rounded-md border border-amber-400/40 px-3 py-2 text-sm">
                  <span className="font-semibold text-amber-300">{damageRoll.name}</span>: [{damageRoll.rolls.join(", ")}]{damageRoll.modifier !== 0 ? ` ${signed(damageRoll.modifier)}` : ""} = <span className="font-bold text-amber-300">{damageRoll.total}</span>
                </div>
              )}
            </div>
            <form className="mt-4 grid gap-3 md:grid-cols-[1fr_120px_1fr_auto]" onSubmit={createAttack}>
              <input className="field" placeholder="Название атаки" value={attackForm.name} onChange={(event) => setAttackForm({ ...attackForm, name: event.target.value })} />
              <input className="field" type="number" value={attackForm.attack_bonus} onChange={(event) => setAttackForm({ ...attackForm, attack_bonus: Number(event.target.value) })} />
              <input className="field" placeholder="Урон, например 1d8+3 рубящий" value={attackForm.damage} onChange={(event) => setAttackForm({ ...attackForm, damage: event.target.value })} />
              <button className="btn" disabled={!attackForm.name.trim()} type="submit"><Plus size={16} />Добавить</button>
            </form>
            {attackError && <p className="mt-3 text-sm text-red-300">{attackError}</p>}
            <div className="mt-4 space-y-3">
              {attacks.map((attack) => (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-white/10 px-3 py-3" key={attack.id}>
                  <div>
                    <div className="font-semibold">{attack.name}</div>
                    <div className="text-sm text-white/60">Попадание: {signed(attack.attack_bonus)} · Урон: {attack.damage || "-"}</div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button className="btn-secondary" onClick={() => rollAttack(attack)}><Dice5 size={16} />Бросить атаку</button>
                    {attack.damage && <button className="btn-secondary" onClick={() => rollDamage(attack)}><Dice5 size={16} />Бросить урон</button>}
                    <button className="btn-secondary" onClick={() => removeAttack(attack)}><Trash2 size={16} />Удалить</button>
                  </div>
                </div>
              ))}
              {attacks.length === 0 && <p className="text-sm text-white/55">Атаки пока не добавлены.</p>}
            </div>
          </section>
        </div>

        <InventoryPanel inventory={inventory} onChange={setInventory} characterId={id} transferTargets={transferTargets} />
      </div>
    </div>
  );
}

function AbilityCard({ label, short, value, onRoll }: { label: string; short: string; value: number; onRoll?: () => void }) {
  const modifier = abilityModifier(value);
  return (
    <button
      className="ability-card text-left w-full"
      onClick={onRoll}
      title={onRoll ? `Бросить d20 + ${signed(modifier)}` : undefined}
      type="button"
    >
      <div>
        <p className="text-xs uppercase text-white/45">{short}</p>
        <h3 className="font-semibold text-ember">{label}</h3>
      </div>
      <div className="text-right">
        <div className="text-3xl font-bold">{value}</div>
        <div className="text-lg font-semibold text-white/75">{signed(modifier)}</div>
      </div>
    </button>
  );
}

function SavingThrowCard({ label, short, value, proficient, proficiencyBonus: bonus, onRoll }: { label: string; short: string; value: number; proficient: boolean; proficiencyBonus: number; onRoll?: () => void }) {
  const modifier = abilityModifier(value) + (proficient ? bonus : 0);
  return (
    <button
      className="ability-card text-left w-full"
      onClick={onRoll}
      title={onRoll ? `Спасбросок d20 + ${signed(modifier)}` : undefined}
      type="button"
    >
      <div>
        <p className="text-xs uppercase text-white/45">{short}</p>
        <h3 className="font-semibold text-ember">{label}</h3>
        {proficient && <p className="text-xs text-emerald-200">Владение спасброском</p>}
      </div>
      <div className="text-right">
        <div className="text-lg font-semibold text-white/75">{signed(modifier)}</div>
      </div>
    </button>
  );
}

function SkillsPanel({ character, onChange }: { character: Character; onChange: (character: Character) => void }) {
  const proficiencies = character.skill_proficiencies ?? [];
  const expertise = character.skill_expertise ?? [];
  const bonus = proficiencyBonus(character.level);
  const [error, setError] = useState("");
  const [skillRoll, setSkillRoll] = useState<SkillRoll | null>(null);

  async function rollSkill(skill: string) {
    setError("");
    try {
      const response = await api.post<SkillRoll>(`/characters/${character.id}/roll-skill/${skill}`);
      setSkillRoll(response.data);
    } catch (rollError) {
      setError(apiErrorDetail(rollError, "Не удалось выполнить бросок навыка"));
    }
  }

  async function save(nextProficiencies: string[], nextExpertise: string[]) {
    setError("");
    try {
      const response = await api.patch<Character>(`/characters/${character.id}`, {
        skill_proficiencies: nextProficiencies,
        skill_expertise: nextExpertise
      });
      onChange(response.data);
    } catch (saveError) {
      setError(apiErrorDetail(saveError, "Не удалось сохранить навыки"));
    }
  }

  return (
    <section className="panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-ember">Навыки</h2>
        {skillRoll ? (
          <span className="rounded-md border border-ember/40 px-3 py-2 text-sm">
            <span className="font-semibold text-ember">{skills.find((skill) => skill.key === skillRoll.skill)?.label}</span>: d20 {signed(skillRoll.modifier)} = <span className="font-bold text-ember">{skillRoll.total}</span>
          </span>
        ) : <span className="text-sm text-white/60">Бонус мастерства {signed(bonus)}</span>}
      </div>
      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
      <div className="mt-4 grid gap-2 lg:grid-cols-2">
        {skills.map((skill) => {
          const proficient = proficiencies.includes(skill.key);
          const expert = expertise.includes(skill.key);
          const score = character[skill.ability];
          const value = abilityModifier(score) + (expert ? bonus * 2 : proficient ? bonus : 0);
          return (
            <div className="grid grid-cols-[minmax(0,1fr)_auto_auto_auto] items-center gap-3 rounded-md border border-white/10 px-3 py-2" key={skill.key}>
              <button className="flex min-w-0 items-center justify-between gap-3 rounded-sm text-left transition hover:text-ember focus-visible:outline focus-visible:outline-2 focus-visible:outline-ember" type="button" onClick={() => rollSkill(skill.key)} aria-label={`Бросить навык ${skill.label} ${signed(value)}`}>
                <span>{skill.label}</span>
                <strong className="text-ember">{signed(value)}</strong>
              </button>
              <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={proficient} onChange={(event) => {
                const nextProficiencies = event.target.checked ? [...proficiencies, skill.key] : proficiencies.filter((key) => key !== skill.key);
                const nextExpertise = event.target.checked ? expertise : expertise.filter((key) => key !== skill.key);
                save(nextProficiencies, nextExpertise);
              }} />Владение</label>
              <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={expert} disabled={!proficient} onChange={(event) => {
                const nextExpertise = event.target.checked ? [...expertise, skill.key] : expertise.filter((key) => key !== skill.key);
                save(proficiencies, nextExpertise);
              }} />Компетентность</label>
            </div>
          );
        })}
      </div>
    </section>
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
        const payload: Record<string, string | number | string[] | Character["class_levels"] | undefined> = {
          class_name: form.class_name,
          class_levels: form.class_levels,
          saving_throw_proficiencies: form.saving_throw_proficiencies
        };
        textFields.forEach(({ field }) => {
          payload[field] = form[field];
        });
        numberFields
          .filter(({ field }) => field !== "level")
          .forEach(({ field }) => {
            payload[field] = form[field];
          });
        await api.patch(`/characters/${id}`, payload);
        navigate(`/characters/${id}`);
      } else {
        await api.post("/characters", form);
        navigate("/characters");
      }
    } catch (error) {
      setError(apiErrorDetail(error, "Не удалось сохранить персонажа"));
    }
  }

  return (
    <form className="panel grid gap-3 p-5 md:grid-cols-2" onSubmit={submit}>
      <h1 className="text-xl font-bold text-ember md:col-span-2">{edit ? "Редактировать персонажа" : "Создать персонажа"}</h1>
      <ClassLevelsEditor
        classLevels={form.class_levels}
        onChange={(classLevels) => setForm({
          ...form,
          class_name: classLevels[0].class_name,
          class_levels: classLevels,
          level: classLevels.reduce((total, entry) => total + entry.level, 0)
        })}
      />
      <label className="field-label md:col-span-2">
        <span>📅 Дата создания персонажа</span>
        <input
          className="field"
          type="date"
          min={GAME_EPOCH}
          value={form.game_created_at ?? GAME_EPOCH}
          disabled={edit}
          onChange={(event) => setForm({ ...form, game_created_at: event.target.value })}
        />
        <span className="text-xs text-white/45">
          {edit
            ? "Дату создания нельзя изменить после создания персонажа."
            : `Начало игрового мира — ${formatGameDate(GAME_EPOCH)}. Эта дата используется для подсчёта свободных дней.`}
        </span>
      </label>
      {textFields.map(({ field, label }) => (
        <label className="field-label" key={field}>
          <span>{label}</span>
          <input className="field" value={form[field]} onChange={(event) => setForm({ ...form, [field]: event.target.value })} />
        </label>
      ))}
      {(edit ? numberFields.filter(({ field }) => field !== "level") : numberFields).map(({ field, label }) => (
        <label className="field-label" key={field}>
          <span>{label}</span>
          <input className="field" type="number" value={form[field]} onChange={(event) => setForm({ ...form, [field]: Number(event.target.value) })} />
        </label>
      ))}
      <div className="md:col-span-2 grid gap-2 rounded-md border border-white/10 p-3 sm:grid-cols-2 lg:grid-cols-3">
        <span className="text-sm font-semibold text-ember sm:col-span-2 lg:col-span-3">Владение спасбросками</span>
        {abilityDefinitions.map((ability) => (
          <label className="flex items-center gap-2 text-sm" key={ability.field}>
            <input
              type="checkbox"
              checked={form.saving_throw_proficiencies.includes(ability.field)}
              onChange={(event) => setForm({
                ...form,
                saving_throw_proficiencies: event.target.checked
                  ? [...form.saving_throw_proficiencies, ability.field]
                  : form.saving_throw_proficiencies.filter((field) => field !== ability.field)
              })}
            />
            Владение спасброском: {ability.label}
          </label>
        ))}
      </div>
      {error && <p className="text-sm text-red-300 md:col-span-2">{error}</p>}
      <button className="btn md:col-span-2" type="submit">Сохранить</button>
    </form>
  );
}

function ClassLevelsEditor({ classLevels, onChange }: {
  classLevels: Character["class_levels"];
  onChange: (classLevels: Character["class_levels"]) => void;
}) {
  const levels = classLevels.length ? classLevels : [{ class_name: defaultCharacterClass, level: 1 }];
  const totalLevel = levels.reduce((total, entry) => total + entry.level, 0);
  return (
    <fieldset className="md:col-span-2 rounded-md border border-white/10 p-3">
      <legend className="px-2 text-sm font-semibold text-ember">Дополнительные классы</legend>
      <p className="mb-3 text-sm text-white/55">Первый класс — основной. Общий уровень: {totalLevel}</p>
      <div className="space-y-2">
        {levels.map((entry, index) => (
          <div className="grid gap-2 sm:grid-cols-[1fr_120px_auto]" key={`${index}-${entry.class_name}`}>
            <ClassSelect value={entry.class_name} onChange={(value) => onChange(levels.map((item, itemIndex) => itemIndex === index ? { ...item, class_name: value } : item))} />
            <label className="field-label"><span>Уровень класса</span><input className="field" min={1} max={20} type="number" value={entry.level} onChange={(event) => onChange(levels.map((item, itemIndex) => itemIndex === index ? { ...item, level: Number(event.target.value) } : item))} /></label>
            {index > 0 && <button className="btn-secondary self-end" type="button" onClick={() => onChange(levels.filter((_, itemIndex) => itemIndex !== index))}><Trash2 size={16} />Удалить</button>}
          </div>
        ))}
      </div>
      <button className="btn-secondary mt-3" type="button" onClick={() => onChange([...levels, { class_name: defaultCharacterClass, level: 1 }])}><Plus size={16} />Добавить класс</button>
    </fieldset>
  );
}

function InventoryPanel({ inventory, onChange, characterId, transferTargets }: { inventory: Inventory | null; onChange: (inventory: Inventory) => void; characterId: number; transferTargets: TransferTarget[] }) {
  const recipients = transferTargets.filter((character) => character.id !== characterId);
  const [currencyTransfer, setCurrencyTransfer] = useState({ recipient_character_id: "", gold: 0, silver: 0, copper: 0 });
  const [itemRecipients, setItemRecipients] = useState<Record<number, string>>({});
  const [notesDraft, setNotesDraft] = useState("");
  const [notesSaved, setNotesSaved] = useState(false);
  const [error, setError] = useState("");

  async function remove(item: InventoryItem) {
    const response = await api.delete<Inventory>(`/characters/${characterId}/inventory/items/${item.id}`);
    onChange(response.data);
  }

  async function transferCurrency(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const response = await api.post<Inventory>(`/characters/${characterId}/inventory/currency/transfer`, {
        ...currencyTransfer,
        recipient_character_id: Number(currencyTransfer.recipient_character_id)
      });
      onChange(response.data);
      setCurrencyTransfer({ recipient_character_id: currencyTransfer.recipient_character_id, gold: 0, silver: 0, copper: 0 });
    } catch (transferError) {
      setError(apiErrorDetail(transferError, "Не удалось передать валюту"));
    }
  }

  async function transferItem(item: InventoryItem) {
    const recipientId = itemRecipients[item.id];
    if (!recipientId) return;
    setError("");
    try {
      const response = await api.post<Inventory>(`/characters/${characterId}/inventory/items/transfer`, {
        recipient_character_id: Number(recipientId),
        item_id: item.id
      });
      onChange(response.data);
    } catch (transferError) {
      setError(apiErrorDetail(transferError, "Не удалось передать предмет"));
    }
  }

  async function saveNotes() {
    setError("");
    setNotesSaved(false);
    try {
      const response = await api.patch<Inventory>(`/characters/${characterId}/inventory/notes`, { notes: notesDraft });
      onChange(response.data);
      setNotesSaved(true);
    } catch (notesError) {
      setError(apiErrorDetail(notesError, "Не удалось сохранить заметки"));
    }
  }

  useEffect(() => {
    if (!currencyTransfer.recipient_character_id && recipients[0]) {
      setCurrencyTransfer((current) => ({ ...current, recipient_character_id: String(recipients[0].id) }));
    }
  }, [currencyTransfer.recipient_character_id, recipients]);

  useEffect(() => {
    setNotesDraft(inventory?.notes ?? "");
    setNotesSaved(false);
  }, [inventory?.id, inventory?.notes]);

  return (
    <aside className="panel p-5">
      <h2 className="text-lg font-semibold text-ember">Инвентарь</h2>
      <p className="mt-1 text-sm text-white/70">{inventory?.gold ?? 0} зол. / {inventory?.silver ?? 0} сер. / {inventory?.copper ?? 0} мед.</p>
      <div className="mt-4">
        <label className="field-label">
          <span>Заметки</span>
          <textarea className="field min-h-32 resize-y" value={notesDraft} onChange={(event) => {
            setNotesSaved(false);
            setNotesDraft(event.target.value);
          }} />
        </label>
        <div className="mt-2 flex items-center gap-3">
          <button className="btn-secondary" onClick={saveNotes}><Save size={16} />Сохранить заметки</button>
          {notesSaved && <span className="text-sm text-emerald-200">Сохранено</span>}
        </div>
      </div>
      <form className="mt-4 rounded-md border border-white/10 p-3" onSubmit={transferCurrency}>
        <h3 className="font-semibold text-ember">Передать валюту</h3>
        <div className="mt-3 grid grid-cols-3 gap-2">
          {(["gold", "silver", "copper"] as const).map((field) => (
            <input
              className="field"
              key={field}
              min={0}
              type="number"
              value={currencyTransfer[field]}
              onChange={(event) => setCurrencyTransfer({ ...currencyTransfer, [field]: Number(event.target.value) })}
            />
          ))}
        </div>
        <select className="field mt-2" value={currencyTransfer.recipient_character_id} onChange={(event) => setCurrencyTransfer({ ...currencyTransfer, recipient_character_id: event.target.value })}>
          {recipients.map((character) => <option key={character.id} value={character.id}>{character.name} · {character.owner_username}</option>)}
        </select>
        <button className="btn mt-2 w-full" disabled={!currencyTransfer.recipient_character_id}>Передать</button>
      </form>
      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
      <div className="mt-4 space-y-3">
        {inventory?.items.map((item) => (
          <div className="rounded-md border border-white/10 p-3" key={item.id}>
            <div className="font-semibold">{item.name}</div>
            <div className="text-sm text-white/60">{item.rarity} · {item.is_consumable ? "расходуемый" : "постоянный"}</div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link className="btn-secondary" to={`/shop?mode=sell&character=${characterId}&item=${item.id}`}>Продать</Link>
              <button className="btn-secondary" onClick={() => remove(item)}>Удалить</button>
              <select className="field min-w-0 flex-1" value={itemRecipients[item.id] ?? ""} onChange={(event) => setItemRecipients({ ...itemRecipients, [item.id]: event.target.value })}>
                <option value="">Кому передать</option>
                {recipients.map((character) => <option key={character.id} value={character.id}>{character.name} · {character.owner_username}</option>)}
              </select>
              <button className="btn-secondary" disabled={!itemRecipients[item.id]} onClick={() => transferItem(item)}>Передать</button>
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
  const [form, setForm] = useState({ magic_item_id: "", item_name: "", rarity: "Обычный", is_consumable: false, item_id: "", searcher_type: "paid_hireling", hireling_level: "Плохой" });
  const [magicItems, setMagicItems] = useState<MagicItem[]>([]);
  const [magicItemSearch, setMagicItemSearch] = useState("");
  const [magicItemRarity, setMagicItemRarity] = useState("");
  const [magicItemType, setMagicItemType] = useState("");
  const [magicItemsLoading, setMagicItemsLoading] = useState(false);
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

  useEffect(() => {
    if (mode !== "buy") return;

    const handle = window.setTimeout(() => {
      setMagicItemsLoading(true);
      api.get<MagicItem[]>("/shop/magic-items", {
        params: {
          search: magicItemSearch || undefined,
          rarity: magicItemRarity || undefined,
          item_type: magicItemType || undefined,
          limit: 100
        }
      })
        .then((response) => setMagicItems(response.data))
        .catch(() => setMagicItems([]))
        .finally(() => setMagicItemsLoading(false));
    }, 150);

    return () => window.clearTimeout(handle);
  }, [mode, magicItemSearch, magicItemRarity, magicItemType]);

  function selectMagicItem(itemId: string) {
    const item = magicItems.find((magicItem) => magicItem.id === itemId);
    if (!item) {
      setForm((current) => ({ ...current, magic_item_id: "" }));
      return;
    }

    setForm((current) => ({
      ...current,
      magic_item_id: item.id,
      item_name: item.name,
      rarity: item.rarity,
      is_consumable: item.is_consumable
    }));
  }

  async function performSearch() {
    setError("");
    try {
      const payload = mode === "buy"
        ? {
            mode,
            magic_item_id: form.magic_item_id || undefined,
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
    } catch (searchError) {
      setError(apiErrorDetail(searchError, "Поиск не выполнен"));
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
  const selectedMagicItem = magicItems.find((item) => item.id === form.magic_item_id);
  const canSearch = Boolean(characterId) && (mode === "buy" ? Boolean(form.magic_item_id || form.item_name.trim()) : Boolean(form.item_id));
  const paidHirelingSelected = form.searcher_type === "paid_hireling";

  function searcherDisabled(searcherType: SearcherType) {
    if (searcherType === "personal_hireling") return !selectedCharacter?.personal_hireling_enabled;
    if (searcherType === "simulacrum") return !selectedCharacter?.simulacrum_enabled;
    return false;
  }

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
              <span>Поиск в базе предметов</span>
              <input className="field" value={magicItemSearch} onChange={(event) => setMagicItemSearch(event.target.value)} />
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="field-label">
                <span>Фильтр редкости</span>
                <select className="field" value={magicItemRarity} onChange={(event) => setMagicItemRarity(event.target.value)}>
                  <option value="">Все</option>
                  {rarities.map((rarity) => <option key={rarity} value={rarity}>{rarity}</option>)}
                </select>
              </label>
              <label className="field-label">
                <span>Тип</span>
                <input className="field" value={magicItemType} onChange={(event) => setMagicItemType(event.target.value)} />
              </label>
            </div>
            <label className="field-label">
              <span>Предмет из базы</span>
              <select className="field min-h-48" size={8} value={form.magic_item_id} onChange={(event) => selectMagicItem(event.target.value)}>
                <option value="">Ручной ввод</option>
                {magicItems.map((item) => (
                  <option key={item.id} value={item.id}>{item.name} · {item.rarity} · {item.item_type}</option>
                ))}
              </select>
            </label>
            {magicItemsLoading && <p className="text-sm text-white/55">Загрузка предметов...</p>}
            {selectedMagicItem && (
              <div className="rounded-md border border-white/10 bg-black/25 p-3 text-sm text-white/70">
                <p className="font-semibold text-parchment">{selectedMagicItem.name}</p>
                <p>{selectedMagicItem.rarity} · {selectedMagicItem.item_type}{selectedMagicItem.is_consumable ? " · расходуемый" : ""}</p>
                {(selectedMagicItem.source || selectedMagicItem.page || selectedMagicItem.tier) && (
                  <p>
                    {[selectedMagicItem.source, selectedMagicItem.page ? `стр. ${selectedMagicItem.page}` : "", selectedMagicItem.tier].filter(Boolean).join(" · ")}
                  </p>
                )}
                {selectedMagicItem.entries[0] && <p className="mt-2 max-h-24 overflow-hidden text-white/60">{selectedMagicItem.entries[0]}</p>}
              </div>
            )}
            <label className="field-label">
              <span>Название предмета</span>
              <input className="field" value={form.item_name} onChange={(event) => setForm({ ...form, magic_item_id: "", item_name: event.target.value })} />
            </label>
            <label className="field-label">
              <span>Редкость</span>
              <select className="field" value={form.rarity} onChange={(event) => setForm({ ...form, magic_item_id: "", rarity: event.target.value })}>{rarities.map((rarity) => <option key={rarity}>{rarity}</option>)}</select>
            </label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_consumable} onChange={(event) => setForm({ ...form, magic_item_id: "", is_consumable: event.target.checked })} />Расходуемый</label>
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
          {searcherOptions.map((option) => (
            <button
              type="button"
              className={form.searcher_type === option.type ? "mode-tab-active" : "mode-tab"}
              disabled={searcherDisabled(option.type)}
              key={option.type}
              onClick={() => setForm({ ...form, searcher_type: option.type })}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {hirelings.map((hireling) => (
            <button
              className={form.hireling_level === hireling.level ? "hireling-option-active" : "hireling-option"}
              disabled={!paidHirelingSelected}
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

function MarketPage() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [characterId, setCharacterId] = useState("");
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [form, setForm] = useState({ item_name: "", gold: "" });
  const [lastSale, setLastSale] = useState<MarketSaleLog | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get<Character[]>("/characters")
      .then((response) => {
        setCharacters(response.data);
        setCharacterId(String(response.data[0]?.id ?? ""));
      })
      .catch((loadError) => setError(apiErrorDetail(loadError, "Не удалось загрузить персонажей")));
  }, []);

  useEffect(() => {
    if (!characterId) {
      setInventory(null);
      return;
    }
    setError("");
    api.get<Inventory>(`/characters/${characterId}/inventory`)
      .then((response) => setInventory(response.data))
      .catch((loadError) => setError(apiErrorDetail(loadError, "Не удалось загрузить баланс")));
  }, [characterId]);

  async function sell(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLastSale(null);
    setSubmitting(true);
    try {
      const response = await api.post<MarketSaleResult>(
        `/characters/${characterId}/market/sales`,
        { item_name: form.item_name, gold: Number(form.gold) },
      );
      setInventory(response.data.inventory);
      setLastSale(response.data.sale);
      setForm({ item_name: "", gold: "" });
    } catch (saleError) {
      setError(apiErrorDetail(saleError, "Не удалось выполнить продажу"));
    } finally {
      setSubmitting(false);
    }
  }

  const selectedCharacter = characters.find((character) => String(character.id) === characterId);
  return (
    <div className="mx-auto grid max-w-4xl gap-4 lg:grid-cols-[420px_1fr]">
      <form className="panel flex flex-col gap-4 p-5" onSubmit={sell}>
        <div>
          <h1 className="text-xl font-bold text-ember">Рынок</h1>
          <p className="mt-1 text-sm text-white/60">Быстрая продажа обычной добычи</p>
        </div>
        <label className="field-label">
          <span>Персонаж</span>
          <select className="field" required value={characterId} onChange={(event) => setCharacterId(event.target.value)}>
            <option value="">Выберите персонажа</option>
            {characters.map((character) => <option key={character.id} value={character.id}>{character.name}</option>)}
          </select>
        </label>
        <label className="field-label">
          <span>Наименование предмета</span>
          <input className="field" required maxLength={255} placeholder="Например, длинный меч" value={form.item_name} onChange={(event) => setForm({ ...form, item_name: event.target.value })} />
        </label>
        <label className="field-label">
          <span>Полученная сумма, зм</span>
          <input className="field" required type="number" min="1" step="1" value={form.gold} onChange={(event) => setForm({ ...form, gold: event.target.value })} />
        </label>
        <button className="btn" disabled={submitting || !characterId || !form.item_name.trim() || Number(form.gold) <= 0}>
          <Coins size={17} />{submitting ? "Продажа..." : "Продать предмет"}
        </button>
        {error && <p className="text-sm text-red-300">{error}</p>}
      </form>
      <section className="panel p-5">
        <h2 className="text-lg font-semibold text-ember">Баланс персонажа</h2>
        {selectedCharacter ? (
          <>
            <p className="mt-3 text-white/65">{selectedCharacter.name}</p>
            <p className="mt-2 text-2xl font-bold">{inventory?.gold ?? 0} зм</p>
            <p className="mt-1 text-sm text-white/55">{inventory?.silver ?? 0} см · {inventory?.copper ?? 0} мм</p>
          </>
        ) : <p className="mt-3 text-sm text-white/55">Создайте персонажа, чтобы воспользоваться рынком.</p>}
        {lastSale && (
          <div className="mt-6 rounded-md border border-emerald-400/30 bg-emerald-950/25 p-4 text-sm text-emerald-100">
            <p className="font-semibold">Продажа записана</p>
            <p className="mt-1">{lastSale.item_name}: +{lastSale.gold} зм</p>
          </div>
        )}
        <p className="mt-6 text-sm text-white/55">Каждая операция сохраняется в журнале для проверки администрацией.</p>
      </section>
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
          <p className="text-sm text-white/65">{result.item_name}</p>
        </div>
        {result.is_consumed && <span className="rounded-md border border-emerald-400/40 px-2 py-1 text-sm text-emerald-200">Сделка завершена</span>}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">
        <Stat label="Время поиска" value={`${result.days} дн.`} />
        {result.item_price !== null && <Stat label="Цена" value={`${result.item_price} зм`} />}
        {result.searcher_type === "paid_hireling" && <Stat label="Плата наёмнику" value={`${result.hireling_cost} зм`} />}
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
  const [purchases, setPurchases] = useState<KarmaPurchase[]>([]);
  useEffect(() => {
    if (user) api.get<KarmaPurchase[]>("/karma-shop/purchases").then((response) => setPurchases(response.data));
  }, [user]);
  if (loading || !user) return <p>Загрузка...</p>;
  return <div className="grid gap-4 md:grid-cols-2"><section className="panel p-5"><h1 className="text-xl font-bold text-ember">{user.username}</h1><p>{user.email}</p><p className="mt-2">Карма: {user.karma}</p></section><section className="panel p-5"><h2 className="text-xl font-bold text-ember">Открывашки</h2><div className="mt-4 space-y-2">{purchases.map((purchase) => <div className="rounded-md bg-black/25 p-3" key={purchase.id}><p className="font-semibold">{purchase.name}</p><p className="text-sm text-white/55">{purchase.purchase_type === "opener" ? "Открывашка" : "Товар"} · {purchase.cost} кармы</p></div>)}{!purchases.length && <p className="text-white/55">Покупок пока нет</p>}</div></section></div>;
}

function KarmaShopPage() {
  const { user, setUser } = useAuth();
  const [characters, setCharacters] = useState<Character[]>([]);
  const [characterId, setCharacterId] = useState("");
  const [xpAmount, setXpAmount] = useState(1);
  const [purchaseType, setPurchaseType] = useState<"item" | "opener">("opener");
  const [name, setName] = useState("");
  const [cost, setCost] = useState(1);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const resurrectionCharacters = characters.filter(
    (character) => character.is_dead && character.level <= 10
  );
  const resurrectionCharacter = resurrectionCharacters.find(
    (character) => String(character.id) === characterId
  );
  const resurrectionCost = resurrectionCharacter
    ? (resurrectionCharacter.level <= 5 ? 5 : 10)
    : null;
  const canAffordResurrection = resurrectionCost !== null
    && (user?.karma ?? 0) >= resurrectionCost;

  useEffect(() => {
    api.get<Character[]>("/characters").then((response) => {
      setCharacters(response.data);
      if (response.data[0]) setCharacterId(String(response.data[0].id));
    });
  }, []);

  async function execute(path: string, payload: object, success: string) {
    setError(""); setMessage("");
    try {
      const response = await api.post<KarmaPurchaseResult>(path, payload);
      if (user) setUser({ ...user, karma: response.data.remaining_karma });
      setMessage(success);
      const refreshed = await api.get<Character[]>("/characters");
      setCharacters(refreshed.data);
    } catch (purchaseError) {
      setError(apiErrorDetail(purchaseError, "Покупка не выполнена"));
    }
  }

  return <div className="space-y-4"><section className="panel p-5"><h1 className="text-2xl font-bold text-ember">Магазин Кармы</h1><p className="mt-2 text-white/70">Баланс: {user?.karma ?? 0} кармы</p>{message && <p className="mt-3 text-emerald-200">{message}</p>}{error && <p className="mt-3 text-red-300">{error}</p>}</section><div className="grid gap-4 lg:grid-cols-3"><section className="panel p-5"><h2 className="text-lg font-semibold text-ember">Покупка опыта</h2><p className="text-sm text-white/55">1 опыт = 5 кармы</p><select className="field mt-4" value={characterId} onChange={(event) => setCharacterId(event.target.value)}><option value="">Выберите персонажа</option>{characters.map((character) => <option key={character.id} value={character.id}>{character.name} · ур. {character.level}</option>)}</select><input className="field mt-3" min={1} type="number" value={xpAmount} onChange={(event) => setXpAmount(Number(event.target.value))} /><button className="btn mt-3" disabled={!characterId || xpAmount < 1} onClick={() => execute("/karma-shop/xp", { character_id: Number(characterId), amount: xpAmount }, `Куплено ${xpAmount} опыта`)}>Купить за {xpAmount * 5} кармы</button></section><section className="panel p-5"><h2 className="text-lg font-semibold text-ember">Специальная покупка</h2><select className="field mt-4" value={purchaseType} onChange={(event) => setPurchaseType(event.target.value as "item" | "opener")}><option value="opener">Открывашка</option><option value="item">Другой товар</option></select><input className="field mt-3" placeholder="Название" value={name} onChange={(event) => setName(event.target.value)} /><input className="field mt-3" min={1} type="number" value={cost} onChange={(event) => setCost(Number(event.target.value))} /><button className="btn mt-3" disabled={!name.trim() || cost < 1} onClick={() => execute("/karma-shop/purchases", { purchase_type: purchaseType, name, cost }, "Покупка сохранена")}>Купить за {cost} кармы</button></section><section className="panel p-5"><h2 className="text-lg font-semibold text-ember">Воскресить персонажа</h2><p className="text-sm text-white/55">1–5 уровень: 5 кармы · 6–10: 10 кармы · 11+: недоступно</p><select className="field mt-4" value={resurrectionCharacter ? characterId : ""} onChange={(event) => setCharacterId(event.target.value)}><option value="">Выберите погибшего персонажа</option>{resurrectionCharacters.map((character) => <option key={character.id} value={character.id}>{character.name} · ур. {character.level}</option>)}</select>{resurrectionCharacters.length === 0 && <p className="mt-3 text-sm text-white/55">Нет погибших персонажей доступного уровня.</p>}{resurrectionCost !== null && !canAffordResurrection && <p className="mt-3 text-sm text-red-300">Недостаточно кармы для воскрешения.</p>}<button className="btn mt-3" disabled={!resurrectionCharacter || !canAffordResurrection} onClick={() => execute("/karma-shop/resurrect", { character_id: Number(characterId) }, "Персонаж воскрешён")}>Воскресить за {resurrectionCost ?? "—"} кармы</button></section></div></div>;
}

function LeaderboardPage() {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);

  useEffect(() => {
    api.get<LeaderboardEntry[]>("/leaderboard").then((response) => setEntries(response.data));
  }, []);

  return (
    <section className="panel p-5">
      <div className="mb-5 flex items-center gap-2">
        <Trophy size={20} className="text-ember" />
        <h1 className="text-xl font-bold text-ember">Таблица лидеров</h1>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-sm">
          <thead className="text-xs uppercase text-white/45">
            <tr>
              <th className="py-2 pr-3">Место</th>
              <th className="py-2 pr-3">Пользователь</th>
              <th className="py-2 pr-3">Карма</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr className="border-t border-white/10" key={entry.id}>
                <td className="py-3 pr-3 font-semibold text-ember">{entry.rank}</td>
                <td className="py-3 pr-3">{entry.username}</td>
                <td className="py-3 pr-3">{entry.karma}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const CHAT_PAGE_SIZE = 50;
const RECRUITMENT_PAGE_SIZE_OPTIONS = [5, 10, 20, 50];

const blankRecruitment = {
  real_date: "",
  game_date: "",
  start_time: "18:00",
  duration: "4 часа",
  location: "",
  quest: "",
  notes: ""
};

function GameRecruitmentsPage() {
  const { user } = useAuth();
  const [recruitments, setRecruitments] = useState<GameRecruitment[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedCharacters, setSelectedCharacters] = useState<Record<number, string>>({});
  const [selectedApplications, setSelectedApplications] = useState<Record<number, number[]>>({});
  const [form, setForm] = useState(blankRecruitment);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [chatMessages, setChatMessages] = useState<Record<number, import("./api").RecruitmentMessage[]>>({});
  const [chatDrafts, setChatDrafts] = useState<Record<number, string>>({});
  const [chatHasOlder, setChatHasOlder] = useState<Record<number, boolean>>({});

  async function load() {
    setError("");
    try {
      const [recruitmentsResponse, charactersResponse] = await Promise.all([
        api.get<PaginatedResponse<GameRecruitment>>("/game-recruitments", { params: { page, page_size: pageSize } }),
        api.get<Character[]>("/characters")
      ]);
      setRecruitments(recruitmentsResponse.data.items);
      setTotal(recruitmentsResponse.data.total);
      setPages(recruitmentsResponse.data.pages);
      setCharacters(charactersResponse.data.filter((character) => !character.is_dead));
      setSelectedApplications(Object.fromEntries(recruitmentsResponse.data.items.map((row) => [
        row.id,
        row.applications.filter((application) => application.status === "selected").map((application) => application.id)
      ])));
    } catch (loadError) {
      setError(apiErrorDetail(loadError, "Не удалось загрузить наборы на игры"));
    }
  }

  useEffect(() => { load(); }, [page, pageSize]);

  async function loadChat(recruitmentId: number, beforeId?: number) {
    const response = await api.get<import("./api").RecruitmentMessage[]>(`/game-recruitments/${recruitmentId}/messages`, { params: { before_id: beforeId, limit: CHAT_PAGE_SIZE } });
    setChatMessages((current) => ({ ...current, [recruitmentId]: beforeId ? [...response.data, ...(current[recruitmentId] ?? [])] : response.data }));
    setChatHasOlder((current) => ({ ...current, [recruitmentId]: response.data.length === CHAT_PAGE_SIZE }));
  }

  async function sendChat(recruitmentId: number) {
    const content = (chatDrafts[recruitmentId] ?? "").trim();
    if (!content) return;
    const response = await api.post<import("./api").RecruitmentMessage>(`/game-recruitments/${recruitmentId}/messages`, { content });
    setChatMessages((current) => ({ ...current, [recruitmentId]: [...(current[recruitmentId] ?? []), response.data] }));
    setChatDrafts((current) => ({ ...current, [recruitmentId]: "" }));
  }

  async function deleteChatMessage(recruitmentId: number, messageId: number) {
    await api.delete(`/game-recruitments/${recruitmentId}/messages/${messageId}`);
    setChatMessages((current) => ({ ...current, [recruitmentId]: (current[recruitmentId] ?? []).filter((message) => message.id !== messageId) }));
  }

  async function createRecruitment(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/game-recruitments", form);
      setForm(blankRecruitment);
      setShowForm(false);
      await load();
    } catch (createError) {
      setError(apiErrorDetail(createError, "Не удалось опубликовать игру"));
    } finally {
      setBusy(false);
    }
  }

  async function apply(recruitmentId: number) {
    const characterId = Number(selectedCharacters[recruitmentId]);
    if (!characterId) return;
    setBusy(true);
    setError("");
    try {
      await api.post(`/game-recruitments/${recruitmentId}/applications`, { character_id: characterId });
      await load();
    } catch (applyError) {
      setError(apiErrorDetail(applyError, "Не удалось записаться на игру"));
    } finally {
      setBusy(false);
    }
  }

  function toggleApplication(recruitmentId: number, applicationId: number) {
    setSelectedApplications((current) => {
      const selected = new Set(current[recruitmentId] ?? []);
      selected.has(applicationId) ? selected.delete(applicationId) : selected.add(applicationId);
      return { ...current, [recruitmentId]: [...selected] };
    });
  }

  async function publishParticipants(recruitmentId: number) {
    const applicationIds = selectedApplications[recruitmentId] ?? [];
    if (!applicationIds.length) return;
    setBusy(true);
    setError("");
    try {
      await api.post(`/game-recruitments/${recruitmentId}/participants`, { application_ids: applicationIds });
      await load();
    } catch (selectionError) {
      setError(apiErrorDetail(selectionError, "Не удалось выбрать участников"));
    } finally {
      setBusy(false);
    }
  }

  async function changeRecruitmentStatus(recruitment: GameRecruitment) {
    setBusy(true);
    setError("");
    try {
      await api.patch(`/game-recruitments/${recruitment.id}/status`, {
        status: recruitment.status === "upcoming" ? "completed" : "upcoming"
      });
      await load();
    } catch (statusError) {
      setError(apiErrorDetail(statusError, "Не удалось изменить статус публикации"));
    } finally {
      setBusy(false);
    }
  }

  async function deleteRecruitment(recruitmentId: number) {
    if (!window.confirm("Удалить публикацию и все записи участников?")) return;
    setBusy(true);
    setError("");
    try {
      await api.delete(`/game-recruitments/${recruitmentId}`);
      if (recruitments.length === 1 && page > 1) setPage(page - 1);
      else await load();
    } catch (deleteError) {
      setError(apiErrorDetail(deleteError, "Не удалось удалить публикацию"));
    } finally {
      setBusy(false);
    }
  }

  const statusLabels = {
    not_applied: "Не записан",
    applied: "Записан",
    selected: "Выбран мастером"
  };

  return (
    <div className="space-y-5">
      <section className="panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-ember">Набор на игры</h1>
            <p className="mt-1 text-sm text-white/60">Предстоящие приключения и запись персонажей</p>
          </div>
          {user?.is_admin && <button className="btn" onClick={() => setShowForm((value) => !value)}><Plus size={16} />Создать игру</button>}
        </div>
        {showForm && (
          <form className="mt-5 grid gap-4 border-t border-white/10 pt-5 md:grid-cols-2" onSubmit={createRecruitment}>
            <label className="field-label"><span>Реальная дата</span><input required className="field" type="date" value={form.real_date} onChange={(event) => setForm({ ...form, real_date: event.target.value })} /></label>
            <label className="field-label"><span>Игровая дата</span><input required className="field" type="date" value={form.game_date} onChange={(event) => setForm({ ...form, game_date: event.target.value })} /></label>
            <label className="field-label"><span>Начало игры</span><input required className="field" type="time" value={form.start_time} onChange={(event) => setForm({ ...form, start_time: event.target.value })} /></label>
            <label className="field-label"><span>Примерная длительность</span><input required maxLength={100} className="field" value={form.duration} onChange={(event) => setForm({ ...form, duration: event.target.value })} /></label>
            <label className="field-label md:col-span-2"><span>Место действия</span><input required maxLength={300} className="field" value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} /></label>
            <label className="field-label md:col-span-2"><span>Задание</span><textarea required maxLength={2000} className="field min-h-24" value={form.quest} onChange={(event) => setForm({ ...form, quest: event.target.value })} /></label>
            <label className="field-label md:col-span-2"><span>Примечания</span><textarea maxLength={2000} className="field min-h-20" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
            <div className="flex gap-2 md:col-span-2"><button className="btn" disabled={busy}><Send size={16} />Опубликовать</button><button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>Отмена</button></div>
          </form>
        )}
        {error && <p className="mt-4 text-sm text-red-300">{error}</p>}
      </section>

      {recruitments.map((recruitment) => (
        <article className="panel overflow-hidden" key={recruitment.id}>
          <div className="border-b border-white/10 bg-black/20 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><p className="text-xs uppercase tracking-widest text-white/45">Мастер #{recruitment.author_username}</p><h2 className="mt-1 text-xl font-bold text-ember">{recruitment.quest}</h2></div>
              <div className="flex flex-wrap items-center gap-2">
                <span className={recruitment.status === "upcoming" ? "rounded-full bg-amber-500/20 px-3 py-1 text-sm text-amber-200" : "rounded-full bg-white/10 px-3 py-1 text-sm text-white/65"}>{recruitment.status === "upcoming" ? "Будет проведена" : "Проведена"}</span>
                <span className={recruitment.application_status === "selected" ? "rounded-full bg-green-500/20 px-3 py-1 text-sm text-green-200" : "rounded-full bg-white/10 px-3 py-1 text-sm"}>{statusLabels[recruitment.application_status]}</span>
                {recruitment.can_manage && <button className="btn-secondary" disabled={busy} onClick={() => changeRecruitmentStatus(recruitment)}>{recruitment.status === "upcoming" ? "Отметить проведённой" : "Вернуть в предстоящие"}</button>}
                {recruitment.can_manage && <button className="btn-secondary text-red-200" disabled={busy} onClick={() => deleteRecruitment(recruitment.id)}><Trash2 size={16} />Удалить</button>}
              </div>
            </div>
            <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div><span className="text-white/45">Дата</span><p>{formatGameDate(recruitment.real_date)}</p></div>
              <div><span className="text-white/45">Игровая дата</span><p>{formatGameDate(recruitment.game_date)}</p></div>
              <div><span className="text-white/45">Время</span><p>{recruitment.start_time.slice(0, 5)} · {recruitment.duration}</p></div>
              <div><span className="text-white/45">Место</span><p className="flex items-center gap-1"><MapPin size={14} />{recruitment.location}</p></div>
            </div>
            {recruitment.notes && <p className="mt-4 whitespace-pre-wrap rounded-md border border-white/10 p-3 text-sm text-white/70"><strong className="text-parchment">Примечания:</strong> {recruitment.notes}</p>}
          </div>
          <div className="grid gap-5 p-5 lg:grid-cols-2">
            <section>
              <h3 className="font-semibold text-ember">Желающие ({recruitment.applications.length})</h3>
              <div className="mt-3 space-y-2">
                {recruitment.applications.map((application) => (
                  <label className="flex items-center gap-3 rounded-md border border-white/10 p-3" key={application.id}>
                    {recruitment.can_manage && <input type="checkbox" checked={(selectedApplications[recruitment.id] ?? []).includes(application.id)} onChange={() => toggleApplication(recruitment.id, application.id)} />}
                    <span className="min-w-0 flex-1"><strong>#{application.username}</strong> — «{application.character_name}»<span className="block text-sm text-white/55">{application.class_name}, уровень {application.level}</span></span>
                    {application.status === "selected" && <Check size={18} className="text-green-300" />}
                  </label>
                ))}
                {!recruitment.applications.length && <p className="text-sm text-white/50">Пока никто не записался.</p>}
              </div>
              {recruitment.can_manage ? (
                <button className="btn mt-3" disabled={busy || !(selectedApplications[recruitment.id] ?? []).length} onClick={() => publishParticipants(recruitment.id)}><Check size={16} />Выдать выбранных игроков</button>
              ) : recruitment.status === "upcoming" && recruitment.application_status === "not_applied" ? (
                <div className="mt-3 flex flex-wrap gap-2"><select className="field max-w-sm" value={selectedCharacters[recruitment.id] ?? ""} onChange={(event) => setSelectedCharacters({ ...selectedCharacters, [recruitment.id]: event.target.value })}><option value="">Выберите персонажа</option>{characters.map((character) => <option key={character.id} value={character.id}>{character.name} · {character.class_name} · ур. {character.level}</option>)}</select><button className="btn" disabled={busy || !selectedCharacters[recruitment.id]} onClick={() => apply(recruitment.id)}>Записаться</button></div>
              ) : null}
            </section>
            <section>
              <div className="flex items-center justify-between"><h3 className="font-semibold text-ember">Чат публикации</h3>{!chatMessages[recruitment.id] && <button className="btn-secondary" onClick={() => loadChat(recruitment.id)}>Открыть чат</button>}</div>
              {chatMessages[recruitment.id] && <><div className="mt-3 max-h-80 space-y-2 overflow-y-auto rounded-md border border-white/10 p-3" onScroll={(event) => { if (event.currentTarget.scrollTop === 0 && chatHasOlder[recruitment.id]) loadChat(recruitment.id, chatMessages[recruitment.id][0]?.id); }}>
                {chatHasOlder[recruitment.id] && <p className="text-center text-xs text-white/40">Прокрутите вверх для старых сообщений</p>}
                {chatMessages[recruitment.id].map((message) => <div className="rounded-md bg-black/25 p-3" key={message.id}><div className="flex items-start justify-between gap-2"><p className="text-xs text-white/45">{message.is_system ? "Система" : `#${message.username}`}</p>{!message.is_system && (message.user_id === user?.id || user?.is_admin) && <button aria-label="Удалить сообщение" className="text-red-300" onClick={() => deleteChatMessage(recruitment.id, message.id)}><Trash2 size={14} /></button>}</div><p className="mt-1 whitespace-pre-wrap text-sm text-white/80">{message.content}</p><p className="mt-2 text-xs text-white/35">{new Date(message.created_at).toLocaleString("ru-RU")}</p></div>)}
                {!chatMessages[recruitment.id].length && <p className="text-sm text-white/50">Сообщений пока нет.</p>}
              </div><div className="mt-2 flex gap-2"><input maxLength={2000} className="field flex-1" placeholder="Сообщение" value={chatDrafts[recruitment.id] ?? ""} onChange={(event) => setChatDrafts((current) => ({ ...current, [recruitment.id]: event.target.value }))} onKeyDown={(event) => { if (event.key === "Enter") sendChat(recruitment.id); }} /><button className="btn" onClick={() => sendChat(recruitment.id)}><Send size={16} /></button></div></>}
            </section>
          </div>
        </article>
      ))}
      {!recruitments.length && <section className="panel p-8 text-center text-white/55">Опубликованных игр пока нет.</section>}
      <section className="panel p-4">
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-white/65">
          <span>Всего публикаций: {total}</span>
          <label className="flex items-center gap-2"><span>На странице</span><select className="field w-auto min-w-20" aria-label="Количество публикаций на странице" value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}>{RECRUITMENT_PAGE_SIZE_OPTIONS.map((option) => <option value={option} key={option}>{option}</option>)}</select></label>
          <div className="flex items-center gap-2"><button className="btn-secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Назад</button><span>Страница {page} из {Math.max(pages, 1)}</span><button className="btn-secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>Вперёд</button></div>
        </div>
      </section>
    </div>
  );
}

function ChatPage() {
  const { user } = useAuth();
  const [channel, setChannel] = useState<"general" | "rolls">("general");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const pendingScrollToBottom = useRef(false);

  async function loadMessages(nextChannel = channel) {
    pendingScrollToBottom.current = true;
    try {
      const response = await api.get<ChatMessage[]>("/chat/messages", {
        params: { channel: nextChannel, limit: CHAT_PAGE_SIZE }
      });
      setMessages(response.data);
      setHasMore(response.data.length === CHAT_PAGE_SIZE);
    } catch (loadError) {
      pendingScrollToBottom.current = false;
      setError(apiErrorDetail(loadError, "Не удалось загрузить чат"));
    }
  }

  useEffect(() => {
    setError("");
    setHasMore(false);
    loadMessages(channel);
  }, [channel]);

  useLayoutEffect(() => {
    // Only scroll once the freshly loaded messages have actually rendered.
    // The initial mount renders with an empty list, so guarding on
    // messages.length keeps the pending flag set until real content arrives
    // (otherwise the empty render would consume it and the view would stay
    // pinned at the oldest message).
    if (pendingScrollToBottom.current && listRef.current && messages.length > 0) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
      pendingScrollToBottom.current = false;
    }
  }, [messages, channel]);

  async function loadOlderMessages() {
    if (!messages.length) return;
    setLoadingMore(true);
    try {
      const oldestId = messages[0].id;
      const response = await api.get<ChatMessage[]>("/chat/messages", {
        params: { channel, limit: CHAT_PAGE_SIZE, before_id: oldestId }
      });
      const previousScrollHeight = listRef.current?.scrollHeight ?? 0;
      setMessages((current) => [...response.data, ...current]);
      setHasMore(response.data.length === CHAT_PAGE_SIZE);
      requestAnimationFrame(() => {
        if (listRef.current) {
          listRef.current.scrollTop = listRef.current.scrollHeight - previousScrollHeight;
        }
      });
    } catch (loadError) {
      setError(apiErrorDetail(loadError, "Не удалось загрузить сообщения"));
    } finally {
      setLoadingMore(false);
    }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const response = await api.post<ChatMessage>("/chat/messages", { content });
      setContent("");
      if (response.data.channel !== channel) {
        setChannel(response.data.channel);
      } else {
        setMessages((current) => [...current, response.data]);
        requestAnimationFrame(() => {
          if (listRef.current) {
            listRef.current.scrollTop = listRef.current.scrollHeight;
          }
        });
      }
    } catch (sendError) {
      setError(apiErrorDetail(sendError, "Не удалось отправить сообщение"));
    }
  }

  async function deleteMessage(messageId: number) {
    if (!window.confirm("Удалить сообщение?")) return;
    setError("");
    try {
      await api.delete(`/chat/messages/${messageId}`);
      setMessages((current) => current.filter((message) => message.id !== messageId));
    } catch (deleteError) {
      setError(apiErrorDetail(deleteError, "Не удалось удалить сообщение"));
    }
  }

  return (
    <section className="panel flex h-[calc(100vh-7rem)] flex-col p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <MessageSquare size={20} className="text-ember" />
          <h1 className="text-xl font-bold text-ember">Чат</h1>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button className={channel === "general" ? "mode-tab-active" : "mode-tab"} onClick={() => setChannel("general")}>Общий чат</button>
          <button className={channel === "rolls" ? "mode-tab-active" : "mode-tab"} onClick={() => setChannel("rolls")}>Броски</button>
        </div>
      </div>

      <div ref={listRef} className="mt-5 min-h-0 flex-1 space-y-3 overflow-y-auto rounded-md border border-white/10 p-3">
        {hasMore && (
          <div className="flex justify-center pb-2">
            <button className="btn-secondary" onClick={loadOlderMessages} disabled={loadingMore}>
              {loadingMore ? "Загрузка..." : "Загрузить ещё"}
            </button>
          </div>
        )}
        {messages.map((message) => (
          <article className="rounded-md bg-black/25 p-3" key={message.id}>
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="font-semibold text-ember">{message.username}</span>
              <span className="flex items-center gap-2 text-white/45">
                {new Date(message.created_at).toLocaleString("ru-RU")}
                {user?.is_admin && <button aria-label="Удалить сообщение" className="rounded p-1 text-red-200 hover:bg-red-400/15" type="button" onClick={() => deleteMessage(message.id)}><Trash2 size={15} /></button>}
              </span>
            </div>
            {message.channel === "rolls" ? (
              <div className="mt-2 text-sm text-white/80">
                <p className="whitespace-pre-wrap">{message.content}</p>
                {message.formula && (
                  <p className="mt-2 text-white/60">Формула: {message.formula} · Результаты: [{message.rolls?.join(", ")}] · Итого: {message.total}</p>
                )}
              </div>
            ) : (
              <p className="mt-2 whitespace-pre-wrap text-sm text-white/80">{message.content}</p>
            )}
          </article>
        ))}
        {messages.length === 0 && <p className="text-sm text-white/55">Сообщений пока нет.</p>}
      </div>

      <form className="mt-4 grid gap-2 md:grid-cols-[1fr_auto]" onSubmit={sendMessage}>
        <input className="field" placeholder={channel === "rolls" ? "/r 1d20" : "Сообщение или /r 2d6"} value={content} onChange={(event) => setContent(event.target.value)} />
        <button className="btn" disabled={!content.trim()}><Send size={16} />Отправить</button>
      </form>
      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
    </section>
  );
}

const ROLE_OPTIONS: UserRole[] = ["owner", "project_owner", "head_admin", "admin", "technician", "player"];

// Roles that a head administrator is allowed to assign. Owners may assign any
// lower role, while head admins cannot grant owner-level or head-admin roles.
const HEAD_ADMIN_ASSIGNABLE_ROLES: UserRole[] = ["admin", "technician", "player"];
const ADMIN_PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

interface PaginationControlsProps {
  page: number;
  pageSize: number;
  pages: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

function PaginationControls({ page, pageSize, pages, total, onPageChange, onPageSizeChange }: PaginationControlsProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-white/65">
      <span>Всего: {total}</span>
      <label className="flex items-center gap-2">
        <span>На странице</span>
        <select
          className="field w-auto min-w-20"
          aria-label="Количество записей на странице"
          value={pageSize}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
        >
          {ADMIN_PAGE_SIZE_OPTIONS.map((option) => <option value={option} key={option}>{option}</option>)}
        </select>
      </label>
      <div className="flex items-center gap-2">
        <button className="btn-secondary" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Назад</button>
        <span>Страница {page} из {Math.max(pages, 1)}</span>
        <button className="btn-secondary" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>Вперёд</button>
      </div>
    </div>
  );
}

function AdminPage() {
  const { user } = useAuth();
  const [characters, setCharacters] = useState<Character[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [selected, setSelected] = useState("");
  const [amount, setAmount] = useState(1);
  const [karmaUserId, setKarmaUserId] = useState("");
  const [karmaAmount, setKarmaAmount] = useState(1);
  const [item, setItem] = useState({ name: "", rarity: "Обычный", is_consumable: false });
  const [reason, setReason] = useState("");
  const [roleError, setRoleError] = useState("");
  const [characterPage, setCharacterPage] = useState(1);
  const [characterPageSize, setCharacterPageSize] = useState(20);
  const [characterTotal, setCharacterTotal] = useState(0);
  const [characterPages, setCharacterPages] = useState(0);
  const [userPage, setUserPage] = useState(1);
  const [userPageSize, setUserPageSize] = useState(20);
  const [userTotal, setUserTotal] = useState(0);
  const [userPages, setUserPages] = useState(0);
  const [collapsed, setCollapsed] = useState<Record<"master" | "character" | "karma" | "interface", boolean>>(() => {
    try {
      return { master: false, character: false, karma: false, interface: false, ...JSON.parse(localStorage.getItem("admin-panel-state") ?? "{}") };
    } catch {
      return { master: false, character: false, karma: false, interface: false };
    }
  });

  const selectedCharacter = useMemo(() => characters.find((character) => String(character.id) === selected), [characters, selected]);
  const selectedUser = useMemo(() => users.find((user) => String(user.id) === karmaUserId), [users, karmaUserId]);

  function load() {
    Promise.all([
      api.get<PaginatedResponse<Character>>("/admin/characters", { params: { page: characterPage, page_size: characterPageSize } }),
      api.get<PaginatedResponse<AdminUser>>("/admin/users", { params: { page: userPage, page_size: userPageSize } })
    ]).then(([characterResponse, userResponse]) => {
      setCharacters(characterResponse.data.items);
      setCharacterTotal(characterResponse.data.total);
      setCharacterPages(characterResponse.data.pages);
      if (characterResponse.data.pages > 0 && characterPage > characterResponse.data.pages) {
        setCharacterPage(characterResponse.data.pages);
      }
      setSelected((current) => characterResponse.data.items.some((character) => String(character.id) === current) ? current : "");
      setUsers(userResponse.data.items);
      setUserTotal(userResponse.data.total);
      setUserPages(userResponse.data.pages);
      if (userResponse.data.pages > 0 && userPage > userResponse.data.pages) {
        setUserPage(userResponse.data.pages);
      }
      setKarmaUserId((current) => userResponse.data.items.some((row) => String(row.id) === current) ? current : "");
    });
  }

  useEffect(load, [characterPage, characterPageSize, userPage, userPageSize]);

  async function action(path: string, body?: unknown) {
    const payload = body && typeof body === "object" ? body : {};
    await api.post(`/admin/characters/${selected}/${path}`, { ...payload, reason });
    load();
  }

  async function applyKarma() {
    await api.post(`/admin/users/${karmaUserId}/karma`, { amount: karmaAmount, reason });
    load();
  }

  async function changeRole(userId: number, role: UserRole) {
    setRoleError("");
    try {
      await api.post(`/admin/users/${userId}/role`, { role });
      load();
    } catch (error) {
      setRoleError(apiErrorDetail(error, "Не удалось изменить роль"));
    }
  }

  async function verifyEmail(userId: number) {
    await api.post(`/admin/users/${userId}/verify-email`);
    load();
  }

  const canManageRoles = Boolean(user?.is_owner || user?.is_head_admin);

  function togglePanel(panel: "master" | "character" | "karma" | "interface") {
    setCollapsed((current) => {
      const next = { ...current, [panel]: !current[panel] };
      localStorage.setItem("admin-panel-state", JSON.stringify(next));
      return next;
    });
  }

  function PanelToggle({ panel, label }: { panel: "master" | "character" | "karma" | "interface"; label: string }) {
    return (
      <button className="btn-secondary p-2" aria-label={`${collapsed[panel] ? "Развернуть" : "Свернуть"} панель «${label}»`} aria-expanded={!collapsed[panel]} onClick={() => togglePanel(panel)}>
        {collapsed[panel] ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
      </button>
    );
  }

  // Head admins may not touch owners or other head admins, and they may never
  // grant the owner or head-admin roles. Owners have unrestricted control.
  function canEditRole(row: AdminUser): boolean {
    if (row.id === user?.id) return false;
    if (user?.is_owner) return true;
    return !row.is_owner && !row.is_head_admin;
  }

  function roleOptionsFor(row: AdminUser): UserRole[] {
    const assignable = user?.is_owner ? ROLE_OPTIONS : HEAD_ADMIN_ASSIGNABLE_ROLES;
    // Always keep the row's current role visible in the dropdown, even when it
    // is one the current actor is not allowed to assign.
    return assignable.includes(row.role) ? assignable : [row.role, ...assignable];
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
      <div className="space-y-4">
        <section className="panel flex flex-col gap-3 p-5">
          <div className="flex items-center justify-between gap-3">
            <h1 className="text-xl font-bold text-ember">Админка мастера</h1>
            <div className="flex gap-2"><Link className="btn-secondary" to="/admin/grant-logs"><ScrollText size={16} />Журнал выдач</Link><PanelToggle panel="master" label="Админка мастера" /></div>
          </div>
          {!collapsed.master && <>
          <label className="field-label">
            <span>Персонаж</span>
            <select className="field" value={selected} onChange={(event) => setSelected(event.target.value)}>
              <option value="">Выберите персонажа</option>
              {characters.map((character) => <option value={character.id} key={character.id}>{character.name} · {character.owner_username}</option>)}
            </select>
          </label>
          <label className="field-label">
            <span>Изменение</span>
            <input className="field" type="number" value={amount} onChange={(event) => setAmount(Number(event.target.value))} />
          </label>
          <label className="field-label"><span>Причина выдачи</span><textarea className="field" required value={reason} onChange={(event) => setReason(event.target.value)} /></label>
          <button className="btn" disabled={!selected || !reason.trim()} onClick={() => action("xp", { amount })}>Применить XP</button>
          <button className="btn" disabled={!selected || !reason.trim()} onClick={() => action("gold", { amount })}>Применить золото</button>
          <button className="btn-secondary" disabled={!selected} onClick={() => action("revive")}>Воскресить персонажа</button>
          </>}
          <div className="mt-2 border-t border-white/10 pt-3">
            <div className="flex items-center justify-between gap-3"><h2 className="text-lg font-semibold text-ember">{selectedCharacter?.name ?? "Персонаж"}</h2><PanelToggle panel="character" label="Персонаж" /></div>
            {!collapsed.character && (
            <div className="mt-3 flex flex-col gap-3">
              <input className="field" placeholder="название" value={item.name} onChange={(event) => setItem({ ...item, name: event.target.value })} />
              <select className="field" value={item.rarity} onChange={(event) => setItem({ ...item, rarity: event.target.value })}>{rarities.map((rarity) => <option key={rarity}>{rarity}</option>)}</select>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={item.is_consumable} onChange={(event) => setItem({ ...item, is_consumable: event.target.checked })} />Расходуемый</label>
              <button className="btn" disabled={!selected || !reason.trim()} onClick={() => action("item", item)}>Выдать предмет</button>
            </div>
            )}
          </div>
        </section>
        <section className="panel flex flex-col gap-3 p-5">
          <div className="flex items-center justify-between gap-3"><h2 className="text-lg font-semibold text-ember">Карма игроков</h2><PanelToggle panel="karma" label="Карма игроков" /></div>
          {!collapsed.karma && <>
          <label className="field-label">
            <span>Игрок</span>
            <select className="field" value={karmaUserId} onChange={(event) => setKarmaUserId(event.target.value)}>
              <option value="">Выберите пользователя</option>
              {users.map((user) => <option value={user.id} key={user.id}>{user.username} · {user.karma} кармы</option>)}
            </select>
          </label>
          <label className="field-label">
            <span>Изменение кармы</span>
            <input className="field" type="number" value={karmaAmount} onChange={(event) => setKarmaAmount(Number(event.target.value))} />
          </label>
          <p className="text-sm text-white/65">{selectedUser?.username ?? "Игрок"}: {selectedUser?.karma ?? 0}</p>
          <label className="field-label"><span>Причина выдачи</span><textarea className="field" required value={reason} onChange={(event) => setReason(event.target.value)} /></label>
          <button className="btn" disabled={!karmaUserId || !reason.trim()} onClick={applyKarma}>Применить</button>
          </>}
        </section>
        {canManageRoles && (
          <section className="panel flex flex-col gap-3 p-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2"><Shield size={18} className="text-ember" /><h2 className="text-lg font-semibold text-ember">Интерфейс</h2></div>
              <PanelToggle panel="interface" label="Интерфейс" />
            </div>
            {!collapsed.interface && <>
            <h3 className="font-semibold text-ember">Роли пользователей</h3>
            <p className="text-sm text-white/55">
              {user?.is_owner
                ? "Назначайте роли. Доступно только владельцу и главному администратору."
                : "Главный администратор управляет ролями мастеров, техников и игроков. Роли владельцев недоступны."}
            </p>
            <div className="flex flex-col gap-2">
              {users.map((row) => (
                <div className="flex items-center justify-between gap-2 rounded-md bg-black/25 px-3 py-2" key={row.id}>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-ember">{row.username}</div>
                    <div className="truncate text-xs text-white/55">{row.email}</div>
                    <div className={`text-xs ${row.email_verified ? "text-green-300" : "text-red-300"}`}>{row.email_verified ? "✅ Подтверждён" : "❌ Не подтверждён"}</div>
                  </div>
                  {!row.email_verified && <button className="btn-secondary" type="button" onClick={() => verifyEmail(row.id)}>Подтвердить</button>}
                  <select
                    className="field max-w-[220px]"
                    value={row.role}
                    disabled={!canEditRole(row)}
                    onChange={(event) => changeRole(row.id, event.target.value as UserRole)}
                  >
                    {roleOptionsFor(row).map((role) => (
                      <option value={role} key={role}>{ROLE_LABELS[role]}</option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
            <PaginationControls
              page={userPage}
              pageSize={userPageSize}
              pages={userPages}
              total={userTotal}
              onPageChange={setUserPage}
              onPageSizeChange={(value) => { setUserPageSize(value); setUserPage(1); }}
            />
            {roleError && <p className="text-sm text-red-300">{roleError}</p>}
            </>}
          </section>
        )}
      </div>
      <section className="panel p-5">
        <h2 className="text-lg font-semibold text-ember">Все персонажи</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[960px] text-left text-sm">
            <thead className="text-xs uppercase text-white/45">
              <tr>
                <th className="py-2 pr-3">Имя</th>
                <th className="py-2 pr-3">Владелец</th>
                <th className="py-2 pr-3">Уровень</th>
                <th className="py-2 pr-3">Дата сбора</th>
                <th className="py-2 pr-3">Свободные дни</th>
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
                  <td className="py-3 pr-3">{formatGameDate(character.game_created_at)}</td>
                  <td className="py-3 pr-3">{character.free_days ?? "-"}</td>
                  <td className="py-3 pr-3">{character.race || "-"}</td>
                  <td className="py-3 pr-3">{character.subclass || "-"}</td>
                  <td className="py-3 pr-3">{character.route || "-"}</td>
                  <td className="py-3 pr-3"><Link className="btn-secondary" to={`/admin/characters/${character.id}`}>Открыть</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 border-t border-white/10 pt-4">
          <PaginationControls
            page={characterPage}
            pageSize={characterPageSize}
            pages={characterPages}
            total={characterTotal}
            onPageChange={setCharacterPage}
            onPageSizeChange={(value) => { setCharacterPageSize(value); setCharacterPage(1); }}
          />
        </div>
      </section>
    </div>
  );
}

function AdminCharacterPage() {
  const { id: idParam } = useParams();
  const id = Number(idParam);
  const [character, setCharacter] = useState<Character | null>(null);
  const [form, setForm] = useState<Character | null>(null);
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const navigate = useNavigate();
  const { user } = useAuth();
  const canDeleteCharacter = Boolean(user?.is_owner || user?.is_head_admin);

  function load() {
    Promise.all([
      api.get<Character>(`/admin/characters/${id}`),
      api.get<Inventory>(`/admin/characters/${id}/inventory`)
    ]).then(([characterResponse, inventoryResponse]) => {
      setCharacter(characterResponse.data);
      setForm(characterResponse.data);
      setInventory(inventoryResponse.data);
    });
  }

  useEffect(load, [id]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setError("");
    setSaved(false);

    const payload: Record<string, string | number | boolean | string[] | Character["class_levels"] | undefined> = {
      class_name: form.class_name,
      class_levels: form.class_levels
    };
    textFields.forEach(({ field }) => {
      payload[field] = form[field];
    });
    adminNumberFields.forEach(({ field }) => {
      payload[field] = form[field] ?? 0;
    });
    adminUnitDateFields.forEach(({ field }) => {
      payload[field] = form[field] ?? GAME_EPOCH;
    });
    payload.personal_hireling_enabled = form.personal_hireling_enabled ?? false;
    payload.simulacrum_enabled = form.simulacrum_enabled ?? false;
    payload.is_dead = form.is_dead ?? false;
    payload.saving_throw_proficiencies = form.saving_throw_proficiencies ?? [];

    try {
      const response = await api.patch<Character>(`/admin/characters/${id}`, payload);
      setCharacter(response.data);
      setForm(response.data);
      setSaved(true);
    } catch (saveError) {
      setError(apiErrorDetail(saveError, "Не удалось сохранить персонажа"));
    }
  }

  async function deleteCharacter() {
    setError("");
    try {
      await api.delete(`/admin/characters/${id}`, {
        params: { confirmation: deleteConfirmation }
      });
      navigate("/admin");
    } catch (deleteError) {
      setError(apiErrorDetail(deleteError, "Не удалось удалить персонажа"));
    }
  }

  if (!character || !form) return <p>Загрузка...</p>;
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
        <form className="grid gap-3 md:grid-cols-2" onSubmit={save}>
          <ClassLevelsEditor
            classLevels={form.class_levels}
            onChange={(classLevels) => {
              setSaved(false);
              setForm({
                ...form,
                class_name: classLevels[0].class_name,
                class_levels: classLevels,
                level: classLevels.reduce((total, entry) => total + entry.level, 0)
              });
            }}
          />
          {textFields.map(({ field, label }) => (
            <label className="field-label" key={field}>
              <span>{label}</span>
              <input
                className="field"
                value={form[field]}
                onChange={(event) => {
                  setSaved(false);
                  setForm({ ...form, [field]: event.target.value });
                }}
              />
            </label>
          ))}
          {adminNumberFields.map(({ field, label }) => (
            <label className="field-label" key={field}>
              <span>{label}</span>
              <input
                className="field"
                type="number"
                value={form[field] ?? 0}
                onChange={(event) => {
                  setSaved(false);
                  setForm({ ...form, [field]: Number(event.target.value) });
                }}
              />
            </label>
          ))}
          <div className="md:col-span-2 grid gap-2 rounded-md border border-white/10 p-3 sm:grid-cols-2 lg:grid-cols-3">
            <span className="text-sm font-semibold text-ember sm:col-span-2 lg:col-span-3">Владение спасбросками</span>
            {abilityDefinitions.map((ability) => (
              <label className="flex items-center gap-2 text-sm" key={ability.field}>
                <input
                  type="checkbox"
                  checked={(form.saving_throw_proficiencies ?? []).includes(ability.field)}
                  onChange={(event) => {
                    const current = form.saving_throw_proficiencies ?? [];
                    setSaved(false);
                    setForm({
                      ...form,
                      saving_throw_proficiencies: event.target.checked
                        ? [...current, ability.field]
                        : current.filter((field) => field !== ability.field)
                    });
                  }}
                />
                Владение спасброском: {ability.label}
              </label>
            ))}
          </div>
          <div className="md:col-span-2 grid gap-3 rounded-md border border-white/10 p-3 md:grid-cols-2">
            <label className="flex items-center gap-2 text-sm md:col-span-2">
              <input
                type="checkbox"
                checked={Boolean(form.is_dead)}
                onChange={(event) => {
                  setSaved(false);
                  setForm({ ...form, is_dead: event.target.checked });
                }}
              />
              Смерть
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={Boolean(form.personal_hireling_enabled)}
                onChange={(event) => {
                  setSaved(false);
                  setForm({ ...form, personal_hireling_enabled: event.target.checked });
                }}
              />
              Личный наёмник
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={Boolean(form.simulacrum_enabled)}
                onChange={(event) => {
                  setSaved(false);
                  setForm({ ...form, simulacrum_enabled: event.target.checked });
                }}
              />
              Симулякр
            </label>
            {adminUnitDateFields.map(({ field, label }) => (
              <label className="field-label" key={field}>
                <span>{label}</span>
                <input
                  className="field"
                  min={GAME_EPOCH}
                  type="date"
                  value={form[field] ?? GAME_EPOCH}
                  onChange={(event) => {
                    setSaved(false);
                    setForm({ ...form, [field]: event.target.value });
                  }}
                />
              </label>
            ))}
          </div>
          {error && <p className="text-sm text-red-300 md:col-span-2">{error}</p>}
          {saved && <p className="text-sm text-emerald-200 md:col-span-2">Сохранено</p>}
          <button className="btn md:col-span-2" type="submit"><Save size={16} />Сохранить изменения</button>
        </form>
        <dl className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Уровень" value={character.level} />
          <Stat label="XP" value={character.xp} />
          <Stat label="Смерть" value={character.is_dead ? "Да" : "Нет"} />
          <Stat label="HP" value={character.hp} />
          <Stat label="КД" value={character.armor_class} />
          <Stat label="Дата сбора" value={formatGameDate(character.game_created_at)} />
          <Stat label="Свободные дни" value={character.free_days ?? 0} />
          <Stat label="Личный наёмник" value={character.personal_hireling_enabled ? `${character.personal_hireling_free_days ?? 0} дн.` : "-"} />
          <Stat label="Симулякр" value={character.simulacrum_enabled ? `${character.simulacrum_free_days ?? 0} дн.` : "-"} />
          {stats.map((stat) => <Stat key={stat.field} label={stat.label} value={character[stat.field]} />)}
        </dl>
        <div className="mt-5">
          <CalendarPanel characterId={id} />
        </div>
        {character.personal_hireling_enabled && (
          <div className="mt-5">
            <CalendarPanel
              characterId={id}
              agentType="personal_hireling"
              title="Календарь личного наёмника"
            />
          </div>
        )}
        {character.simulacrum_enabled && (
          <div className="mt-5">
            <CalendarPanel
              characterId={id}
              agentType="simulacrum"
              title="Календарь симулякра"
            />
          </div>
        )}
        {canDeleteCharacter && <div className="mt-5 rounded-md border border-red-400/30 p-4">
          <h2 className="font-semibold text-red-200">Удаление персонажа</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <input className="field flex-1" placeholder="УДАЛИТЬ" value={deleteConfirmation} onChange={(event) => setDeleteConfirmation(event.target.value)} />
            <button className="btn-secondary border-red-400/40 text-red-100" disabled={deleteConfirmation !== "УДАЛИТЬ"} onClick={deleteCharacter}><Trash2 size={16} />Удалить персонажа</button>
          </div>
        </div>}
      </section>
      <ReadOnlyInventoryPanel inventory={inventory} />
    </div>
  );
}

const grantTypeLabels: Record<AdminGrantLog["operation_type"], string> = {
  karma: "Карма",
  xp: "Опыт",
  gold: "Золото",
  item: "Предмет"
};

function GrantLogsPage() {
  const [logs, setLogs] = useState<AdminGrantLog[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [filters, setFilters] = useState({ character_id: "", user_id: "", operation_type: "", date: "" });
  const [error, setError] = useState("");

  function loadLogs(nextFilters = filters) {
    const params = Object.fromEntries(Object.entries(nextFilters).filter(([, value]) => value));
    setError("");
    api.get<AdminGrantLog[]>("/admin/grant-logs", { params })
      .then((response) => setLogs(response.data))
      .catch((loadError) => setError(apiErrorDetail(loadError, "Не удалось загрузить журнал выдач")));
  }

  useEffect(() => {
    Promise.all([api.get<Character[]>("/admin/characters"), api.get<AdminUser[]>("/admin/users")])
      .then(([characterResponse, userResponse]) => {
        setCharacters(characterResponse.data);
        setUsers(userResponse.data);
      });
    loadLogs();
  }, []);

  return (
    <section className="panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-2xl font-bold text-ember">Журнал выдач</h1><p className="text-sm text-white/55">История выдачи игровых ресурсов администраторами</p></div>
        <Link className="btn-secondary" to="/admin">Назад</Link>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-4">
        <select className="field" value={filters.user_id} onChange={(event) => setFilters({ ...filters, user_id: event.target.value })}><option value="">Все игроки</option>{users.map((row) => <option key={row.id} value={row.id}>{row.username}</option>)}</select>
        <select className="field" value={filters.character_id} onChange={(event) => setFilters({ ...filters, character_id: event.target.value })}><option value="">Все персонажи</option>{characters.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select>
        <select className="field" value={filters.operation_type} onChange={(event) => setFilters({ ...filters, operation_type: event.target.value })}><option value="">Все типы</option>{Object.entries(grantTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <input className="field" type="date" value={filters.date} onChange={(event) => setFilters({ ...filters, date: event.target.value })} />
      </div>
      <button className="btn mt-3" onClick={() => loadLogs()}>Применить фильтры</button>
      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[1040px] text-left text-sm">
          <thead className="text-xs uppercase text-white/45"><tr><th className="py-2 pr-3">Дата и время</th><th className="py-2 pr-3">Администратор</th><th className="py-2 pr-3">Игрок</th><th className="py-2 pr-3">Персонаж</th><th className="py-2 pr-3">Тип</th><th className="py-2 pr-3">Значение</th><th className="py-2 pr-3">Причина</th></tr></thead>
          <tbody>{logs.map((log) => <tr className="border-t border-white/10" key={log.id}><td className="py-3 pr-3">{new Date(log.created_at).toLocaleString("ru-RU")}</td><td className="py-3 pr-3">{log.admin_username}</td><td className="py-3 pr-3">{log.username}</td><td className="py-3 pr-3">{log.character_name ?? "-"}</td><td className="py-3 pr-3">{grantTypeLabels[log.operation_type]}</td><td className="py-3 pr-3">{log.value}</td><td className="py-3 pr-3 whitespace-pre-wrap">{log.reason}</td></tr>)}</tbody>
        </table>
        {!logs.length && <p className="py-6 text-center text-white/55">Записей нет</p>}
      </div>
    </section>
  );
}

function ShopLogsPage() {
  const [logs, setLogs] = useState<ShopTransactionLog[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [filters, setFilters] = useState({ character_id: "", user_id: "", mode: "", date: "" });
  const [error, setError] = useState("");

  function loadLogs(nextFilters = filters) {
    const params = Object.fromEntries(
      Object.entries(nextFilters).filter(([, value]) => value)
    );
    setError("");
    api.get<ShopTransactionLog[]>("/admin/shop-logs", { params })
      .then((response) => setLogs(response.data))
      .catch((loadError) => setError(apiErrorDetail(loadError, "Не удалось загрузить логи")));
  }

  useEffect(() => {
    Promise.all([
      api.get<Character[]>("/admin/characters"),
      api.get<AdminUser[]>("/admin/users")
    ]).then(([characterResponse, userResponse]) => {
      setCharacters(characterResponse.data);
      setUsers(userResponse.data);
    });
  }, []);

  useEffect(() => {
    loadLogs();
  }, [filters]);

  function updateFilter(field: keyof typeof filters, value: string) {
    setFilters((current) => ({ ...current, [field]: value }));
  }

  function resetFilters() {
    setFilters({ character_id: "", user_id: "", mode: "", date: "" });
  }

  return (
    <section className="panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-ember">Логи магазина</h1>
          <p className="text-sm text-white/60">Покупки, продажи и заработок персонажей</p>
        </div>
        <Link className="btn-secondary" to="/admin">Назад</Link>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-4">
        <label className="field-label">
          <span>Игрок</span>
          <select className="field" value={filters.user_id} onChange={(event) => updateFilter("user_id", event.target.value)}>
            <option value="">Все</option>
            {users.map((user) => <option key={user.id} value={user.id}>{user.username}</option>)}
          </select>
        </label>
        <label className="field-label">
          <span>Персонаж</span>
          <select className="field" value={filters.character_id} onChange={(event) => updateFilter("character_id", event.target.value)}>
            <option value="">Все</option>
            {characters.map((character) => <option key={character.id} value={character.id}>{character.name} · {character.owner_username}</option>)}
          </select>
        </label>
        <label className="field-label">
          <span>Операция</span>
          <select className="field" value={filters.mode} onChange={(event) => updateFilter("mode", event.target.value)}>
            <option value="">Все</option>
            <option value="buy">Покупка</option>
            <option value="sell">Продажа</option>
            <option value="work">Работа</option>
          </select>
        </label>
        <label className="field-label">
          <span>Дата</span>
          <input className="field" type="date" value={filters.date} onChange={(event) => updateFilter("date", event.target.value)} />
        </label>
      </div>
      <div className="mt-3 flex justify-end">
        <button className="btn-secondary" onClick={resetFilters}>Сбросить</button>
      </div>
      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead className="text-xs uppercase text-white/45">
            <tr>
              <th className="py-2 pr-3">Дата</th>
              <th className="py-2 pr-3">Кто выполнил</th>
              <th className="py-2 pr-3">Игрок</th>
              <th className="py-2 pr-3">Персонаж</th>
              <th className="py-2 pr-3">Операция</th>
              <th className="py-2 pr-3">Предмет</th>
              <th className="py-2 pr-3">Цена</th>
              <th className="py-2 pr-3">Наёмник</th>
              <th className="py-2 pr-3">Итого</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr className="border-t border-white/10" key={log.id}>
                <td className="py-3 pr-3">{new Date(log.created_at).toLocaleString("ru-RU")}</td>
                <td className="py-3 pr-3">{log.actor_username ?? log.username}</td>
                <td className="py-3 pr-3">{log.username}</td>
                <td className="py-3 pr-3">{log.character_name}</td>
                <td className="py-3 pr-3">{log.mode === "buy" ? "Покупка" : log.mode === "sell" ? "Продажа" : "Работа"}</td>
                <td className="py-3 pr-3">{log.item_name} · {log.rarity}</td>
                <td className="py-3 pr-3">{log.item_price} зм</td>
                <td className="py-3 pr-3">{log.hireling_cost} зм</td>
                <td className="py-3 pr-3 font-semibold text-ember">{log.mode === "work" && log.total_copper != null ? `${Math.floor(log.total_copper / 100)} зм ${Math.floor(log.total_copper % 100 / 10)} см ${log.total_copper % 10} мм` : `${log.total_amount} зм`}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr className="border-t border-white/10">
                <td className="py-6 text-center text-white/55" colSpan={9}>Записей нет</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MarketSalesPage() {
  const [logs, setLogs] = useState<MarketSaleLog[]>([]);
  const [date, setDate] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    api.get<MarketSaleLog[]>("/admin/market-sales", { params: date ? { date } : {} })
      .then((response) => setLogs(response.data))
      .catch((loadError) => setError(apiErrorDetail(loadError, "Не удалось загрузить продажи")));
  }, [date]);
  return (
    <section className="panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-xl font-bold text-ember">Журнал рынка</h1><p className="text-sm text-white/60">Продажи обычных предметов игроками</p></div>
        <Link className="btn-secondary" to="/admin">Назад</Link>
      </div>
      <label className="field-label mt-5 max-w-xs"><span>Дата</span><input className="field" type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
      <div className="mt-5 overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="text-xs uppercase text-white/45"><tr><th className="py-2 pr-3">Дата</th><th className="py-2 pr-3">Кто выполнил</th><th className="py-2 pr-3">Игрок</th><th className="py-2 pr-3">Персонаж</th><th className="py-2 pr-3">Предмет</th><th className="py-2 pr-3">Сумма</th></tr></thead><tbody>{logs.map((log) => <tr className="border-t border-white/10" key={log.id}><td className="py-3 pr-3">{new Date(log.created_at).toLocaleString("ru-RU")}</td><td className="py-3 pr-3">{log.actor_username ?? log.username}</td><td className="py-3 pr-3">{log.username}</td><td className="py-3 pr-3">{log.character_name}</td><td className="py-3 pr-3">{log.item_name}</td><td className="py-3 pr-3 font-semibold text-ember">+{log.gold} зм</td></tr>)}</tbody></table>{!logs.length && <p className="py-6 text-center text-white/55">Записей нет</p>}</div>
    </section>
  );
}

const karmaPurchaseLabels: Record<KarmaPurchase["purchase_type"], string> = {
  xp: "Покупка опыта",
  item: "Товар магазина",
  opener: "Покупка открывашки",
  resurrection: "Воскрешение персонажа"
};

function KarmaShopLogsPage() {
  const [logs, setLogs] = useState<KarmaPurchase[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    api.get<KarmaPurchase[]>("/admin/karma-shop-logs")
      .then((response) => setLogs(response.data))
      .catch((loadError) => setError(apiErrorDetail(loadError, "Не удалось загрузить логи")));
  }, []);
  return <section className="panel p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-bold text-ember">Логи магазина кармы</h1><p className="text-sm text-white/55">История всех покупок за карму</p></div><Link className="btn-secondary" to="/admin">Назад</Link></div>{error && <p className="mt-3 text-red-300">{error}</p>}<div className="mt-5 overflow-x-auto"><table className="w-full min-w-[850px] text-left text-sm"><thead className="text-xs uppercase text-white/45"><tr><th className="py-2 pr-3">Дата</th><th className="py-2 pr-3">Кто выполнил</th><th className="py-2 pr-3">Игрок</th><th className="py-2 pr-3">Персонаж</th><th className="py-2 pr-3">Тип</th><th className="py-2 pr-3">Наименование</th><th className="py-2 pr-3">Стоимость</th><th className="py-2 pr-3">Уровень</th></tr></thead><tbody>{logs.map((log) => <tr className="border-t border-white/10" key={log.id}><td className="py-3 pr-3">{new Date(log.created_at).toLocaleString("ru-RU")}</td><td className="py-3 pr-3">{log.actor_username ?? log.username}</td><td className="py-3 pr-3">{log.username}</td><td className="py-3 pr-3">{log.character_name ?? "-"}</td><td className="py-3 pr-3">{karmaPurchaseLabels[log.purchase_type]}</td><td className="py-3 pr-3">{log.name}</td><td className="py-3 pr-3">{log.cost} кармы</td><td className="py-3 pr-3">{log.character_level ?? "-"}</td></tr>)}</tbody></table>{!logs.length && <p className="py-6 text-center text-white/55">Записей нет</p>}</div></section>;
}

function TransferLogsPage() {
  const [logs, setLogs] = useState<TransferLog[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [filters, setFilters] = useState({ character_id: "", user_id: "", transfer_type: "", date: "" });
  const [error, setError] = useState("");

  function loadLogs(nextFilters = filters) {
    const params = Object.fromEntries(
      Object.entries(nextFilters).filter(([, value]) => value)
    );
    setError("");
    api.get<TransferLog[]>("/admin/transfer-logs", { params })
      .then((response) => setLogs(response.data))
      .catch((loadError) => setError(apiErrorDetail(loadError, "Не удалось загрузить передачи")));
  }

  useEffect(() => {
    Promise.all([
      api.get<Character[]>("/admin/characters"),
      api.get<AdminUser[]>("/admin/users")
    ]).then(([characterResponse, userResponse]) => {
      setCharacters(characterResponse.data);
      setUsers(userResponse.data);
    });
  }, []);

  useEffect(() => {
    loadLogs();
  }, [filters]);

  function updateFilter(field: keyof typeof filters, value: string) {
    setFilters((current) => ({ ...current, [field]: value }));
  }

  function resetFilters() {
    setFilters({ character_id: "", user_id: "", transfer_type: "", date: "" });
  }

  return (
    <section className="panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-ember">Логи передач</h1>
          <p className="text-sm text-white/60">Валюта и предметы между персонажами</p>
        </div>
        <Link className="btn-secondary" to="/admin">Назад</Link>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-4">
        <label className="field-label">
          <span>Игрок</span>
          <select className="field" value={filters.user_id} onChange={(event) => updateFilter("user_id", event.target.value)}>
            <option value="">Все</option>
            {users.map((user) => <option key={user.id} value={user.id}>{user.username}</option>)}
          </select>
        </label>
        <label className="field-label">
          <span>Персонаж</span>
          <select className="field" value={filters.character_id} onChange={(event) => updateFilter("character_id", event.target.value)}>
            <option value="">Все</option>
            {characters.map((character) => <option key={character.id} value={character.id}>{character.name} · {character.owner_username}</option>)}
          </select>
        </label>
        <label className="field-label">
          <span>Тип</span>
          <select className="field" value={filters.transfer_type} onChange={(event) => updateFilter("transfer_type", event.target.value)}>
            <option value="">Все</option>
            <option value="currency">Валюта</option>
            <option value="item">Предмет</option>
          </select>
        </label>
        <label className="field-label">
          <span>Дата</span>
          <input className="field" type="date" value={filters.date} onChange={(event) => updateFilter("date", event.target.value)} />
        </label>
      </div>
      <div className="mt-3 flex justify-end">
        <button className="btn-secondary" onClick={resetFilters}>Сбросить</button>
      </div>
      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[920px] text-left text-sm">
          <thead className="text-xs uppercase text-white/45">
            <tr>
              <th className="py-2 pr-3">Дата</th>
              <th className="py-2 pr-3">Игрок</th>
              <th className="py-2 pr-3">Отправитель</th>
              <th className="py-2 pr-3">Получатель</th>
              <th className="py-2 pr-3">Тип</th>
              <th className="py-2 pr-3">Сумма</th>
              <th className="py-2 pr-3">Предмет</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr className="border-t border-white/10" key={log.id}>
                <td className="py-3 pr-3">{new Date(log.created_at).toLocaleString("ru-RU")}</td>
                <td className="py-3 pr-3">{log.username}</td>
                <td className="py-3 pr-3">{log.sender_character_name}</td>
                <td className="py-3 pr-3">{log.recipient_character_name}</td>
                <td className="py-3 pr-3">{log.transfer_type === "currency" ? "Валюта" : "Предмет"}</td>
                <td className="py-3 pr-3">{log.gold} зм / {log.silver} см / {log.copper} мм</td>
                <td className="py-3 pr-3">{log.item_name ? `${log.item_name} · ${log.item_rarity}` : "-"}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr className="border-t border-white/10">
                <td className="py-6 text-center text-white/55" colSpan={7}>Записей нет</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ReadOnlyInventoryPanel({ inventory }: { inventory: Inventory | null }) {
  return (
    <aside className="panel p-5">
      <h2 className="text-lg font-semibold text-ember">Инвентарь</h2>
      <p className="mt-1 text-sm text-white/70">{inventory?.gold ?? 0} зм / {inventory?.silver ?? 0} см / {inventory?.copper ?? 0} мм</p>
      <div className="mt-4 rounded-md border border-white/10 p-3">
        <h3 className="font-semibold text-ember">Заметки</h3>
        <p className="mt-2 whitespace-pre-wrap text-sm text-white/75">{inventory?.notes || "Заметок нет"}</p>
      </div>
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

class ErrorBoundary extends Component<{ children: React.ReactNode }, { error: Error | null }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="grid min-h-screen place-items-center bg-[#101217] px-4 text-parchment">
          <div className="panel flex w-full max-w-sm flex-col gap-3 p-6">
            <h1 className="text-2xl font-bold text-ember">Что-то пошло не так</h1>
            <p className="text-sm text-white/70">Произошла ошибка. Попробуйте обновить страницу.</p>
            <button className="btn" onClick={() => window.location.reload()}>Обновить</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/" element={<Protected><HomePage /></Protected>} />
        <Route path="/characters" element={<Protected><CharactersPage /></Protected>} />
        <Route path="/characters/new" element={<Protected><CharacterFormPage /></Protected>} />
        <Route path="/characters/:id" element={<Protected><CharacterPage /></Protected>} />
        <Route path="/characters/:id/edit" element={<Protected><CharacterFormPage edit /></Protected>} />
        <Route path="/shop" element={<Protected><ShopPage /></Protected>} />
        <Route path="/market" element={<Protected><MarketPage /></Protected>} />
        <Route path="/karma-shop" element={<Protected><KarmaShopPage /></Protected>} />
        <Route path="/leaderboard" element={<Protected><LeaderboardPage /></Protected>} />
        <Route path="/chat" element={<Protected><ChatPage /></Protected>} />
        <Route path="/game-recruitments" element={<Protected><GameRecruitmentsPage /></Protected>} />
        <Route path="/server-rules" element={<Protected><ContentPage pageSlug="server-rules" title="Правила сервера" /></Protected>} />
        <Route path="/approved-homebrew" element={<Protected><ContentPage pageSlug="approved-homebrew" title="Одобренное ХБ" /></Protected>} />
        <Route path="/profile" element={<Protected><ProfilePage /></Protected>} />
        <Route path="/project-settings" element={<Protected><ProjectSettingsPage /></Protected>} />
        <Route path="/project-management" element={<Protected><ProjectManagementPage /></Protected>} />
        <Route path="/admin/shop-logs" element={<Protected><ShopLogsPage /></Protected>} />
        <Route path="/admin/market-sales" element={<Protected><MarketSalesPage /></Protected>} />
        <Route path="/admin/karma-shop-logs" element={<Protected><KarmaShopLogsPage /></Protected>} />
        <Route path="/admin/transfer-logs" element={<Protected><TransferLogsPage /></Protected>} />
        <Route path="/admin/grant-logs" element={<Protected><GrantLogsPage /></Protected>} />
        <Route path="/admin/characters/:id" element={<Protected><AdminCharacterPage /></Protected>} />
        <Route path="/admin" element={<Protected><AdminPage /></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

createRoot(document.getElementById("root")!).render(<ErrorBoundary><App /></ErrorBoundary>);
