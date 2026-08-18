# DocQA — Frontend Client

Modern, responsive web interface for the DocQA RAG document platform built with **React 19**, **TypeScript**, and **Vite**.

## Architecture & Structure

- **`src/components/`**: Modular UI components:
  - `Sidebar.tsx`: Navigation, user profile card, upload dropzone, document list, conversation threads.
  - `ChatPanel.tsx`: Chat window, message history, streaming response renderer, input composer.
  - `MessageBubble.tsx`: Message bubble with full GitHub Flavored Markdown support via `react-markdown` and `remark-gfm`.
  - `SourceCard.tsx`: Interactive expandable citation cards showing relevance scores and matched chunk excerpts.
  - `AuthModal.tsx`: User registration, email/password login, and active user profile details.
  - `EmptyState.tsx`: Onboarding screen with actionable prompt suggestions.
- **`src/hooks/`**: Custom React hooks (`useChat`, `useDocuments`, `useConversations`, `useUsers`) managing state and API lifecycle.
- **`src/styles/`**: Modular CSS design system:
  - `variables.css`: Design tokens and color themes.
  - `base.css`: Reset, layout, and toast notification styles.
  - `sidebar.css`: Sidebar and document management styles.
  - `chat.css`: Messages, markdown typography, and input composer styles.
  - `auth.css`: Authentication modal and profile card styles.
- **`src/api/client.ts`**: Typed REST & SSE streaming client with JWT header management.

## Scripts

```bash
npm run dev     # Start Vite development server
npm run build   # Type-check with tsc and build production bundle
npm run preview # Preview production build locally
```
