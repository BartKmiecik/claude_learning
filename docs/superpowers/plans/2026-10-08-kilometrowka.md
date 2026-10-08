# Kilometrówka Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a free, no-account, client-side Polish mileage log web app ("ewidencja przebiegu pojazdu") with a one-time 79 zł Pro unlock sold via Lemon Squeezy license keys.

**Architecture:** A static SPA (Vanilla JS + Vite) served from Cloudflare Pages. Pure logic modules (`rates.js`, `km.js`, `slownie.js`, `store.js`) are DOM-free and unit-tested in isolation; UI wires them together; `pdf/` and `xlsx.js` consume plain data structures. Everything runs in the browser — the only network call is the Lemon Squeezy license API.

**Tech Stack:** Node ≥ 20 (installed: v23.0.0), npm 9, Vite (vanilla template), Vitest (+jsdom for UI tests), pdfmake (PDF), pdfjs-dist (PDF text-extraction in tests), SheetJS `xlsx` (Excel export).

**Spec:** [docs/superpowers/specs/2026-10-08-kilometrowka-design.md](../specs/2026-10-08-kilometrowka-design.md)

**Deviations from spec (approved via plan review):**
1. **pdfmake instead of pdf-lib + Noto Sans.** pdfmake bundles Roboto TTF with full Polish glyph coverage and declarative table layout; it avoids a fragile TTF-vendoring pipeline. The diacritics guarantee is enforced by a pdfjs-dist text-extraction test instead of font embedding.
2. **`storage.flats` added** to the data model — ryczałt (flat monthly settlement) entries are not km trips, so they get their own array.
3. **`storage.sellerName` added** — the PDF header needs a seller name in the free tier; Pro adds the logo.
4. Trip fields follow the spec (`start`/`end` as two route inputs), not a single "route" field.

## Global Constraints

- All user-visible copy is Polish; code identifiers and commit messages are English.
- Client-side only. No server, no backend, no uploads. The ONLY network call allowed is `https://api.lemonsqueezy.com/v1/licenses`.
- Rates are data-driven and versioned in `src/rates.js` — never hardcoded in logic.
- Every PDF ends with the disclaimer "Niniejszy dokument nie zastępuje programu księgowego ani doradcy podatkowego."
- Pro price: 79 zł one-time. Pro features are gated behind `isPro(license)`.
- One commit per task, conventional messages (e.g. `feat: add rates module`). Every commit message ends with the line `Co-Authored-By: Claude Code <noreply@anthropic.com>`.
- Run tests with `npm test` (configured as `vitest run`). Node environment by default; UI tests opt into jsdom with `// @vitest-environment jsdom` as the file's first line.

## Review Focus

The five input classes the spec implies but no single task's happy-path test covers:

1. **Month boundary:** a trip on `2026-01-31` must never appear in the February summary and vice versa. → Task 3 test.
2. **Polish decimal comma:** users type `12,5` — parsing must accept the comma and produce `12.5`; garbage input must produce a clean Polish error, not `NaN`. → Task 3 test (logic) + Task 5 test (error shown in UI).
3. **Diacritics in the PDF:** seller names and purposes containing ą/ę/ż/ó must render correctly in the generated PDF. → Task 6 text-extraction test.
4. **Corrupt or foreign localStorage:** malformed JSON or wrong-shape data must show a clean Polish error message, never a crash or silent data loss. → Task 2 tests + Task 5 error-render test.
5. **Limit boundary:** exactly 6 000 km → no warning; 6 000,5 km → warning (strict `>`). → Task 3 test.

---

### Task 1: Scaffold + rates module

**Files:**
- Create: `projects/kilometrowka/` (via Vite scaffold)
- Create: `src/rates.js`
- Modify: `vite.config.js` (add Vitest config)
- Modify: `package.json` (add `test` script)
- Test: `tests/rates.test.js`
- Delete: `src/counter.js`, `src/javascript.svg`, `public/vite.svg` (template boilerplate)

**Interfaces:**
- Consumes: nothing.
- Produces (used by Tasks 3, 5, 10):
  - `capacityClass` values: `'<=900' | '>900' | 'motorcycle' | 'moped'`
  - `RATE_SETS` — object keyed by set id, e.g. `{ 'od 2023-01-17': { '<=900': { label, rate, monthlyLimitKm }, ... } }`
  - `DEFAULT_RATE_SET = 'od 2023-01-17'`
  - `rateFor(capacityClass, setId = DEFAULT_RATE_SET)` → `{ label: string, rate: number, monthlyLimitKm: number }`; throws `Error('Nieznana klasa pojazdu: ' + capacityClass)` for unknown classes
  - `monthlyLimitKm(capacityClass, setId = DEFAULT_RATE_SET)` → number

- [ ] **Step 1: Scaffold the Vite vanilla project**

Run from the repo root:
```bash
cd projects && npm create -y vite@latest kilometrowka -- --template vanilla && cd kilometrowka && npm install && npm install -D vitest
```

- [ ] **Step 2: Remove template boilerplate**

```bash
rm src/counter.js src/javascript.svg public/vite.svg
```

- [ ] **Step 3: Write the failing tests**

Create `tests/rates.test.js`:

```js
import { describe, it, expect } from 'vitest';
import { rateFor, monthlyLimitKm, DEFAULT_RATE_SET, RATE_SETS } from '../src/rates.js';

describe('rateFor', () => {
  it('returns the statutory rate for a car up to 900 cm³', () => {
    expect(rateFor('<=900')).toEqual({
      label: 'Samochód osobowy do 900 cm³',
      rate: 0.89,
      monthlyLimitKm: 6000,
    });
  });

  it('returns the statutory rate for a car above 900 cm³', () => {
    expect(rateFor('>900')).toEqual({
      label: 'Samochód osobowy powyżej 900 cm³',
      rate: 1.15,
      monthlyLimitKm: 6000,
    });
  });

  it('returns the motorcycle and moped rates', () => {
    expect(rateFor('motorcycle').rate).toBe(0.69);
    expect(rateFor('moped').rate).toBe(0.42);
  });

  it('throws on an unknown capacity class', () => {
    expect(() => rateFor('bicycle')).toThrow(/Nieznana klasa pojazdu/);
  });

  it('supports selecting a rate set by id', () => {
    expect(rateFor('<=900', DEFAULT_RATE_SET).rate).toBe(0.89);
  });
});

describe('monthlyLimitKm', () => {
  it('returns 6000 km for cars and 7500 km for two-wheelers', () => {
    expect(monthlyLimitKm('<=900')).toBe(6000);
    expect(monthlyLimitKm('>900')).toBe(6000);
    expect(monthlyLimitKm('motorcycle')).toBe(7500);
    expect(monthlyLimitKm('moped')).toBe(7500);
  });
});

describe('RATE_SETS', () => {
  it('defines all four capacity classes in the default set', () => {
    expect(Object.keys(RATE_SETS[DEFAULT_RATE_SET])).toEqual(['<=900', '>900', 'motorcycle', 'moped']);
  });
});
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `npm test`
Expected: FAIL — `Cannot find module '../src/rates.js'`.

- [ ] **Step 5: Implement `src/rates.js`**

```js
// Statutory mileage rates (Rozporządzenie Ministra Infrastruktury z 25.03.2002,
// Dz.U. 2023 poz. 5 § 2), unchanged since 17 Jan 2023. Data-driven and versioned:
// when the pending 2026 regulation is enacted, add a new set and point
// DEFAULT_RATE_SET at it.
export const RATE_SETS = {
  'od 2023-01-17': {
    '<=900': { label: 'Samochód osobowy do 900 cm³', rate: 0.89, monthlyLimitKm: 6000 },
    '>900': { label: 'Samochód osobowy powyżej 900 cm³', rate: 1.15, monthlyLimitKm: 6000 },
    motorcycle: { label: 'Motocykl', rate: 0.69, monthlyLimitKm: 7500 },
    moped: { label: 'Motorower', rate: 0.42, monthlyLimitKm: 7500 },
  },
};

export const DEFAULT_RATE_SET = 'od 2023-01-17';

export function rateFor(capacityClass, setId = DEFAULT_RATE_SET) {
  const entry = RATE_SETS[setId]?.[capacityClass];
  if (!entry) {
    throw new Error(`Nieznana klasa pojazdu: ${capacityClass}`);
  }
  return entry;
}

export function monthlyLimitKm(capacityClass, setId = DEFAULT_RATE_SET) {
  return rateFor(capacityClass, setId).monthlyLimitKm;
}
```

- [ ] **Step 6: Add the Vitest config and test script**

In `vite.config.js` (replace the template content):

```js
import { defineConfig } from 'vite';

export default defineConfig({
  test: {
    environment: 'node',
  },
});
```

In `package.json`, add to `"scripts"`:
```json
"test": "vitest run"
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `npm test`
Expected: PASS — 7 tests.

- [ ] **Step 8: Commit**

```bash
git add projects/kilometrowka
git commit -m "feat: scaffold kilometrowka project with statutory rates module"
```

---

### Task 2: Store (persistence)

**Files:**
- Create: `src/store.js`
- Test: `tests/store.test.js`

**Interfaces:**
- Consumes: nothing.
- Produces (used by Tasks 3, 5, 9, 10):
  - `STORAGE_KEY = 'kilometrowka.v1'`
  - `createStore(storage, key = STORAGE_KEY)` → `{ load(): state, save(state): void }` where `storage` is any object with `getItem(key) → string|null` and `setItem(key, value)` (browser `localStorage` or a test double)
  - `state` shape: `{ version: 1, vehicles: [{ id, name, plate, capacityClass }], trips: [{ id, date, start, end, purpose, km, vehicleId }], flats: [{ id, month, amount, vehicleId }], sellerName: '', logo: null }` (`logo` holds a Pro-tier logo data URL; `null` when unset)
  - `StoreError extends Error` — thrown by `load()` on corrupt data

- [ ] **Step 1: Write the failing tests**

Create `tests/store.test.js`:

