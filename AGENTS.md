# Project: Epoch of Catastrophe Assistant (D&D Open Table)

## 0) Purpose & Vision

### Purpose

Web application that assists players and game masters of the D&D 2014 open-table campaign **"Epoch of Catastrophe"**.

The application is intended to automate repetitive bookkeeping tasks:

* Character management
* Inventory management
* Currency tracking
* Karma tracking
* Trading and item acquisition
* Experience management
* Game Master administration

The application is not intended to replace tabletop roleplaying. It only assists with record keeping and rule automation.

### Target Users

Two user roles exist:

#### Player

Can:

* Log in
* Manage own characters
* View character sheets
* Manage inventory
* Buy and sell items
* Track currency
* View karma (ingame currency for players rollplay. Players get 0-3 karma after game from master. Master get 0-3 karma after game from players. Karma not directly  for players character. Karma is globaly for player.)

#### Game Master (Admin)

Can:

* Manage all players
* Manage all characters
* Grant XP (Epoha has revorked experience system. Players need that much xp as their next lvl to reach next lvl. For example. 10 level varior need 11 xp to reach 11 lvl. 17 lvl wizard need 18xp to reach lvl 18. And 3 lvl barbarian need 4 lvl to reach level 4.)
* Grant or remove currency
* Modify karma
* Add items to inventories
* Revive dead characters
* View campaign statistics

---

## 1) Technology Stack

### Backend

* Python 3.12+
* FastAPI
* SQLAlchemy ORM
* PostgreSQL
* JWT Authentication

### Frontend

Preferred:

* React
* TypeScript


### API Style

* REST API
* JSON requests/responses

### Authentication

* JWT Bearer Token
* Login required for all protected endpoints

---

## 2) Current Domain Model

### User

Represents a player account.

Fields:

* id
* username
* email
* hashed_password
* karma

Relationships:

* User -> many Characters

### Character

Represents a player character.

Fields:

* id
* name
* class_name
* subclass
* race
* background
* route
* level
* xp
* hp
* armor_class
* strength
* dexterity
* constitution
* intelligence
* wisdom
* charisma
* investigation

Relationships:

* Character -> User
* Character -> Inventory

### Inventory

Stores character resources.

Fields:

* gold
* silver
* copper

Relationships:

* Inventory -> many InventoryItems

### InventoryItem

Fields:

* id
* name
* rarity
* is_consumable

---

## 3) First Prototype Requirements

### Page 1: Login

Purpose:

Authenticate user and obtain JWT token.

UI:

* Username field
* Password field
* Login button
* Logout button

Requirements:

* Store JWT token in browser
* Automatically redirect authenticated users
* Display login errors

Database seed:

Create default administrator account.

Document credentials inside README.

Example:

Username: admin

Password: admin123

These values may be changed later.

---

### Page 2: Main Menu

Purpose:

Central navigation page.

Buttons:

* Shop
* My Characters
* Create Character

Additional:

Display current user information:

* Username
* Karma

---

### Page 3: Character List

Purpose:

Show all characters owned by current user.

Features:

* List all characters
* Open character sheet
* Create character
* Edit character

Displayed information:

* Name
* Class
* Level
* Race
* Subclass

---

### Page 4: Character Sheet

Purpose:

Detailed character page.

Display:

#### Basic Information

* Name
* Class
* Subclass
* Race
* Background
* Route

#### Combat

* HP
* Armor Class

#### Progression

* Level
* XP

#### Attributes

* Strength
* Dexterity
* Constitution
* Intelligence
* Wisdom
* Charisma
* Investigation

#### Inventory

Currency:

* Gold
* Silver
* Copper

Items:

* Name
* Rarity
* Consumable status

---

### Page 5: Shop

Purpose:

Automate item acquisition and sale according to campaign rules.

Workflow:

#### Step 1

Choose:

* Buy
* Sell

#### Step 2

Enter:

* Item name
* Item rarity
* Consumable status

#### Step 3

Choose character.

#### Step 4

Choose searcher.

Options:

##### Poor Hireling

Bonus:
+0

Cost:
1 gold/day

##### Good Hireling

Bonus:
+4

Cost:
5 gold/day

##### Competent Hireling

Bonus:
+6

Cost:
10 gold/day

##### Expert Hireling

Bonus:
+8

Cost:
25 gold/day

#### Step 5

Search

Button:

* Find Seller
* Find Buyer

System performs:

##### Search Roll

d20 + modifier

Success DC depends on rarity.

##### Price Roll

d100

Determines final price multiplier.

##### Search Duration

Common:
d4 days

Uncommon:
d8 days

Rare:
d12 days

Every search consumes hireling cost.

#### Step 6

Show Result

Display:

* Search roll
* Total roll
* Required DC
* Days spent
* Price roll
* Item price

Buttons:

* Buy Item / Sell Item
* Continue Search

#### Purchase Result

* Currency deducted
* Item added to inventory

#### Sale Result

* Currency added
* Item removed from inventory

---

## 4) Admin Panel

Accessible only to administrators.

### User Management

View:

* All users
* Karma
* Character count

Actions:

* Modify karma

### Character Management

View all characters.

Actions:

#### Grant XP

Increase character XP.

#### Grant Currency

Add:

* Gold
* Silver
* Copper

#### Grant Item

Add inventory item.

#### Revive Character

Set character alive.

Future support:

* Death system
* Status effects

---

## 5) Frontend Architecture

Recommended structure:

```text
frontend/
├── src/
│   ├── api/
│   │   ├── auth.ts
│   │   ├── characters.ts
│   │   ├── inventory.ts
│   │   └── shop.ts
│   │
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── HomePage.tsx
│   │   ├── CharactersPage.tsx
│   │   ├── CharacterPage.tsx
│   │   ├── ShopPage.tsx
│   │   └── AdminPage.tsx
│   │
│   ├── components/
│   │   ├── Navbar.tsx
│   │   ├── CharacterCard.tsx
│   │   ├── InventoryView.tsx
│   │   └── ShopSearchPanel.tsx
│   │
│   └── App.tsx
```

---

## 6) Backend Development Rules

### API Design

Always:

* Validate ownership of characters
* Validate inventory ownership
* Validate authenticated user

Never:

* Trust frontend data
* Allow cross-user access

### Security

JWT required for protected endpoints.

All modifications must verify:

```python
character.user_id == current_user.id
```

unless administrator privileges are used.

---

## 7) README Requirements

README must contain:

### Setup

#### Backend

* Python installation
* Virtual environment creation
* Dependency installation
* PostgreSQL setup
* Database creation
* Running FastAPI

#### Frontend

* Node.js installation
* npm install
* npm run dev

#### VS Code

Recommended extensions:

* Python
* Pylance
* ESLint
* Prettier

### Test Admin Account

Include:

* Username
* Password

### API Documentation

Swagger URL:

```text
http://localhost:8000/docs
```

---

## 8) Future Features

Not required for first prototype.

Planned:

* Character death system
* Resurrection mechanics
* Campaign logs
* Quest tracking
* Reputation system
* World events
* Crafting
* Downtime activities
* Character portraits
* Multi-GM support
* Mobile-friendly UI

---

## 9) Acceptance Criteria

First prototype is considered complete when:

* User can log in
* User can create characters
* User can edit characters
* User can view character sheets
* User can buy items
* User can sell items
* Currency updates automatically
* Inventory updates automatically
* Admin can grant XP
* Admin can grant currency
* Admin can modify karma
* Admin can grant items
* Admin can revive characters
* Frontend communicates with FastAPI backend successfully
* README contains complete setup instructions
