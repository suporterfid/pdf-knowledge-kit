# Frontend Architecture Guide

This document explains how the React client inside `frontend/src/` is organized, which components are available, how shared state and API integrations are handled, and what styling conventions to follow when extending the UI.

## Project layout

```
frontend/src/
├── App.tsx                 # Router with public and protected routes
├── ChatPage.tsx            # Main end-user chat experience
├── Login.tsx               # API key capture form
├── RequireApiKey.tsx       # Route guard redirecting to login when missing a key
├── apiKey.tsx              # API key context + authenticated fetch helper
├── chat.tsx                # Chat context with streaming + retry logic
├── chat.test.tsx           # Integration tests for the chat flow
├── components/             # Chat-specific presentational components
│   ├── Composer.tsx
│   ├── ConversationPane.tsx
│   ├── Disclaimer.tsx
│   ├── ErrorBanner.tsx
│   ├── Footer.tsx
│   ├── Header.tsx
│   ├── Header.test.tsx
│   ├── Message.tsx
│   ├── Sidebar.tsx
│   └── SourcesList.tsx
├── admin/                  # Admin console (data ingestion & monitoring)
│   ├── AdminApp.tsx
│   ├── AdminRoute.tsx
│   ├── AgentBuilder.tsx
│   ├── Dashboard.tsx
│   ├── IngestLocal.tsx
│   ├── IngestUrl.tsx
│   ├── IngestUrls.tsx
│   ├── JobDetail.tsx
│   ├── LogViewer.tsx
│   ├── Sources.tsx
│   └── __tests__/
│       ├── AgentBuilder.test.tsx
│       ├── IngestLocal.test.tsx
│       └── Sources.test.tsx
├── config.tsx              # Runtime configuration provider
├── hooks/
│   └── useAuth.ts
├── main.tsx                # React entry point wiring all providers
├── theme.tsx               # Light/Dark theme context
├── theme.css               # Tailwind base + CSS variables shared across app
├── types.d.ts              # Ambient types for non-TypeScript assets
├── utils/
│   └── uuid.ts             # UUID helper used for conversation ids
└── … (test utilities, supporting files)
```

> **Tip:** the admin console deliberately lives under `/admin/*` routes and is lazy-free. Add new admin modules inside `frontend/src/admin/` so that routing stays colocated with the navigation inside `AdminApp.tsx`.

## Entry point & routing

The application boots from `main.tsx`, which wires a stack of React providers before rendering `<App />`:

```tsx
// main.tsx (excerpt)
<React.StrictMode>
  <ThemeProvider>
    <ApiKeyProvider>
      <ConfigProvider>
        <App />
      </ConfigProvider>
    </ApiKeyProvider>
  </ThemeProvider>
</React.StrictMode>
```

`App.tsx` owns the router setup. Public routes include `/login`; everything else is wrapped in `<RequireApiKey>` so users without an API key are redirected back to the login flow. Admin-only routes are also wrapped in `<AdminRoute>` which verifies operator/admin roles before rendering the admin console.

## Main chat experience

`ChatPage.tsx` orchestrates the conversational UI:

* Persists conversation metadata in `localStorage` (id, title, creation date) and redirects `/chat/new` requests to a fresh UUID.
* Wraps the page in `<ChatProvider>` (from `chat.tsx`) so all child components can access the chat state.
* Renders the chat layout with:
  * `<Sidebar />` – conversation history management (create/rename/delete) and mobile drawer behaviour.
  * `<Header />`, `<ErrorBanner />`, `<ConversationPane />`, `<Composer />`, `<Disclaimer />`, and `<Footer />` – arranged vertically in the content area.

### Reusable chat UI elements

All chat visuals live under `frontend/src/components/` and stick to a “presentational + props” style. Highlights:

* **Header.tsx** – brand/logo from `ConfigProvider`, new chat button, theme toggle (`useTheme()`), and a lightweight user menu. Responsive menu state is handled locally.
* **Sidebar.tsx** – reads/writes conversation metadata to `localStorage`, uses `clsx` for conditional Tailwind classes, and emits navigation events when users select a conversation.
* **Composer.tsx** – message input, attachment upload, cancel/regenerate controls hooked into the chat context.
* **ConversationPane.tsx** & **Message.tsx** – render a stream of chat messages, streaming status, and citations.
* **SourcesList.tsx** – lists retrieval sources returned by the backend.
* **ErrorBanner.tsx**, **Disclaimer.tsx**, **Footer.tsx** – lightweight components shared across chat and admin surfaces.

When building new UI, prefer colocating logic inside the chat context and keep components in this folder as stateless as possible.