```js
import { describe, it, expect } from 'vitest';
import { createStore, StoreError, STORAGE_KEY } from '../src/store.js';

function memoryStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
  };
}

describe('createStore', () => {
  it('returns an empty state when nothing is stored', () => {
    const store = createStore(memoryStorage());
    expect(store.load()).toEqual({ version: 1, vehicles: [], trips: [], flats: [], sellerName: '', logo: null });
  });

  it('round-trips state through save and load', () => {
    const storage = memoryStorage();
    const store = createStore(storage);
    const state = {
      version: 1,
      vehicles: [{ id: 1, name: 'Mój samochód', plate: 'WA 12345', capacityClass: '>900' }],
      trips: [{ id: 1, date: '2026-10-08', start: 'Warszawa', end: 'Gdańsk', purpose: 'klient', km: 340, vehicleId: 1 }],
      flats: [],
      sellerName: 'Jan Kowalski',
      logo: null,
    };
    store.save(state);
    expect(store.load()).toEqual(state);
    expect(storage.getItem(STORAGE_KEY)).toContain('"sellerName":"Jan Kowalski"');
  });

  it('throws StoreError with a Polish message on corrupt JSON', () => {
    const storage = memoryStorage();
    storage.setItem(STORAGE_KEY, '{nie-json');
    const store = createStore(storage);
    expect(() => store.load()).toThrow(StoreError);
    expect(() => store.load()).toThrow(/uszkodzone/);
  });

  it('throws StoreError on wrong-shape data', () => {
    const storage = memoryStorage();
    storage.setItem(STORAGE_KEY, JSON.stringify({ vehicles: 'nie-tablica' }));
    const store = createStore(storage);
    expect(() => store.load()).toThrow(/nieprawidłowy format/);
  });

  it('defaults missing flats, sellerName and logo for forward compatibility', () => {
    const storage = memoryStorage();
    storage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, vehicles: [], trips: [] }));
    const store = createStore(storage);
    expect(store.load()).toEqual({ version: 1, vehicles: [], trips: [], flats: [], sellerName: '', logo: null });
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/store.js`**

```js
export const STORAGE_KEY = 'kilometrowka.v1';

export class StoreError extends Error {}

function emptyState() {
  return { version: 1, vehicles: [], trips: [], flats: [], sellerName: '', logo: null };
}

export function createStore(storage, key = STORAGE_KEY) {
  return {
    load() {
      const raw = storage.getItem(key);
      if (raw === null || raw === '') {
        return emptyState();
      }
      let parsed;
      try {
        parsed = JSON.parse(raw);
      } catch {
        throw new StoreError('Dane kilometrówki w przeglądarce są uszkodzone i nie mogły zostać odczytane.');
      }
      if (
        typeof parsed !== 'object' ||
        parsed === null ||
        !Array.isArray(parsed.vehicles) ||
        !Array.isArray(parsed.trips)
      ) {
        throw new StoreError('Dane kilometrówki mają nieprawidłowy format.');
      }
      return {
        version: 1,
        vehicles: parsed.vehicles,
        trips: parsed.trips,
        flats: Array.isArray(parsed.flats) ? parsed.flats : [],
        sellerName: typeof parsed.sellerName === 'string' ? parsed.sellerName : '',
        logo: typeof parsed.logo === 'string' ? parsed.logo : null,
      };
    },
    save(state) {
      storage.setItem(key, JSON.stringify(state));
    },
  };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test`
Expected: PASS — 5 new tests.

- [ ] **Step 5: Commit**

```bash
git add projects/kilometrowka/src/store.js projects/kilometrowka/tests/store.test.js
git commit -m "feat: add localStorage persistence with corrupt-data errors"
```

---

### Task 3: Domain logic (trips + aggregation + limits)

**Files:**
- Create: `src/km.js`
- Test: `tests/km.test.js`

**Interfaces:**
- Consumes: `rateFor` from Task 1; state shape from Task 2.
- Produces (used by Tasks 5, 6, 9, 10):
  - `round2(x)` → number (rounds to 2 decimals)
  - `parseKm(input)` → number; accepts `'12,5'` and `12.5`; throws `Error('Podaj liczbę kilometrów, np. 12,5.')` on garbage
  - `nextId(state)` → number (max id across vehicles/trips/flats + 1, or 1)
  - `addTrip(state, trip)` → new state
  - `addFlat(state, flat)` → new state
  - `aggregateMonth(state, month)` → summary, where `month` is `'YYYY-MM'`:
    ```js
    {
      month,
      vehicles: [{ vehicle, km, kmAmount, flatAmount, total, rate, purposes: [{ purpose, km }] }],
      totals: { km, kmAmount, flatAmount, total },
      limitWarnings: [{ vehicleId, vehicleName, km, limit }],
    }
    ```

- [ ] **Step 1: Write the failing tests**

Create `tests/km.test.js`:

```js
import { describe, it, expect } from 'vitest';
import { round2, parseKm, nextId, addTrip, addFlat, aggregateMonth } from '../src/km.js';

const vehicle = (id = 1, capacityClass = '>900') => ({ id, name: `Auto ${id}`, plate: '', capacityClass });
const trip = (overrides = {}) => ({
  id: 1, date: '2026-10-08', start: 'Warszawa', end: 'Gdańsk', purpose: 'klient', km: 100, vehicleId: 1,
  ...overrides,
});

describe('parseKm', () => {
  it('accepts Polish decimal comma', () => {
    expect(parseKm('12,5')).toBe(12.5);
  });
  it('accepts dot decimals and plain numbers', () => {
    expect(parseKm('12.5')).toBe(12.5);
    expect(parseKm('12')).toBe(12);
    expect(parseKm(12.5)).toBe(12.5);
  });
  it('throws a Polish error on garbage input', () => {
    expect(() => parseKm('abc')).toThrow(/kilometrów/);
    expect(() => parseKm('')).toThrow(/kilometrów/);
    expect(() => parseKm('12,5,5')).toThrow(/kilometrów/);
  });
});

describe('nextId', () => {
  it('returns 1 for an empty state', () => {
    expect(nextId({ vehicles: [], trips: [], flats: [] })).toBe(1);
  });
  it('returns max+1 across all collections', () => {
    const state = { vehicles: [{ id: 3 }], trips: [{ id: 7 }], flats: [{ id: 1 }] };
    expect(nextId(state)).toBe(8);
  });
});

describe('addTrip / addFlat', () => {
  it('appends without mutating the original state', () => {
    const state = { vehicles: [], trips: [], flats: [] };
    const next = addTrip(state, trip());
    expect(state.trips).toHaveLength(0);
    expect(next.trips).toHaveLength(1);
    const withFlat = addFlat(next, { id: 9, month: '2026-10', amount: 200, vehicleId: 1 });
    expect(withFlat.flats).toHaveLength(1);
  });
});

describe('aggregateMonth', () => {
  const state = {
    vehicles: [vehicle(1, '>900')],
    trips: [
      trip({ id: 1, date: '2026-10-05', km: 100 }),
      trip({ id: 2, date: '2026-10-20', km: 50, purpose: 'serwis' }),
      // Boundary: last day of the previous month must NOT be included.
      trip({ id: 3, date: '2026-09-30', km: 999 }),
      // Boundary: first day of the next month must NOT be included.
      trip({ id: 4, date: '2026-11-01', km: 999 }),
    ],
    flats: [],
  };

  it('aggregates only trips of the requested month', () => {
    const summary = aggregateMonth(state, '2026-10');
    expect(summary.vehicles[0].km).toBe(150);
    expect(summary.totals.km).toBe(150);
  });

  it('multiplies km by the vehicle rate (1.15 zł)', () => {
    const summary = aggregateMonth(state, '2026-10');
    expect(summary.vehicles[0].kmAmount).toBe(172.5);
    expect(summary.vehicles[0].rate).toBe(1.15);
    expect(summary.totals.total).toBe(172.5);
  });

  it('breaks down km per purpose', () => {
    const summary = aggregateMonth(state, '2026-10');
    const purposes = summary.vehicles[0].purposes;
    expect(purposes).toEqual([
      { purpose: 'klient', km: 100 },
      { purpose: 'serwis', km: 50 },
    ]);
  });

  it('uses "(bez celu)" for empty purposes', () => {
    const summary = aggregateMonth(
      { vehicles: [vehicle()], trips: [trip({ purpose: '  ' })], flats: [] },
      '2026-10',
    );
    expect(summary.vehicles[0].purposes).toEqual([{ purpose: '(bez celu)', km: 100 }]);
  });

  it('adds ryczałt flat amounts to the monthly total', () => {
    const summary = aggregateMonth(
      { vehicles: [vehicle()], trips: [trip()], flats: [{ id: 1, month: '2026-10', amount: 200, vehicleId: 1 }] },
      '2026-10',
    );
    expect(summary.vehicles[0].flatAmount).toBe(200);
    expect(summary.vehicles[0].total).toBe(315);
    expect(summary.totals.flatAmount).toBe(200);
    expect(summary.totals.total).toBe(315);
  });

  it('warns strictly above the monthly limit, not at it', () => {
    const atLimit = aggregateMonth(
      { vehicles: [vehicle()], trips: [trip({ km: 6000 })], flats: [] },
      '2026-10',
    );
    expect(atLimit.limitWarnings).toHaveLength(0);

    const overLimit = aggregateMonth(
      { vehicles: [vehicle()], trips: [trip({ km: 6000.5 })], flats: [] },
      '2026-10',
    );
    expect(overLimit.limitWarnings).toEqual([
      { vehicleId: 1, vehicleName: 'Auto 1', km: 6000.5, limit: 6000 },
    ]);
  });

  it('ignores trips whose vehicle no longer exists', () => {
    const summary = aggregateMonth(
      { vehicles: [], trips: [trip({ vehicleId: 99 })], flats: [] },
      '2026-10',
    );
    expect(summary.totals.km).toBe(0);
    expect(summary.limitWarnings).toHaveLength(0);
  });
});

describe('round2', () => {
  it('rounds floating point products to 2 decimals', () => {
    expect(round2(1234.56 * 1.15)).toBe(1419.74);
    expect(round2(0.1 + 0.2)).toBe(0.3);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/km.js`**

