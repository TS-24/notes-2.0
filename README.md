# Notes 2.0 📝

Notes 2.0 is a fast, minimal, and intuitive note-taking application designed to feel premium and snappy. It functions similarly to Google Keep but is augmented with AI-driven analytics, deep linguistic analysis, and a sleek user interface.

## 🌟 Features

- **Buttery Smooth UI:** Built with `framer-motion` for fluid, spring-physics-based animations across the entire application (sidebars, note expansions, card interactions).
- **Offline First:** Currently utilizes browser `localStorage` for immediate, lightning-fast note saving. 
- **Masonry Grid Layout:** Perfectly organizes your thoughts, lists, and ideas in a beautiful Pinterest-style grid.
- **Smart Note Creation:** A minimal, expanding text-bar inspired by modern search interfaces that gets out of your way.
- **AI & Analytics Ready:** Designed to connect to a FastAPI backend that uses Natural Language Processing to analyze your notes for readability, sentence structure, and vocabulary.

## 🏗️ Architecture (Monorepo)

This project is organized as a monorepo containing both the frontend and the analytical backend.

```
notes-2.0/
├── notes2.0/       # Frontend Application (React Router v7 + Vite)
├── backend/        # Backend Analytics API (Python + FastAPI)
├── agent.md        # Agent guidelines and architectural documentation
└── README.md       # This file
```

### Tech Stack

**Frontend (`notes2.0/`)**
- **Framework:** React Router v7
- **Language:** TypeScript
- **Styling:** Tailwind CSS + `shadcn/ui` components
- **Animations:** Framer Motion (`framer-motion`)
- **Layouts:** Masonic (Masonry grids)

**Backend (`backend/`)**
- **Framework:** FastAPI (Python 3)
- **NLP / Analysis:** NLTK (`nltk`) and TextStat (`textstat`)

---

## 🚀 Getting Started

### 1. Frontend Setup
Navigate into the frontend directory and start the Vite development server:
```bash
cd notes2.0
npm install
npm run dev
```
The application will be available at `http://localhost:5173`.

### 2. Backend Setup
Navigate into the backend directory, activate the virtual environment, and install dependencies:
```bash
cd backend
.venv\Scripts\activate
pip install -r requirements.txt
# (FastAPI server startup commands to be added here)
```