## State management & shared contexts

This project does not use Redux/Zustand—state is managed with React context providers located alongside their domains:

* **`ApiKeyProvider` (`apiKey.tsx`)** – stores the API key in `localStorage` and exposes `apiKey`, `setApiKey`, and `clearApiKey`. Also exports `useApiFetch`, a memoised wrapper around `fetch` that injects the API key header and surfaces authentication errors via `react-toastify`.
* **`ConfigProvider` (`config.tsx`)** – bootstraps runtime configuration (brand label, upload limits, etc.) from a server-injected global and an `/api/config` request. Components consume the config through `useConfig()`.
* **`ThemeProvider` (`theme.tsx`)** – toggles light/dark mode by applying CSS variables to the `document.documentElement` and persisting the user’s choice in `localStorage`.
* **`ChatProvider` (`chat.tsx`)** – holds the entire chat session state: messages, streaming progress, sources, errors, cancellation, retry, and regenerate helpers. It persists message history per conversation in `localStorage`.
* **`useAuth` hook (`hooks/useAuth.ts`)** – reacts to API key changes, calls `/api/auth/roles`, and returns `{ roles, loading }`. `AdminRoute` and admin screens leverage this to gate privileged actions.

When introducing new global state, follow this pattern: create a dedicated context/provider pair and mount it in `main.tsx` so the provider order stays consistent.

## Backend integration

The app talks to the backend exclusively through `useApiFetch` and higher-level hooks/components that call it. This ensures the API key header and toast-based error reporting are always applied.

Typical usage looks like:

```tsx
const apiFetch = useApiFetch();

async function sendPrompt(text: string) {
  const params = new URLSearchParams({ q: text, k: '5', sessionId });
  const response = await apiFetch(`/api/chat?${params}`, { method: 'GET' });
  // handle streaming body...
}
```

Key integrations include:

* **Chat streaming (`chat.tsx`)** – orchestrates SSE-style streaming by reading chunks from `Response.body.getReader()`, interpreting `event:` lines, and updating `messages`/`sources` incrementally. It also handles file uploads, large-file pre-uploads (`/api/upload`), cancellation via `AbortController`, rate-limit errors, and retries.
* **Admin ingestion screens** – e.g., `IngestLocal.tsx` posts to `/api/admin/ingest/local` and requires `operator` or `admin` roles to enable the form. Other admin modules follow the same `useApiFetch` pattern.
* **Configuration** – `ConfigProvider` fetches `/api/config` once at mount to augment the injected defaults.
* **Authentication/Authorization** – `useAuth` hits `/api/auth/roles` and controls whether privileged UI should render.

Whenever you add a new backend call, ensure it goes through `useApiFetch()` so credentials and standard error handling remain consistent.

## Styling conventions

Styling is a blend of Tailwind utilities and handcrafted CSS variables defined in `theme.css`:

* **Tailwind** – the project is configured via `tailwind.config.js`. Components primarily use utility class strings (e.g., `className="flex flex-col gap-2"`).
* **CSS variables** – `theme.css` defines color tokens (`--color-bg`, `--color-surface`, etc.) for light and dark modes. `ThemeProvider` toggles them at runtime, and global element selectors (e.g., `.composer textarea`) enforce shared look-and-feel.
* **Class composition** – `clsx` is used in components like `Sidebar.tsx` to conditionally apply Tailwind classes.

When introducing new styles:

1. Reach for Tailwind utilities first for layout/spacing/typography.
2. If you need theme-aware colors or reusable tokens, extend `theme.css` and apply via the existing CSS variables.
3. Keep global overrides inside `theme.css`; component-specific adjustments can live inlined via Tailwind classes.

## Testing

The frontend uses `vitest`/`@testing-library/react` (see `chat.test.tsx` and the admin `__tests__` folder) to verify component behaviour. Tests typically render components with mocked providers and assert on user interactions. When adding components that depend on context or routing, provide the minimal wrapper (e.g., `MemoryRouter`, custom providers) inside the test file.

## Adding new functionality

* Place shared UI in `frontend/src/components/` and export a presentational component that receives data via props.
* Add new chat features by extending `ChatProvider` (for state) and the relevant components for the UI.
* Extend the admin console inside `frontend/src/admin/` and register routes/links in `AdminApp.tsx`.
* Prefer storing persistent user-specific data in `localStorage` (following the patterns in `ChatPage.tsx` and `chat.tsx`) so conversations survive reloads.
* Keep backend calls encapsulated, and add new hooks if a piece of logic is reused across screens.

Following these patterns will keep the frontend modular, testable, and easy to evolve.