```js
import { rateFor } from './rates.js';

export function round2(x) {
  return Math.round(x * 100) / 100;
}

export function parseKm(input) {
  if (typeof input === 'number') {
    return input;
  }
  const normalized = String(input).trim().replace(',', '.');
  if (normalized === '' || !/^\d+(\.\d+)?$/.test(normalized)) {
    throw new Error('Podaj liczbę kilometrów, np. 12,5.');
  }
  return Number(normalized);
}

export function nextId(state) {
  const ids = [
    ...state.vehicles.map((v) => v.id),
    ...state.trips.map((t) => t.id),
    ...state.flats.map((f) => f.id),
  ];
  return ids.length ? Math.max(...ids) + 1 : 1;
}

export function addTrip(state, trip) {
  return { ...state, trips: [...state.trips, trip] };
}

export function addFlat(state, flat) {
  return { ...state, flats: [...state.flats, flat] };
}

export function aggregateMonth(state, month) {
  const trips = state.trips.filter((t) => t.date.slice(0, 7) === month);
  const flats = state.flats.filter((f) => f.month === month);

  const byVehicle = new Map();
  for (const vehicle of state.vehicles) {
    byVehicle.set(vehicle.id, { vehicle, km: 0, kmAmount: 0, flatAmount: 0, total: 0, purposes: new Map() });
  }

  for (const trip of trips) {
    const row = byVehicle.get(trip.vehicleId);
    if (!row) continue; // orphan trip: vehicle deleted
    row.km = round2(row.km + trip.km);
    const purpose = (trip.purpose || '').trim() || '(bez celu)';
    row.purposes.set(purpose, round2((row.purposes.get(purpose) || 0) + trip.km));
  }

  const totals = { km: 0, kmAmount: 0, flatAmount: 0, total: 0 };
  const vehicles = [];
  const limitWarnings = [];

  for (const row of byVehicle.values()) {
    const { rate, monthlyLimitKm: limit } = rateFor(row.vehicle.capacityClass);
    row.kmAmount = round2(row.km * rate);
    row.flatAmount = round2(
      flats.filter((f) => f.vehicleId === row.vehicle.id).reduce((sum, f) => sum + f.amount, 0),
    );
    row.total = round2(row.kmAmount + row.flatAmount);
    totals.km = round2(totals.km + row.km);
    totals.kmAmount = round2(totals.kmAmount + row.kmAmount);
    totals.flatAmount = round2(totals.flatAmount + row.flatAmount);
    if (row.km > limit) {
      limitWarnings.push({ vehicleId: row.vehicle.id, vehicleName: row.vehicle.name, km: row.km, limit });
    }
    vehicles.push({ ...row, rate, purposes: [...row.purposes.entries()].map(([purpose, km]) => ({ purpose, km })) });
  }

  totals.total = round2(totals.kmAmount + totals.flatAmount);
  return { month, vehicles, totals, limitWarnings };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test`
