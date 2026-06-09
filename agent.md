# Antigravity Agent Guidelines

Welcome, Antigravity Agent! This document outlines the project structure, development guidelines, stack details, and agent-specific instructions for working on the **Notes 2.0** application.

---

## 1. Project Architecture & Directory Structure

The project is structured as a monorepo containing a frontend React Router app and a Python-based backend.

```
c:/Coding Projects/notes2.0/
├── agent.md                  # This file (Agent guidelines)
├── README.md                 # Root readme (overall setup and running instructions)
├── notes2.0/                 # Frontend React Router project
│   ├── app/                  # Application code (routes, components, notes UI)
│   ├── public/               # Static assets
│   ├── package.json          # Node dependencies and scripts
│   └── tsconfig.json         # TypeScript configuration
└── backend/                  # Backend Python project
    └── .venv/                # Python virtual environment
```

> [!IMPORTANT]
> **Working Directory Context:**
> * Always run frontend-related commands (e.g., `npm run dev`, `npm install`) inside the `notes2.0/` directory.
> * Always activate the virtual environment and run backend commands inside the `backend/` directory.

---

## 2. Tech Stack & Tools

### Frontend (`notes2.0/`)
* **Core Framework:** React Router v7 (Vite-powered template)
* **Language:** TypeScript
* **Styling:** Tailwind CSS (configured via `tailwind.config` or standard setup)
* **Components:** UI components are standard React components (often using Radix UI/shadcn patterns if configured, check `components.json`).

### Backend (`backend/`)
* **Language:** Python 3
* **Environment:** Virtual environment is located at `backend/.venv/`
* **Framework:** FastAPI
* **Language Analysis / NLP:** NLTK (`nltk`) and TextStat (`textstat`) must be used as the default libraries for any text processing, readability metrics, or language analysis.

---

## 3. General Development Guidelines

* **Preserve Code Quality:** Maintain type safety. Use proper TypeScript definitions for all data structures (especially notes, categories, and analytical metadata).
* **Styling & Aesthetics:** 
  * Prioritize clean, modern UI aesthetics (sleek dark mode, using muted, cohesive colors and clean typography).
  * Avoid raw/harsh colors; use smooth Tailwind gradients and interactive hover animations.
* **Component-Driven Development:** Keep components modular, focused, and reusable. Create them inside `notes2.0/app/components/` if they are shared.

---

## 4. Agent Instructions for Antigravity

When completing tasks:
1. **Directory Awareness:** Ensure all commands are proposed with the correct `Cwd` parameter matching the sub-project you are working in.
2. **Investigation first:** Check existing code structure and imports before introducing new dependencies or creating duplicate helper functions.
3. **Responsive feedback:** Provide brief, structured summaries after completing tasks.
4. **Branching:** Whenever creating a new feature, automatically create a new git branch before writing code.

---

## 5. Backend Implementation Plan

### Overview
The backend will be built with **FastAPI** and serve as the analytical engine for Notes 2.0. It will process notes sent from the frontend (which are stored in `localStorage`) and return linguistic metrics.

### Frontend Connections
1. **Home Page**: The backend will interface with the home page to provide quick statistics, summaries, or aggregated analytics of the user's recent notes.
2. **Analytics Page**: The backend will power the detailed analytics page, supplying in-depth text analysis for the user's overall writing or specific notes.

### Analysis Features
The backend will leverage `nltk` and `textstat` to perform the following text analysis:
* **Sentence Length Analysis**: Calculate average sentence length, identify overly long run-on sentences, and analyze sentence structure variety.
* **Word Frequency**: Determine the most frequently used words, extract key themes, and filter out stop words.
* **Word Difficulty & Readability**: Calculate readability scores (e.g., Flesch-Kincaid Reading Ease), measure lexical diversity, and highlight complex vocabulary or jargon.

### API Design (Draft)
* `POST /api/analyze/note`
  * **Request Payload**: Receives the text content of a note from the frontend.
  * **Response**: JSON containing metrics (sentence length, word frequencies, readability scores).
* `POST /api/analyze/aggregate`
  * **Request Payload**: Receives an array of notes from the frontend's local storage.
  * **Response**: Aggregated analytics across all provided notes for the Analytics dashboard.
* `GET /health`
  * **Response**: Simple status check to confirm the backend is reachable from the frontend.

### Implementation Steps
1. Scaffold the FastAPI app inside `backend/` and configure CORS to allow requests from the React frontend.
2. Define Pydantic models for incoming note data and outgoing analysis results.
3. Implement the NLP logic using `nltk` and `textstat` for sentence splitting, tokenization, and readability calculation.
4. Create the API routes and integrate the analysis logic.
5. Implement frontend API client utilities in `notes2.0/` to fetch data from these endpoints on the Home and Analytics pages.