Expected: PASS — all tests (Task 1's 7 + 14 new).

- [ ] **Step 5: Commit**

```bash
git add projects/kilometrowka/src/km.js projects/kilometrowka/tests/km.test.js
git commit -m "feat: add trip aggregation with limits and ryczałt support"
```

---

### Task 4: "Kwota słownie" (amount in words)

**Files:**
- Create: `src/slownie.js`
- Test: `tests/slownie.test.js`

**Interfaces:**
- Consumes: nothing.
- Produces (used by Task 6): `slownieZl(amount)` → string, e.g. `slownieZl(1234.56)` → `'jeden tysiąc dwieście trzydzieści cztery złote 56/100'`

- [ ] **Step 1: Write the failing tests**

Create `tests/slownie.test.js`:

```js
import { describe, it, expect } from 'vitest';
import { slownieZl } from '../src/slownie.js';

describe('slownieZl', () => {
  it('declines złoty / złote / złotych correctly', () => {
    expect(slownieZl(1)).toBe('jeden złoty 00/100');
    expect(slownieZl(2)).toBe('dwa złote 00/100');
    expect(slownieZl(5)).toBe('pięć złotych 00/100');
    expect(slownieZl(21)).toBe('dwadzieścia jeden złoty 00/100');
    expect(slownieZl(22)).toBe('dwadzieścia dwa złote 00/100');
    expect(slownieZl(25)).toBe('dwadzieścia pięć złotych 00/100');
  });

  it('handles the 11–14 exception (…naście → złotych)', () => {
    expect(slownieZl(11)).toBe('jedenaście złotych 00/100');
    expect(slownieZl(12)).toBe('dwanaście złotych 00/100');
    expect(slownieZl(14)).toBe('czternaście złotych 00/100');
    expect(slownieZl(111)).toBe('sto jedenaście złotych 00/100');
    expect(slownieZl(114)).toBe('sto czternaście złotych 00/100');
  });

  it('handles thousands with correct declension', () => {
    expect(slownieZl(1000)).toBe('jeden tysiąc złotych 00/100');
    expect(slownieZl(2000)).toBe('dwa tysiące złotych 00/100');
    expect(slownieZl(5000)).toBe('pięć tysięcy złotych 00/100');
    expect(slownieZl(1234.56)).toBe('jeden tysiąc dwieście trzydzieści cztery złote 56/100');
  });

  it('handles millions, zero and grosze', () => {
    expect(slownieZl(1000000)).toBe('jeden milion złotych 00/100');
    expect(slownieZl(0)).toBe('zero złotych 00/100');
    expect(slownieZl(0.05)).toBe('zero złotych 05/100');
    expect(slownieZl(100.3)).toBe('sto złotych 30/100');
  });

  it('rounds grosze from floating point products', () => {
    expect(slownieZl(1234.56)).toBe('jeden tysiąc dwieście trzydzieści cztery złote 56/100');
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/slownie.js`**

```js
const JEDNOSCI = ['', 'jeden', 'dwa', 'trzy', 'cztery', 'pięć', 'sześć', 'siedem', 'osiem', 'dziewięć'];
const NASTKI = ['dziesięć', 'jedenaście', 'dwanaście', 'trzynaście', 'czternaście', 'piętnaście', 'szesnaście', 'siedemnaście', 'osiemnaście', 'dziewiętnaście'];
const DZIESIATKI = ['', 'dziesięć', 'dwadzieścia', 'trzydzieści', 'czterdzieści', 'pięćdziesiąt', 'sześćdziesiąt', 'siedemdziesiąt', 'osiemdziesiąt', 'dziewięćdziesiąt'];
const SETKI = ['', 'sto', 'dwieście', 'trzysta', 'czterysta', 'pięćset', 'sześćset', 'siedemset', 'osiemset', 'dziewięćset'];

function trzyCyfry(n) {
  const setki = Math.floor(n / 100);
  const reszta = n % 100;
  const czesci = [];
  if (setki) czesci.push(SETKI[setki]);
  if (reszta) {
    const d = Math.floor(reszta / 10);
    const j = reszta % 10;
    czesci.push(d === 1 ? NASTKI[j] : [DZIESIATKI[d], JEDNOSCI[j]].filter(Boolean).join(' '));
  }
  return czesci.join(' ');
}

// Polish plural declension: 1 → po1, 2–4 (but not 12–14) → po24, otherwise poWiele.
function forma(n, [po1, po24, poWiele]) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return po1;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return po24;
  return poWiele;
}

function liczbaSlownie(n) {
  if (n === 0) return 'zero';
  const czesci = [];
  const miliony = Math.floor(n / 1000000);
  const tysiace = Math.floor((n % 1000000) / 1000);
  const reszta = n % 1000;
  if (miliony) czesci.push(`${trzyCyfry(miliony)} ${forma(miliony, ['milion', 'miliony', 'milionów'])}`);
  if (tysiace) czesci.push(`${trzyCyfry(tysiace)} ${forma(tysiace, ['tysiąc', 'tysiące', 'tysięcy'])}`);
  if (reszta) czesci.push(trzyCyfry(reszta));
  return czesci.join(' ');
}

export function slownieZl(amount) {
  const zl = Math.floor(amount);
  const gr = Math.round((amount - zl) * 100);
  return `${liczbaSlownie(zl)} ${forma(zl, ['złoty', 'złote', 'złotych'])} ${String(gr).padStart(2, '0')}/100`;
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test`
Expected: PASS — 5 new tests.

- [ ] **Step 5: Commit**

```bash
git add projects/kilometrowka/src/slownie.js projects/kilometrowka/tests/slownie.test.js
git commit -m "feat: add Polish amount-in-words (kwota słownie) with declension"
```

---

### Task 5: UI core (form, list, monthly summary)

**Files:**
- Modify: `index.html` (app shell)
- Modify: `src/main.js`
- Modify: `src/style.css` (replace template styles)
- Test: `tests/main.test.js` (jsdom)

**Interfaces:**
- Consumes: `createStore`/`StoreError` (Task 2), `parseKm`/`nextId`/`addTrip`/`aggregateMonth` (Task 3), `rateFor` (Task 1).
- Produces (used by Tasks 6, 7, 8, 10):
  - `currentMonth()` → `'YYYY-MM'` of today
  - `initApp(root, deps = {})` → `{ getState: () => state }`; `deps` = `{ storage, store }` for dependency injection in tests. Renders the app into `root` and wires the trip form.

- [ ] **Step 1: Write the failing tests**

Create `tests/main.test.js`:

```js
// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { initApp, currentMonth } from '../src/main.js';
import { createStore } from '../src/store.js';

function memoryStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
  };
}

function setup() {
  const storage = memoryStorage();
  const root = document.createElement('div');
  document.body.appendChild(root);
  const app = initApp(root, { storage, store: createStore(storage) });
  return { root, app };
}

describe('currentMonth', () => {
  it('formats as YYYY-MM', () => {
    expect(currentMonth()).toMatch(/^\d{4}-\d{2}$/);
  });
});

describe('initApp', () => {
  it('renders the default vehicle and an empty summary', () => {
    const { root, app } = setup();
    expect(root.querySelector('select[name="vehicleId"]').children).toHaveLength(1);
    expect(app.getState().vehicles).toHaveLength(1);
    expect(app.getState().vehicles[0].capacityClass).toBe('>900');
    expect(root.textContent).toContain('Brak przejazdów');
  });

  it('adds a trip via the form with a comma decimal and updates the summary', () => {
    const { root, app } = setup();
    const form = root.querySelector('#trip-form');
    form.querySelector('input[name="date"]').value = '2026-10-08';
    form.querySelector('input[name="start"]').value = 'Warszawa';
    form.querySelector('input[name="end"]').value = 'Gdańsk';
    form.querySelector('input[name="purpose"]').value = 'klient';
    form.querySelector('input[name="km"]').value = '100,5';
    form.dispatchEvent(new Event('submit'));
    expect(app.getState().trips).toHaveLength(1);
    expect(app.getState().trips[0].km).toBe(100.5);
    expect(root.querySelector('#summary').textContent).toContain('115,57');
  });

  it('shows a Polish error for invalid km input and does not save', () => {
    const { root, app } = setup();
    const form = root.querySelector('#trip-form');
    form.querySelector('input[name="date"]').value = '2026-10-08';
    form.querySelector('input[name="km"]').value = 'sto';
    form.dispatchEvent(new Event('submit'));
    expect(app.getState().trips).toHaveLength(0);
    const error = root.querySelector('.error');
    expect(error.hidden).toBe(false);
    expect(error.textContent).toContain('kilometrów');
  });

  it('shows the clean StoreError message when stored data is corrupt', () => {
    const storage = memoryStorage();
    storage.setItem('kilometrowka.v1', '{zepsute');
    const root = document.createElement('div');
    document.body.appendChild(root);
    initApp(root, { storage, store: createStore(storage) });
    expect(root.textContent).toContain('uszkodzone');
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test`
Expected: FAIL — `src/main.js` is template boilerplate without `initApp`.

- [ ] **Step 3: Implement `index.html` app shell**

Replace `index.html`:

```html
<!doctype html>
<html lang="pl">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Kalkulator kilometrówki</title>
    <script type="module" src="/src/main.js"></script>
  </head>
  <body>
    <main id="app"></main>
  </body>
</html>
```

- [ ] **Step 4: Implement `src/main.js`**

```js
import './style.css';
import { createStore, StoreError } from './store.js';
import { addTrip, aggregateMonth, nextId, parseKm } from './km.js';
import { rateFor } from './rates.js';

export function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

export function initApp(root, deps = {}) {
  const storage = deps.storage ?? window.localStorage;
  const store = deps.store ?? createStore(storage);

  let state;
  try {
    state = store.load();
  } catch (err) {
    if (err instanceof StoreError) {
      root.innerHTML = `<p class="error">${err.message}</p>`;
      return { getState: () => null };
    }
    throw err;
  }

  if (state.vehicles.length === 0) {
    state = { ...state, vehicles: [{ id: 1, name: 'Mój samochód', plate: '', capacityClass: '>900' }] };
    store.save(state);
  }

  let month = currentMonth();

  root.innerHTML = `
    <h1>Ewidencja przebiegu pojazdu</h1>
    <p class="privacy">Dane nie opuszczają Twojej przeglądarki — wszystko zapisuje się lokalnie.</p>
    <form id="trip-form">
      <label>Data <input type="date" name="date" required /></label>
      <label>Skąd <input type="text" name="start" placeholder="np. Warszawa" /></label>
      <label>Dokąd <input type="text" name="end" placeholder="np. Gdańsk" /></label>
      <label>Cel <input type="text" name="purpose" placeholder="np. spotkanie z klientem" /></label>
      <label>Km <input type="text" name="km" inputmode="decimal" placeholder="np. 12,5" required /></label>
      <label>Pojazd <select name="vehicleId"></select></label>
      <button type="submit">Dodaj przejazd</button>
    </form>
    <div id="summary"></div>
    <div id="trips"></div>
  `;

  const form = root.querySelector('#trip-form');
  const vehicleSelect = form.querySelector('select[name="vehicleId"]');
  const summaryEl = root.querySelector('#summary');
  const tripsEl = root.querySelector('#trips');
  const errorEl = document.createElement('p');
  errorEl.className = 'error';
  errorEl.hidden = true;
  form.after(errorEl);

  function render() {
    vehicleSelect.innerHTML = state.vehicles
      .map((v) => `<option value="${v.id}">${v.name}</option>`)
      .join('');
    const summary = aggregateMonth(state, month);
    const fmt = new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' });
    summaryEl.innerHTML = `
      <h2>Podsumowanie — ${month}</h2>
      <table>
        <tr><th>Pojazd</th><th>Km</th><th>Stawka</th><th>Kwota</th></tr>
        ${summary.vehicles
          .map(
            (v) =>
              `<tr><td>${v.vehicle.name}</td><td>${v.km}</td><td>${v.rate.toFixed(2)} zł</td><td>${fmt.format(v.kmAmount)}</td></tr>`,
          )
          .join('')}
      </table>
      <p class="total">Razem: ${fmt.format(summary.totals.total)}</p>
      ${summary.limitWarnings
        .map((w) => `<p class="warning">Uwaga: ${w.vehicleName} przekroczył limit ${w.limit} km w tym miesiącu (${w.km} km).</p>`)
        .join('')}
    `;
    const monthTrips = state.trips.filter((t) => t.date.slice(0, 7) === month);
    tripsEl.innerHTML =
      '<h3>Przejazdy</h3>' +
      (monthTrips.length
        ? `<ul>${monthTrips
            .map((t) => `<li>${t.date} — ${[t.start, t.end].filter(Boolean).join(' – ') || '(brak trasy)'} — ${t.km} km</li>`)
            .join('')}</ul>`
        : '<p>Brak przejazdów w tym miesiącu.</p>');
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    errorEl.hidden = true;
    const data = new FormData(form);
    let km;
    try {
      km = parseKm(data.get('km'));
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
      return;
    }
    state = addTrip(state, {
      id: nextId(state),
      date: data.get('date'),
      start: data.get('start'),
      end: data.get('end'),
      purpose: data.get('purpose'),
      km,
      vehicleId: Number(data.get('vehicleId')),
    });
    store.save(state);
    form.reset();
    render();
  });

  render();
  return { getState: () => state };
}
```

- [ ] **Step 5: Replace `src/style.css`**

```css
body {
  font-family: system-ui, sans-serif;
  max-width: 720px;
  margin: 2rem auto;
  padding: 0 1rem;
  color: #222;
}
form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.5rem;
  margin: 1rem 0;
}
label {
  display: flex;
  flex-direction: column;
  font-size: 0.85rem;
  gap: 0.2rem;
}
table {
  border-collapse: collapse;
  width: 100%;
}
th, td {
  border: 1px solid #ccc;
  padding: 0.3rem 0.5rem;
  text-align: left;
}
.total {
  font-weight: bold;
}
.error {
  color: #b00020;
}
.warning {
  color: #8a5a00;
}
.privacy {
  font-size: 0.85rem;
  color: #555;
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `npm test`
Expected: PASS — 5 new tests. (If the summary test fails on the amount format, check `Intl.NumberFormat('pl-PL')` output for 115,58 zł — it formats as `115,58 zł` with a non-breaking space; adjust the assertion to use `toContain('115,58')` as written.)

- [ ] **Step 7: Commit**

```bash
git add projects/kilometrowka/index.html projects/kilometrowka/src/main.js projects/kilometrowka/src/style.css projects/kilometrowka/tests/main.test.js
git commit -m "feat: add trip form, list and monthly summary UI"
```

---

### Task 6: PDF report

**Files:**
- Create: `src/pdf/report.js`
- Test: `tests/report.test.js`
- Modify: `package.json` (deps)

**Interfaces:**
- Consumes: `slownieZl` (Task 4); summary shape from `aggregateMonth` (Task 3, note each summary vehicle row includes `rate`).
- Produces (used by Task 10):
  - `monthLabel(month)` → string, e.g. `'2026-10'` → `'październik 2026'`
  - `buildReportDef({ sellerName, vehicle, monthLabel, trips, summary, logoDataUrl })` → pdfmake docDefinition
  - `pdfToBlob(def)` → `Promise<Blob>` (for tests)
  - `downloadReport(def, filename)` — triggers a browser download

- [ ] **Step 1: Install dependencies**

```bash
npm install pdfmake && npm install -D pdfjs-dist
```

- [ ] **Step 2: Write the failing tests**

Create `tests/report.test.js`:

```js
import { describe, it, expect } from 'vitest';
import { buildReportDef, monthLabel, pdfToBlob } from '../src/pdf/report.js';
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';

describe('monthLabel', () => {
  it('formats Polish month names', () => {
    expect(monthLabel('2026-10')).toBe('październik 2026');
    expect(monthLabel('2026-01')).toBe('styczeń 2026');
  });
});

describe('buildReportDef', () => {
  const summary = {
    vehicles: [{ vehicle: { id: 1, name: 'Mój samochód', plate: 'WA 12345' }, km: 150, kmAmount: 172.5, flatAmount: 0, total: 172.5, rate: 1.15 }],
  };

  it('contains the seller, vehicle and slownie line', () => {
    const def = buildReportDef({
      sellerName: 'Żaneta Łukasiewicz',
      vehicle: { id: 1, name: 'Mój samochód', plate: 'WA 12345' },
      monthLabel: 'październik 2026',
      trips: [{ date: '2026-10-05', start: 'Warszawa', end: 'Gdańsk', purpose: 'klient', km: 150 }],
      summary,
    });
    const flatText = JSON.stringify(def.content);
    expect(flatText).toContain('Żaneta Łukasiewicz');
    expect(flatText).toContain('WA 12345');
    expect(flatText).toContain('Słownie:');
    expect(flatText).toContain('sto siedemdziesiąt dwa złote 50/100');
  });

  it('always ends with the fiscal disclaimer', () => {
    const def = buildReportDef({ sellerName: '', vehicle: { id: 1, name: 'A' }, monthLabel: 'x', trips: [], summary });
    const last = def.content[def.content.length - 1].text;
    expect(last).toContain('nie zastępuje programu księgowego');
  });
});

describe('pdfToBlob', () => {
  it('renders Polish diacritics into the actual PDF', async () => {
    const def = buildReportDef({
      sellerName: 'Żaneta Łukasiewicz',
      vehicle: { id: 1, name: 'Samochód służbowy', plate: '' },
      monthLabel: 'październik 2026',
      trips: [{ date: '2026-10-05', start: 'Łódź', end: 'Gdańsk', purpose: 'spotkanie', km: 100 }],
      summary: { vehicles: [{ vehicle: { id: 1, name: 'Samochód służbowy' }, km: 100, kmAmount: 115, flatAmount: 0, total: 115, rate: 1.15 }] },
    });
    const blob = await pdfToBlob(def);
    const doc = await getDocument({ data: new Uint8Array(await blob.arrayBuffer()) }).promise;
    const page = await doc.getPage(1);
    const text = (await page.getTextContent()).items.map((i) => i.str).join(' ');
    expect(text).toContain('Żaneta Łukasiewicz');
    expect(text).toContain('Łódź');
    expect(text).toContain('październik');
    expect(text).toContain('sto piętnaście złotych');
  }, 30000);
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `npm test`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `src/pdf/report.js`**

```js
import pdfMake from 'pdfmake/build/pdfmake';
import pdfFonts from 'pdfmake/build/vfs_fonts';
import { slownieZl } from '../slownie.js';

// pdfmake's bundled Roboto includes Polish glyphs; the extraction test in
// tests/report.test.js enforces that diacritics actually render.
pdfMake.vfs = pdfFonts.pdfMake ? pdfFonts.pdfMake.vfs : pdfFonts.vfs;

const MIESIACE = [
  'stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca',
  'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia',
];

export function monthLabel(month) {
  const [year, monthIndex] = month.split('-');
  return `${MIESIACE[Number(monthIndex) - 1]} ${year}`;
}

export function buildReportDef({ sellerName, vehicle, monthLabel: label, trips, summary, logoDataUrl }) {
  const vehicleSummary = summary.vehicles.find((v) => v.vehicle.id === vehicle.id) ?? {
    km: 0, kmAmount: 0, flatAmount: 0, total: 0, rate: 0,
  };

  const content = [];
  if (logoDataUrl) {
    content.push({ image: logoDataUrl, width: 120, margin: [0, 0, 0, 8] });
  }
  content.push(
    { text: 'EWIDENCJA PRZEBIEGU POJAZDU', style: 'title' },
    { text: `Pojazd: ${vehicle.name}${vehicle.plate ? ` (${vehicle.plate})` : ''}`, margin: [0, 4, 0, 0] },
    { text: `Miesiąc: ${label}`, margin: [0, 2, 0, 0] },
    sellerName ? { text: sellerName, margin: [0, 8, 0, 0] } : null,
    { text: `Stawka: ${vehicleSummary.rate.toFixed(2)} zł/km`, margin: [0, 2, 0, 0] },
    { text: `Do zapłaty: ${vehicleSummary.total.toFixed(2).replace('.', ',')} zł`, margin: [0, 2, 0, 12] },
    { text: `Słownie: ${slownieZl(vehicleSummary.total)}`, italics: true, margin: [0, 0, 0, 12] },
    {
      table: {
        widths: ['auto', '*', '*', 'auto'],
        body: [
          [
            { text: 'Data', bold: true },
            { text: 'Trasa', bold: true },
            { text: 'Cel podróży', bold: true },
            { text: 'Km', bold: true, alignment: 'right' },
          ],
          ...trips.map((t) => [
            t.date,
            [t.start, t.end].filter(Boolean).join(' – '),
            t.purpose,
            { text: String(t.km), alignment: 'right' },
          ]),
          [
            { text: 'Razem', colSpan: 3, bold: true }, {}, {},
            { text: String(vehicleSummary.km), bold: true, alignment: 'right' },
          ],
        ],
      },
    },
    {
      text: 'Niniejszy dokument nie zastępuje programu księgowego ani doradcy podatkowego.',
      style: 'disclaimer',
      margin: [0, 20, 0, 0],
    },
  );

  return {
    content: content.filter(Boolean),
    defaultStyle: { fontSize: 10 },
    styles: {
      title: { fontSize: 16, bold: true, margin: [0, 0, 0, 4] },
      disclaimer: { fontSize: 8, color: '#666666' },
    },
  };
}

export function pdfToBlob(def) {
  return new Promise((resolve) => {
    pdfMake.createPdf(def).getBlob(resolve);
  });
}

export function downloadReport(def, filename) {
  pdfMake.createPdf(def).download(filename);
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `npm test`
Expected: PASS — 4 new tests. (If pdfjs-dist throws `ReferenceError: DOMMatrix is not defined`, add at the top of `tests/report.test.js`, before the pdfjs import: `if (!globalThis.DOMMatrix) globalThis.DOMMatrix = class { constructor() {} };`)

- [ ] **Step 6: Commit**

```bash
git add projects/kilometrowka/src/pdf/report.js projects/kilometrowka/tests/report.test.js projects/kilometrowka/package.json projects/kilometrowka/package-lock.json
git commit -m "feat: add monthly report PDF with Polish diacritics and kwota słownie"
```

---

### Task 7: Lemon Squeezy license

**Files:**
- Create: `src/license.js`
- Test: `tests/license.test.js`

**Interfaces:**
- Consumes: nothing (fetch is injected for tests).
- Produces (used by Task 10):
  - `LICENSE_KEY = 'kilometrowka.license'` (localStorage key)
  - `CHECKOUT_URL = ''` — Lemon Squeezy checkout link; **set in Task 11 after the LS product exists**
  - `activateLicense(licenseKey, fetchImpl = fetch)` → `{ ok, status, instanceId?, error? }` where `status` is `'active' | 'invalid' | 'failed' | <LS status>`
  - `validateLicense(licenseKey, instanceId, fetchImpl = fetch)` → `{ ok, status }` (`'active' | 'expired' | 'disabled' | 'invalid' | 'failed'`)
  - `saveLicense(storage, license)` / `loadLicense(storage)` → license object or null
  - `isPro(license)` → boolean

- [ ] **Step 1: Write the failing tests**

Create `tests/license.test.js`:

```js
import { describe, it, expect } from 'vitest';
import { activateLicense, validateLicense, saveLicense, loadLicense, isPro, LICENSE_KEY } from '../src/license.js';

const okFetch = (payload, ok = true, status = 200) => async () => ({
  ok, status, json: async () => payload,
});
const failFetch = async () => { throw new Error('network down'); };

describe('activateLicense', () => {
  it('activates a valid key and returns the instance id', async () => {
    const fetchImpl = okFetch({
      activated: true,
      license_key: { id: 1 },
      instance: { id: 42 },
      meta: { status: 'active' },
    });
    const result = await activateLicense('abc-123', fetchImpl);
    expect(result).toEqual({ ok: true, status: 'active', instanceId: 42, licenseKey: 'abc-123' });
  });

  it('returns invalid for a rejected key', async () => {
    const fetchImpl = okFetch({ errors: [{ detail: 'The license key is invalid.' }] }, false, 404);
    const result = await activateLicense('zly-klucz', fetchImpl);
    expect(result.ok).toBe(false);
    expect(result.status).toBe('invalid');
    expect(result.error).toContain('Nieprawidłowy klucz licencyjny');
  });

  it('returns failed when the network is down', async () => {
    const result = await activateLicense('abc', failFetch);
    expect(result).toEqual({ ok: false, status: 'failed', error: expect.stringContaining('serwerem licencji') });
  });
});

describe('validateLicense', () => {
  it('accepts an active instance', async () => {
    const result = await validateLicense('abc', 42, okFetch({ meta: { status: 'active' } }));
    expect(result).toEqual({ ok: true, status: 'active' });
  });

  it('reports expired and disabled licenses', async () => {
    expect((await validateLicense('abc', 42, okFetch({ meta: { status: 'expired' } }))).status).toBe('expired');
    expect((await validateLicense('abc', 42, okFetch({ meta: { status: 'disabled' } }))).status).toBe('disabled');
  });

  it('returns failed when the network is down', async () => {
    expect((await validateLicense('abc', 42, failFetch)).status).toBe('failed');
  });
});

describe('saveLicense / loadLicense / isPro', () => {
  const storage = {
    map: new Map(),
    getItem(k) { return this.map.has(k) ? this.map.get(k) : null; },
    setItem(k, v) { this.map.set(k, String(v)); },
  };

  it('round-trips a license and survives corrupt data', () => {
    saveLicense(storage, { status: 'active', instanceId: 42, licenseKey: 'abc' });
    expect(loadLicense(storage)).toEqual({ status: 'active', instanceId: 42, licenseKey: 'abc' });
    expect(storage.getItem(LICENSE_KEY)).toContain('"instanceId":42');

    storage.setItem(LICENSE_KEY, '{zepsute');
    expect(loadLicense(storage)).toBeNull();
  });

  it('isPro is true only for active licenses', () => {
    expect(isPro({ status: 'active' })).toBe(true);
    expect(isPro({ status: 'expired' })).toBe(false);
    expect(isPro(null)).toBe(false);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/license.js`**

```js
export const LICENSE_KEY = 'kilometrowka.license';
// Set after creating the Lemon Squeezy product (see README, "Sprzedaż — Lemon Squeezy").
export const CHECKOUT_URL = '';

const API = 'https://api.lemonsqueezy.com/v1/licenses';

export async function activateLicense(licenseKey, fetchImpl = fetch) {
  try {
    const res = await fetchImpl(`${API}/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ license_key: licenseKey, instance_name: 'kilometrowka' }),
    });
    const data = await res.json();
    if (!res.ok) {
      return {
        ok: false,
        status: 'invalid',
        error: data.errors?.[0]?.detail ?? 'Nieprawidłowy klucz licencyjny.',
      };
    }
    return {
      ok: true,
      status: data.meta?.status === 'active' ? 'active' : data.meta?.status,
      instanceId: data.instance?.id,
      licenseKey,
    };
  } catch {
    return { ok: false, status: 'failed', error: 'Nie udało się połączyć z serwerem licencji. Sprawdź połączenie z internetem.' };
  }
}

export async function validateLicense(licenseKey, instanceId, fetchImpl = fetch) {
  try {
    const res = await fetchImpl(`${API}/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ license_key: licenseKey, instance_id: instanceId }),
    });
    const data = await res.json();
    if (!res.ok) {
      return { ok: false, status: 'invalid' };
    }
    const status = data.meta?.status === 'active' ? 'active' : data.meta?.status;
    return { ok: status === 'active', status };
  } catch {
    return { ok: false, status: 'failed' };
  }
}

export function saveLicense(storage, license) {
  storage.setItem(LICENSE_KEY, JSON.stringify(license));
}

export function loadLicense(storage) {
  const raw = storage.getItem(LICENSE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function isPro(license) {
  return Boolean(license && license.status === 'active');
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test`
Expected: PASS — 8 new tests.

- [ ] **Step 5: Commit**

```bash
git add projects/kilometrowka/src/license.js projects/kilometrowka/tests/license.test.js
git commit -m "feat: add Lemon Squeezy license activation and validation"
```

---

### Task 8: Landing page + SEO content

**Files:**
- Modify: `index.html` (add meta tags, rates section, how-to, FAQ, disclaimer)
- Test: `tests/landing.test.js`

**Interfaces:**
- Consumes: nothing (static content around `#app`).
- Produces: the public landing page — the tool plus the SEO content sections required by spec §8.

- [ ] **Step 1: Write the failing tests**

Create `tests/landing.test.js`:

```js
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const dom = new JSDOM(html);
const doc = dom.window.document;

describe('landing page SEO content', () => {
  it('has a Polish title with the primary keyword', () => {
    expect(doc.title).toContain('Kalkulator kilometrówki 2026');
  });

  it('has a meta description with a keyword', () => {
    const desc = doc.querySelector('meta[name="description"]').content;
    expect(desc).toContain('kilometrówki');
    expect(desc).toContain('ewidencja przebiegu pojazdu');
  });

  it('shows the current statutory rates table', () => {
    const text = doc.body.textContent;
    expect(text).toContain('1,15 zł');
    expect(text).toContain('0,89 zł');
    expect(text).toContain('0,69 zł');
    expect(text).toContain('0,42 zł');
  });

  it('contains the fiscal disclaimer', () => {
    expect(doc.body.textContent).toContain('nie zastępuje programu księgowego ani doradcy podatkowego');
  });

  it('answers FAQ questions', () => {
    const text = doc.body.textContent;
    expect(text).toContain('Czy kilometrówka wymaga ewidencji?');
    expect(text).toContain('limit 6000 km');
  });

  it('keeps the app mount point', () => {
    expect(doc.querySelector('#app')).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test`
Expected: FAIL — index.html lacks the content.

- [ ] **Step 3: Add the content to `index.html`**

Replace `index.html` with (note: `#app` stays where Task 5's `initApp` mounts):

```html
<!doctype html>
<html lang="pl">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Kalkulator kilometrówki 2026 — ewidencja przebiegu pojazdu online</title>
    <meta
      name="description"
      content="Darmowy kalkulator kilometrówki 2026 — prowadź ewidencję przebiegu pojazdu online, bez konta i bez wysyłania danych. Generuj miesięczny raport PDF. Stawki 0,89 zł, 1,15 zł, 0,69 zł, 0,42 zł za km."
    />
    <meta property="og:title" content="Kalkulator kilometrówki 2026" />
    <meta property="og:description" content="Darmowa ewidencja przebiegu pojazdu — wszystko w Twojej przeglądarce." />
    <script type="module" src="/src/main.js"></script>
  </head>
  <body>
    <main>
      <div id="app"></div>
      <section id="stawki">
        <h2>Stawki kilometrówki 2026</h2>
        <table>
          <tr><th>Pojazd</th><th>Stawka za 1 km</th><th>Limit miesięczny</th></tr>
          <tr><td>Samochód osobowy do 900 cm³</td><td>0,89 zł</td><td>6 000 km</td></tr>
          <tr><td>Samochód osobowy powyżej 900 cm³</td><td>1,15 zł</td><td>6 000 km</td></tr>
          <tr><td>Motocykl</td><td>0,69 zł</td><td>7 500 km</td></tr>
          <tr><td>Motorower</td><td>0,42 zł</td><td>7 500 km</td></tr>
        </table>
      </section>
      <section id="jak">
        <h2>Jak prowadzić ewidencję przebiegu pojazdu?</h2>
        <ol>
          <li>Dodaj przejazd: datę, trasę, cel i liczbę kilometrów.</li>
          <li>Narzędzie naliczy kwotę według obowiązującej stawki.</li>
          <li>Na koniec miesiąca pobierz gotowy raport PDF.</li>
        </ol>
      </section>
      <section id="faq">
        <h2>Częste pytania</h2>
        <details>
          <summary>Czy kilometrówka wymaga ewidencji?</summary>
          <p>Tak — zwrot kosztów używania prywatnego pojazdu do celów służbowych wymaga ewidencji przebiegu pojazdu zawierającej m.in. datę, trasę, cel i liczbę kilometrów.</p>
        </details>
        <details>
          <summary>Co oznacza limit 6000 km?</summary>
          <p>Miesięczny limit kilometrów dla samochodów osobowych wynosi 6 000 km (7 500 km dla motocykli i motorowerów). Narzędzie ostrzega po jego przekroczeniu.</p>
        </details>
        <details>
          <summary>Czy dane są bezpieczne?</summary>
          <p>Tak — wszystkie dane zapisują się wyłącznie w Twojej przeglądarce (localStorage). Nic nie jest wysyłane na serwer.</p>
        </details>
      </section>
      <footer>
        <p>Niniejszy dokument nie zastępuje programu księgowego ani doradcy podatkowego.</p>
      </footer>
    </main>
  </body>
</html>
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test`
Expected: PASS — 6 new tests.

- [ ] **Step 5: Commit**

```bash
git add projects/kilometrowka/index.html projects/kilometrowka/tests/landing.test.js
git commit -m "feat: add Polish landing page with rates table and FAQ"
```

---

### Task 9: Pro exports (XLSX + backup/restore)

**Files:**
- Create: `src/xlsx.js`
- Create: `src/backup.js`
- Test: `tests/exports.test.js`
- Modify: `package.json` (dep)

**Interfaces:**
- Consumes: state shape from Task 2.
- Produces (used by Task 10):
  - `tripRows(state)` → array of `{ Data, Skąd, Dokąd, 'Cel podróży', Km }`
  - `buildXlsx(state)` → SheetJS workbook
  - `exportTripsXlsx(state)` — triggers download
  - `validateState(parsed)` → normalized state; throws `StoreError`
  - `importBackup(text)` → state; throws `StoreError` on corrupt text
  - `exportBackup(state)` — triggers JSON download

- [ ] **Step 1: Install the dependency**

```bash
npm install xlsx
```

- [ ] **Step 2: Write the failing tests**

Create `tests/exports.test.js`:

```js
import { describe, it, expect } from 'vitest';
import * as XLSX from 'xlsx';
import { tripRows, buildXlsx } from '../src/xlsx.js';
import { validateState, importBackup } from '../src/backup.js';
import { StoreError } from '../src/store.js';

const state = {
  version: 1,
  vehicles: [{ id: 1, name: 'Auto', plate: '', capacityClass: '>900' }],
  trips: [{ id: 1, date: '2026-10-08', start: 'Warszawa', end: 'Gdańsk', purpose: 'klient', km: 340, vehicleId: 1 }],
  flats: [],
  sellerName: 'Jan Kowalski',
  logo: null,
};

describe('tripRows', () => {
  it('maps trips to Polish spreadsheet columns', () => {
    expect(tripRows(state)).toEqual([
      { Data: '2026-10-08', Skąd: 'Warszawa', Dokąd: 'Gdańsk', 'Cel podróży': 'klient', Km: 340 },
    ]);
  });
});

describe('buildXlsx', () => {
  it('produces a workbook that reads back the same rows', () => {
    const wb = buildXlsx(state);
    const buffer = XLSX.write(wb, { type: 'array' });
    const reread = XLSX.read(buffer);
    const sheet = reread.Sheets['Ewidencja'];
    const rows = XLSX.utils.sheet_to_json(sheet);
    expect(rows).toEqual([{ Data: '2026-10-08', Skąd: 'Warszawa', Dokąd: 'Gdańsk', 'Cel podróży': 'klient', Km: 340 }]);
  });
});

describe('validateState', () => {
  it('normalizes a valid backup', () => {
    expect(validateState({ vehicles: [], trips: [] })).toEqual({
      version: 1, vehicles: [], trips: [], flats: [], sellerName: '', logo: null,
    });
  });

  it('rejects wrong-shape data with StoreError', () => {
    expect(() => validateState({ vehicles: 'nie' })).toThrow(StoreError);
    expect(() => validateState(null)).toThrow(StoreError);
  });
});

describe('importBackup', () => {
  it('parses a valid JSON backup', () => {
    expect(importBackup(JSON.stringify(state))).toEqual(state);
  });

  it('throws StoreError on corrupt JSON', () => {
    expect(() => importBackup('{zepsute')).toThrow(StoreError);
    expect(() => importBackup('{zepsute')).toThrow(/uszkodzony/);
  });
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `npm test`
Expected: FAIL — modules not found.

- [ ] **Step 4: Implement `src/xlsx.js`**

```js
import * as XLSX from 'xlsx';

export function tripRows(state) {
  return state.trips.map((t) => ({
    Data: t.date,
    Skąd: t.start,
    Dokąd: t.end,
    'Cel podróży': t.purpose,
    Km: t.km,
  }));
}

export function buildXlsx(state) {
  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.json_to_sheet(tripRows(state));
  XLSX.utils.book_append_sheet(wb, ws, 'Ewidencja');
  return wb;
}

export function exportTripsXlsx(state) {
  XLSX.writeFile(buildXlsx(state), 'kilometrowka.xlsx');
}
```

- [ ] **Step 5: Implement `src/backup.js`**

```js
import { StoreError } from './store.js';

export function validateState(parsed) {
  if (
    typeof parsed !== 'object' ||
    parsed === null ||
    !Array.isArray(parsed.vehicles) ||
    !Array.isArray(parsed.trips)
  ) {
    throw new StoreError('Plik kopii zapasowej ma nieprawidłowy format.');
  }
  return {
    version: 1,
    vehicles: parsed.vehicles,
    trips: parsed.trips,
    flats: Array.isArray(parsed.flats) ? parsed.flats : [],
    sellerName: typeof parsed.sellerName === 'string' ? parsed.sellerName : '',
    logo: typeof parsed.logo === 'string' ? parsed.logo : null,
  };
}

export function importBackup(text) {
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new StoreError('Plik kopii zapasowej jest uszkodzony.');
  }
  return validateState(parsed);
}

export function exportBackup(state) {
  const blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'kilometrowka-kopia.json';
  a.click();
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `npm test`
Expected: PASS — 6 new tests.

- [ ] **Step 7: Commit**

```bash
git add projects/kilometrowka/src/xlsx.js projects/kilometrowka/src/backup.js projects/kilometrowka/tests/exports.test.js projects/kilometrowka/package.json projects/kilometrowka/package-lock.json
git commit -m "feat: add XLSX export and JSON backup/restore"
```

---

### Task 10: Pro features UI (gating, vehicles, archive, ryczałt, logo, PDF button)

**Files:**
- Modify: `src/main.js` (extend `initApp`)
- Modify: `src/style.css` (add `.pro` section styles)
- Test: `tests/pro.test.js` (jsdom)

**Interfaces:**
- Consumes: everything from Tasks 1–7 and 9.
- Produces: the complete app. After this task the free tier and every Pro feature are usable end-to-end in the browser.

- [ ] **Step 1: Write the failing tests**

Create `tests/pro.test.js`:

```js
// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { initApp } from '../src/main.js';
import { createStore } from '../src/store.js';
import { saveLicense, loadLicense } from '../src/license.js';

function memoryStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
  };
}

function setup(license = null, fetchImpl = null) {
  const storage = memoryStorage();
  const store = createStore(storage);
  if (license) saveLicense(storage, license);
  const root = document.createElement('div');
  document.body.appendChild(root);
  const app = initApp(root, {
    storage,
    store,
    // Tests never touch the network: if a test triggers a fetch it fails loudly.
    fetchImpl: fetchImpl ?? (async () => { throw new Error('nieoczekiwane wywołanie fetch w teście'); }),
  });
  return { root, app, storage, store };
}

describe('Pro panel', () => {
  it('shows the license form without an active license and no Pro controls', () => {
    const { root } = setup();
    expect(root.querySelector('#license-key')).not.toBeNull();
    expect(root.querySelector('#vehicles-panel')).toBeNull();
    expect(root.querySelector('#pdf-button')).toBeNull();
  });

  it('activates Pro with a valid license key', async () => {
    const fetchImpl = async () => ({
      ok: true,
      status: 200,
      json: async () => ({ meta: { status: 'active' }, instance: { id: 1 } }),
    });
    const { root, storage } = setup(null, fetchImpl);
    root.querySelector('#license-key').value = 'test-key';
    root.querySelector('#activate-button').click();
    await new Promise((r) => setTimeout(r, 0));
    expect(root.querySelector('#vehicles-panel')).not.toBeNull();
    expect(loadLicense(storage)).toEqual({ status: 'active', instanceId: 1, licenseKey: 'test-key' });
  });

  it('shows Pro controls immediately for a stored active license', () => {
    const { root } = setup({ status: 'active', licenseKey: 'k', instanceId: 1 });
    expect(root.querySelector('#vehicles-panel')).not.toBeNull();
    expect(root.querySelector('#pdf-button')).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test`
Expected: FAIL — no `#license-key`, `#vehicles-panel` or `#pdf-button` elements exist yet.

- [ ] **Step 3: Extend `src/main.js`**

Replace the whole file with the extended version (changes marked below the existing code):

```js
import './style.css';
import { createStore, StoreError } from './store.js';
import { addTrip, addFlat, aggregateMonth, nextId, parseKm } from './km.js';
import { rateFor } from './rates.js';
import { activateLicense, loadLicense, saveLicense, isPro, CHECKOUT_URL } from './license.js';
import { buildReportDef, downloadReport, monthLabel } from './pdf/report.js';
import { exportTripsXlsx } from './xlsx.js';
import { exportBackup, importBackup } from './backup.js';

export function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

export function initApp(root, deps = {}) {
  const storage = deps.storage ?? window.localStorage;
  const store = deps.store ?? createStore(storage);
  const fetchImpl = deps.fetchImpl ?? window.fetch;

  let state;
  try {
    state = store.load();
  } catch (err) {
    if (err instanceof StoreError) {
      root.innerHTML = `<p class="error">${err.message}</p>`;
      return { getState: () => null };
    }
    throw err;
  }

  if (state.vehicles.length === 0) {
    state = { ...state, vehicles: [{ id: 1, name: 'Mój samochód', plate: '', capacityClass: '>900' }] };
    store.save(state);
  }

  let license = loadLicense(storage);
  let month = currentMonth();

  root.innerHTML = `
    <h1>Ewidencja przebiegu pojazdu</h1>
    <p class="privacy">Dane nie opuszczają Twojej przeglądarki — wszystko zapisuje się lokalnie.</p>
    <form id="trip-form">
      <label>Data <input type="date" name="date" required /></label>
      <label>Skąd <input type="text" name="start" placeholder="np. Warszawa" /></label>
      <label>Dokąd <input type="text" name="end" placeholder="np. Gdańsk" /></label>
      <label>Cel <input type="text" name="purpose" placeholder="np. spotkanie z klientem" /></label>
      <label>Km <input type="text" name="km" inputmode="decimal" placeholder="np. 12,5" required /></label>
      <label>Pojazd <select name="vehicleId"></select></label>
      <button type="submit">Dodaj przejazd</button>
    </form>
    <div class="month-nav">
      <button id="prev-month" type="button">‹ Poprzedni miesiąc</button>
      <span id="month-label"></span>
      <button id="next-month" type="button">Następny miesiąc ›</button>
    </div>
    <div id="summary"></div>
    <div id="trips"></div>
    <section id="settings">
      <h2>Dane sprzedawcy</h2>
      <label>Imię i nazwisko / firma <input type="text" id="seller-name" /></label>
    </section>
    <section id="pro-panel"></section>
  `;

  const form = root.querySelector('#trip-form');
  const vehicleSelect = form.querySelector('select[name="vehicleId"]');
  const summaryEl = root.querySelector('#summary');
  const tripsEl = root.querySelector('#trips');
  const monthLabelEl = root.querySelector('#month-label');
  const sellerInput = root.querySelector('#seller-name');
  const proPanel = root.querySelector('#pro-panel');
  const errorEl = document.createElement('p');
  errorEl.className = 'error';
  errorEl.hidden = true;
  form.after(errorEl);

  function monthShift(delta) {
    const [y, m] = month.split('-').map(Number);
    const next = new Date(y, m - 1 + delta, 1);
    month = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`;
    render();
  }

  function render() {
    sellerInput.value = state.sellerName || '';
    vehicleSelect.innerHTML = state.vehicles
      .map((v) => `<option value="${v.id}">${v.name}</option>`)
      .join('');
    monthLabelEl.textContent = monthLabel(month);
    const summary = aggregateMonth(state, month);
    const fmt = new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' });
    summaryEl.innerHTML = `
      <h2>Podsumowanie — ${monthLabel(month)}</h2>
      <table>
        <tr><th>Pojazd</th><th>Km</th><th>Stawka</th><th>Kwota</th></tr>
        ${summary.vehicles
          .map(
            (v) =>
              `<tr><td>${v.vehicle.name}</td><td>${v.km}</td><td>${v.rate.toFixed(2)} zł</td><td>${fmt.format(v.kmAmount)}</td></tr>`,
          )
          .join('')}
      </table>
      <p class="total">Razem: ${fmt.format(summary.totals.total)}</p>
      ${summary.limitWarnings
        .map((w) => `<p class="warning">Uwaga: ${w.vehicleName} przekroczył limit ${w.limit} km w tym miesiącu (${w.km} km).</p>`)
        .join('')}
      ${isPro(license) ? `
        <button id="pdf-button" type="button">Pobierz raport PDF</button>
        <button id="xlsx-button" type="button">Eksportuj XLSX</button>
        <button id="backup-button" type="button">Kopia zapasowa (JSON)</button>
        <label class="file-label">Przywróć kopię <input type="file" id="backup-file" accept=".json" /></label>
      ` : ''}
    `;
    const monthTrips = state.trips.filter((t) => t.date.slice(0, 7) === month);
    tripsEl.innerHTML =
      '<h3>Przejazdy</h3>' +
      (monthTrips.length
        ? `<ul>${monthTrips
            .map((t) => `<li>${t.date} — ${[t.start, t.end].filter(Boolean).join(' – ') || '(brak trasy)'} — ${t.km} km</li>`)
            .join('')}</ul>`
        : '<p>Brak przejazdów w tym miesiącu.</p>');
    renderProPanel();
  }

  function renderProPanel() {
    if (isPro(license)) {
      proPanel.innerHTML = `
        <h2>PRO — aktywny</h2>
        <section id="vehicles-panel">
          <h3>Pojazdy</h3>
          <ul>${state.vehicles.map((v) => `<li>${v.name} (${rateFor(v.capacityClass).rate.toFixed(2)} zł/km)</li>`).join('')}</ul>
          <form id="vehicle-form">
            <label>Nazwa <input name="name" required /></label>
            <label>Nr rejestracyjny <input name="plate" /></label>
            <label>Klasa
              <select name="capacityClass">
                <option value="<=900">do 900 cm³</option>
                <option value=">900">powyżej 900 cm³</option>
                <option value="motorcycle">Motocykl</option>
                <option value="moped">Motorower</option>
              </select>
            </label>
            <button type="submit">Dodaj pojazd</button>
          </form>
        </section>
        <section id="flat-panel">
          <h3>Ryczałt miesięczny</h3>
          <form id="flat-form">
            <label>Miesiąc <input type="month" name="month" required /></label>
            <label>Kwota <input type="text" name="amount" inputmode="decimal" placeholder="np. 250" required /></label>
            <label>Pojazd <select name="vehicleId">${state.vehicles.map((v) => `<option value="${v.id}">${v.name}</option>`).join('')}</select></label>
            <button type="submit">Dodaj ryczałt</button>
          </form>
        </section>
        <section id="breakdown-panel">
          <h3>Zestawienie według celów — ${monthLabel(month)}</h3>
          ${aggregateMonth(state, month).vehicles
            .map((v) => `<p>${v.vehicle.name}: ${v.purposes.map((p) => `${p.purpose} (${p.km} km)`).join(', ') || '—'}</p>`)
            .join('')}
        </section>
        <section id="logo-panel">
          <h3>Logo na raporcie</h3>
          <input type="file" id="logo-file" accept="image/*" />
        </section>
      `;
      proPanel.querySelector('#vehicle-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const d = new FormData(e.target);
        state = { ...state, vehicles: [...state.vehicles, { id: nextId(state), name: d.get('name'), plate: d.get('plate'), capacityClass: d.get('capacityClass') }] };
        store.save(state);
        render();
      });
      proPanel.querySelector('#flat-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const d = new FormData(e.target);
        const amount = parseKm(d.get('amount'));
        state = addFlat(state, { id: nextId(state), month: d.get('month'), amount, vehicleId: Number(d.get('vehicleId')) });
        store.save(state);
        render();
      });
      proPanel.querySelector('#logo-file').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        if (file.size > 500 * 1024) {
          alert('Plik logo jest za duży (maks. 500 KB).');
          return;
        }
        const reader = new FileReader();
        reader.onload = () => {
          state = { ...state, logo: reader.result };
          store.save(state);
          render();
        };
        reader.readAsDataURL(file);
      });
    } else {
      proPanel.innerHTML = `
        <h2>Wersja PRO — 79 zł (jednorazowo)</h2>
        <ul>
          <li>Wiele pojazdów</li>
          <li>Archiwum wszystkich miesięcy</li>
          <li>Eksport XLSX i kopia zapasowa</li>
          <li>Ryczałt miesięczny</li>
          <li>Zestawienie według celów</li>
          <li>Logo na raporcie PDF</li>
        </ul>
        <form id="license-form">
          <label>Klucz licencyjny <input type="text" id="license-key" placeholder="np. abc123-..." required /></label>
          <button id="activate-button" type="submit">Aktywuj PRO</button>
        </form>
        <p id="license-error" class="error" hidden></p>
        ${CHECKOUT_URL ? `<p><a href="${CHECKOUT_URL}" target="_blank" rel="noopener">Kup PRO za 79 zł →</a></p>` : ''}
      `;
      proPanel.querySelector('#license-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const key = proPanel.querySelector('#license-key').value.trim();
        const result = await activateLicense(key, fetchImpl);
        const errorEl2 = proPanel.querySelector('#license-error');
        if (result.ok) {
          license = { status: result.status, instanceId: result.instanceId, licenseKey: result.licenseKey };
          saveLicense(storage, license);
          render();
        } else {
          errorEl2.textContent = result.error ?? 'Nieprawidłowy klucz licencyjny.';
          errorEl2.hidden = false;
        }
      });
    }
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    errorEl.hidden = true;
    const data = new FormData(form);
    let km;
    try {
      km = parseKm(data.get('km'));
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
      return;
    }
    state = addTrip(state, {
      id: nextId(state),
      date: data.get('date'),
      start: data.get('start'),
      end: data.get('end'),
      purpose: data.get('purpose'),
      km,
      vehicleId: Number(data.get('vehicleId')),
    });
    store.save(state);
    form.reset();
    render();
  });

  sellerInput.addEventListener('change', () => {
    state = { ...state, sellerName: sellerInput.value };
    store.save(state);
  });

  root.querySelector('#prev-month').addEventListener('click', () => monthShift(-1));
  root.querySelector('#next-month').addEventListener('click', () => monthShift(1));

  // Delegate clicks inside #summary (buttons are re-created on every render).
  summaryEl.addEventListener('click', (event) => {
    const target = event.target;
    if (target.id === 'pdf-button') {
      const selectedId = Number(vehicleSelect.value);
      const vehicle = state.vehicles.find((v) => v.id === selectedId);
      const summary = aggregateMonth(state, month);
      const monthTrips = state.trips.filter((t) => t.date.slice(0, 7) === month && t.vehicleId === selectedId);
      const def = buildReportDef({
        sellerName: state.sellerName,
        vehicle,
        monthLabel: monthLabel(month),
        trips: monthTrips,
        summary,
        logoDataUrl: state.logo,
      });
      downloadReport(def, `kilometrowka-${month}.pdf`);
    }
    if (target.id === 'xlsx-button') {
      exportTripsXlsx(state);
    }
    if (target.id === 'backup-button') {
      exportBackup(state);
    }
  });

  // `#backup-file` is re-created on every render, so delegate the change event
  // on the persistent `#summary` element.
  summaryEl.addEventListener('change', (event) => {
    if (event.target.id !== 'backup-file') return;
    const file = event.target.files[0];
    if (!file) return;
    file.text().then((text) => {
      try {
        state = importBackup(text);
        store.save(state);
        license = loadLicense(storage);
        render();
      } catch (err) {
        alert(err.message);
      }
    });
  });

  render();
  return { getState: () => state };
}
```

- [ ] **Step 4: Add Pro styles to `src/style.css`**

Append:

```css
.month-nav {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 1rem 0;
}
.month-nav span {
  font-weight: bold;
  min-width: 10rem;
  text-align: center;
}
#pro-panel {
  border-top: 1px solid #ccc;
  margin-top: 2rem;
  padding-top: 1rem;
}
#pro-panel section {
  margin-top: 1rem;
}
.file-label {
  display: block;
  margin-top: 0.5rem;
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `npm test`
Expected: PASS — 3 new tests, all previous tests still green. (If the activate test races, the click handler awaits `activateLicense` internally; the `setTimeout(0)` in the test lets the promise resolve before assertions.)

- [ ] **Step 6: Manual smoke check**

Run: `npm run dev` and open the printed URL. Verify: add a trip with a comma decimal; navigate months; the Pro panel shows the license form; paste nothing (no license) — free tier works without any account.

- [ ] **Step 7: Commit**

```bash
git add projects/kilometrowka/src/main.js projects/kilometrowka/src/style.css projects/kilometrowka/tests/pro.test.js
git commit -m "feat: add Pro panel with license gating, vehicles, archive, ryczałt and PDF export"
```

---

### Task 11: README, .gitignore, deploy config

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Modify: `src/license.js` (set `CHECKOUT_URL` after the LS product exists — see README)

**Interfaces:**
- Consumes: the finished app.
- Produces: deployment and maintenance documentation.

- [ ] **Step 1: Create `projects/kilometrowka/.gitignore`**

```
node_modules/
dist/
```

- [ ] **Step 2: Create `projects/kilometrowka/README.md`**

````markdown
# Kilometrówka

Darmowy kalkulator kilometrówki 2026 — ewidencja przebiegu pojazdu w przeglądarce, bez konta i bez serwera. Część pakietu dokumentów dla polskich firm (patrz spec portfolio: `docs/superpowers/specs/2026-10-08-side-income-apps-design.md`).

## Development

```bash
npm install
npm run dev      # local dev server
npm test         # Vitest (TDD)
npm run build    # production build → dist/
```

## Architecture

- `src/rates.js` — versioned statutory rates (Dz.U. 2023 poz. 5 § 2); pure
- `src/km.js` — trip model, monthly aggregation, limits; pure
- `src/slownie.js` — "kwota słownie" with Polish declension; pure
- `src/store.js` — localStorage persistence (key `kilometrowka.v1`)
- `src/license.js` — Lemon Squeezy license activation/validation
- `src/pdf/report.js` — monthly report PDF (pdfmake)
- `src/xlsx.js`, `src/backup.js` — Pro exports
- `src/main.js` — UI wiring (SPA, no framework)

## Sprzedaż — Lemon Squeezy

1. Utwórz konto na lemonsqueezy.com i produkt „Kilometrówka PRO" — cena **79 zł, płatność jednorazowa** (one-time payment, nie subskrypcja).
2. Wygeneruj klucze licencyjne dla kupujących (Licenses → Generate).
3. Skopiuj link do kasy (checkout) produktu i wklej go do `CHECKOUT_URL` w `src/license.js`.
4. Aplikacja aktywuje klucz przez publiczne API `https://api.lemonsqueezy.com/v1/licenses/activate` (bez tajnego klucza — bezpieczne po stronie klienta).

## Deploy — Cloudflare Pages

1. Repozytorium: to repozytorium, gałąź `master`.
2. W dashboardzie Cloudflare Pages: **Create project → Connect to Git**.
3. Ustawienia build:
   - Root directory: `projects/kilometrowka`
   - Build command: `npm run build`
   - Build output directory: `dist`
4. Po deployu podłącz własną domenę (Cloudflare DNS), np. `kalkulatorkilometrowki.pl` (~12 zł/rok).

## Reguły

- Stawki kilometrówki aktualizuj w `src/rates.js` (nowy zestaw w `RATE_SETS` + zmiana `DEFAULT_RATE_SET`) i odśwież sekcję stawek w `index.html` oraz rok w `<title>`.
- Rok „2026" w copy (title, meta) aktualizuj co styczeń — styczeń to szczyt wyszukiwań.
- Nie obiecuj zgodności podatkowej — stopka z disclaimerem jest obowiązkowa w każdym PDF.

## Sprawdzony stan

- [ ] `npm test` — wszystkie testy przechodzą
- [ ] `npm run build` — build przechodzi
- [ ] `npx vite preview` — aplikacja działa, PDF zawiera polskie znaki
- [ ] Klucz testowy Lemon Squeezy aktywuje PRO
````

- [ ] **Step 3: Verify the full suite and build**

Run: `npm test && npm run build`
Expected: all tests PASS, build completes with `dist/` output.

- [ ] **Step 4: Commit**

```bash
git add projects/kilometrowka && git commit -m "docs: add README, gitignore and deploy instructions"
```

(If `dist/` was created, it is gitignored — `git add` of it is a no-op; the command still works.)

---

## Verification (whole plan)

After Task 11, run the complete verification:

```bash
cd projects/kilometrowka
npm test
npm run build
npx vite preview
```

Expected: every test green (Task 1's 7, Task 2's 5, Task 3's 14, Task 4's 5, Task 5's 5, Task 6's 4, Task 7's 8, Task 8's 6, Task 9's 6, Task 10's 3 — 63 total), production build succeeds, and the preview app handles: comma-decimal trips, month navigation, limit warnings, a PDF with correct Polish diacritics and "kwota słownie", and a mock-activated Pro panel.

Out-of-plan follow-ups (not part of this plan): buying the domain, creating the Lemon Squeezy product and setting `CHECKOUT_URL`, the Cloudflare Pages project, and the launch checklist from spec §8 (Wykop, forum.gofin.pl, JDG Facebook groups).
